"""
Engine - The orchestration core of Ready Dual LLM.

Handles:
1. LLM API communication (LM Studio compatible)
2. Sigil parsing from model output
3. Tool dispatch and result injection
4. Autonomous tool→think→tool loops with LOOP PROTECTION
"""

import json
import requests
import threading
import os
import hashlib
import time
import base64
import mimetypes
from datetime import datetime

from core.sigil_parser import (
    parse_sigils, parse_write_block, parse_read_block,
    parse_terminal_block, parse_explorer_block, parse_delegate_block,
    parse_replace_block
)
from core.tools import Tools
from core.dataset import SYNTHETIC_MEMORY


class Engine:
    def __init__(self, config_path: str):
        self.config_path = config_path
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.manager_url = self.config['manager']['url']
        self.coder_url = self.config['coder']['url']

        self.manager_history = []
        self.coder_history = []

        self.tools = Tools()
        self._max_tool_loops = 50         # Safety: max consecutive tool-use rounds
        self._max_duplicate_calls = 1     # If same tool+args called this many times, STOP
        self._cancel_flag = False         # UI can set this to abort
        self._is_manager_running = False  # Track if manager is busy
        self._write_approve_fn = None     # Callback for write approval
        
        # New Chat/History support
        self.reset_session()

    def _initial_manager_history(self):
        return [
            {"role": "system", "content": self.config['manager']['system_message']}
        ] + [dict(item) for item in SYNTHETIC_MEMORY]

    def _initial_coder_history(self):
        return [
            {"role": "system", "content": self.config['coder']['system_message']}
        ]

    def _visible_manager_history(self, history=None):
        """Return history after the system prompt and synthetic training examples."""
        history = history if history is not None else self.manager_history
        start = 0
        if history and history[0].get("role") == "system":
            start = 1
        if history[start:start + len(SYNTHETIC_MEMORY)] == SYNTHETIC_MEMORY:
            start += len(SYNTHETIC_MEMORY)
        return history[start:]

    @staticmethod
    def _is_internal_user_message(content: str) -> bool:
        stripped = (content or "").strip()
        return stripped.startswith("[TOOL_RESULT:") or stripped.startswith("[SYSTEM]")

    def _first_real_user_message(self, history=None):
        for msg in self._visible_manager_history(history):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").strip()
            if content and not self._is_internal_user_message(content):
                return content
        return ""

    @staticmethod
    def _session_title_from_message(message: str) -> str:
        title = (message or "").strip()[:30].strip()
        if len((message or "").strip()) > 30:
            title += "..."
        return title

    def _is_synthetic_session_name(self, name: str) -> bool:
        synthetic_titles = {
            self._session_title_from_message(msg.get("content", ""))
            for msg in SYNTHETIC_MEMORY
            if msg.get("role") == "user"
        }
        return name in synthetic_titles

    def get_display_messages(self):
        """Messages the UI should show in chat history."""
        messages = []
        for msg in self._visible_manager_history():
            role = msg.get("role")
            content = msg.get("content", "").strip()
            if not content:
                continue
            if role == "user" and self._is_internal_user_message(content):
                continue
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
        return messages

    def has_real_messages(self):
        return bool(self._first_real_user_message())

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """Rename an existing session on disk."""
        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        filepath = os.path.join(sess_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['name'] = new_name
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            if session_id == self.session_id:
                self.session_name = new_name
            return True
        return False

    # ----------------------------------------------------------------
    # Cancellation
    # ----------------------------------------------------------------
    def cancel(self):
        """Called by UI to abort the current tool loop."""
        self._cancel_flag = True

    def _is_cancelled(self) -> bool:
        return self._cancel_flag

    def _save_config(self):
        """Persist config changes and refresh cached endpoint URLs."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        self.manager_url = self.config['manager']['url']
        self.coder_url = self.config['coder']['url']

    def _get_model_id(self, role: str) -> str:
        cfg_model = self.config[role]['model']
        if cfg_model == "auto":
            url = self.manager_url if role == "manager" else self.coder_url
            return self._detect_model(url)
        return cfg_model

    def _detect_models_list(self) -> list:
        """Fetch all available models from LM Studio."""
        try:
            r = requests.get(f"{self.manager_url}/models", timeout=3)
            if r.status_code == 200:
                data = r.json().get('data', [])
                return [m['id'] for m in data]
        except: pass
        return []

    def _detect_model(self, base_url: str) -> str:
        try:
            r = requests.get(f"{base_url}/models", timeout=5)
            r.raise_for_status()
            models = r.json().get('data', [])
            if models:
                return models[0]['id']
        except Exception:
            pass
        return "default"

    def _supports_vision(self, role: str) -> bool:
        return bool(self.config.get("capabilities", {}).get(role, {}).get("vision", False))

    @staticmethod
    def _is_image_path(path: str) -> bool:
        return os.path.splitext(path or "")[1].lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

    @staticmethod
    def _is_text_path(path: str) -> bool:
        return os.path.splitext(path or "")[1].lower() in {
            ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".jsonl",
            ".html", ".htm", ".css", ".xml", ".svg", ".yml", ".yaml", ".toml",
            ".ini", ".cfg", ".csv", ".sql", ".ps1", ".bat", ".cmd", ".sh"
        }

    def _attachment_summary(self, attachments) -> str:
        if not attachments:
            return ""
        lines = ["\n[ATTACHMENTS]"]
        for attachment in attachments:
            path = attachment.get("path", "")
            kind = "image" if self._is_image_path(path) else "file"
            lines.append(f"- {kind}: {path}")
            if kind == "file" and self._is_text_path(path) and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(12000)
                    truncated = " (truncated)" if os.path.getsize(path) > 12000 else ""
                    lines.append(f"[TEXT FILE CONTENT: {path}{truncated}]\n{content}")
                except Exception as e:
                    lines.append(f"[ERROR reading attached file {path}: {e}]")
        return "\n".join(lines)

    def _data_url_for_image(self, path: str) -> str:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _multimodal_content(self, text: str, attachments):
        content = [{"type": "text", "text": text}]
        for attachment in attachments or []:
            path = attachment.get("path", "")
            if self._is_image_path(path) and os.path.exists(path):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": self._data_url_for_image(path)}
                })
        return content

    def _format_user_input_with_attachments(self, user_input: str, attachments) -> str:
        return (user_input or "").strip() + self._attachment_summary(attachments)

    def send_to_manager(self, user_input: str, on_chat, on_tool_log, on_status,
                        on_coder_result=None, terminal_approve_fn=None,
                        write_approve_fn=None, attachments=None):
        """
        Send user input to the Manager with full tool loop.

        terminal_approve_fn(command: str) -> bool
        write_approve_fn(filepath: str, content: str) -> (bool, str)
        """
        if self._is_manager_running:
            on_tool_log("[WARNING] Manager is already processing.")
            return

        attachments = attachments or []
        user_input_for_history = self._format_user_input_with_attachments(user_input, attachments)
        has_images = any(self._is_image_path(a.get("path", "")) for a in attachments)
        if has_images and not self._supports_vision("manager"):
            self._handle_image_routing(
                user_input_for_history, attachments, on_chat, on_tool_log,
                on_status, on_coder_result
            )
            return

        self._is_manager_running = True
        self.manager_history.append({"role": "user", "content": user_input_for_history})
        self.save_session()
        self._cancel_flag = False
        self._terminal_approve_fn = terminal_approve_fn
        self._write_approve_fn = write_approve_fn
        first_request_attachments = attachments if has_images and self._supports_vision("manager") else []

        def run():
            nonlocal first_request_attachments
            current_session = self.session_id
            on_status("manager", "THINKING...")
            loop_count = 0
            call_tracker = {}  # Track duplicate calls: hash -> count

            while loop_count < self._max_tool_loops:
                if self._is_cancelled() or current_session != self.session_id:
                    on_tool_log("[STOPPED] Session changed or user cancelled.")
                    on_status("manager", "STOPPED")
                    return

                loop_count += 1
                on_tool_log(f"--- Loop {loop_count} ---")

                # 1. Call the Manager LLM
                try:
                    model_id = self._get_model_id("manager")
                    messages = self.manager_history
                    if first_request_attachments:
                        messages = list(self.manager_history)
                        messages[-1] = {
                            "role": "user",
                            "content": self._multimodal_content(user_input_for_history, first_request_attachments)
                        }
                        first_request_attachments = []
                    response = requests.post(
                        f"{self.manager_url}/chat/completions",
                        json={
                            "model": model_id,
                            "messages": messages,
                            "temperature": 0.1,
                            "top_p": 0.9,
                            "repetition_penalty": 1.15,
                            "max_tokens": self.config['manager'].get('max_tokens', 8192)
                        },
                        timeout=120
                    )
                    response.raise_for_status()
                    data = response.json()
                    raw_text = data['choices'][0]['message']['content']
                except Exception as e:
                    on_tool_log(f"[ERROR] Manager request failed: {e}")
                    on_status("manager", "ERROR")
                    return

                if self._is_cancelled() or current_session != self.session_id:
                    on_tool_log("[STOPPED] Session changed or user cancelled.")
                    on_status("manager", "STOPPED")
                    return

                # 2. Record in history
                self.manager_history.append({"role": "assistant", "content": raw_text})
                self.save_session()

                # 3. Parse sigils
                parsed = parse_sigils(raw_text)

                # 4. Display chat segments
                for segment in parsed.chat_segments:
                    on_chat("assistant", segment)

                # 5. No tools = done
                if not parsed.has_tools:
                    on_status("manager", "READY")
                    return

                # 6. Execute tools with LOOP DETECTION
                tool_results = []
                loop_detected = False

                if parsed.tool_calls:
                    on_status("manager", "WAITING FOR TOOLS")

                for block in parsed.tool_calls:
                    if self._is_cancelled() or current_session != self.session_id:
                        on_tool_log("[STOPPED] Session changed or user cancelled.")
                        on_status("manager", "STOPPED")
                        return

                    # --- LOOP DETECTION ---
                    call_hash = hashlib.md5(
                        f"{block.tool_name}:{block.raw_content}".encode()
                    ).hexdigest()

                    call_tracker[call_hash] = call_tracker.get(call_hash, 0) + 1

                    if call_tracker[call_hash] > self._max_duplicate_calls:
                        on_tool_log(f"[LOOP DETECTED] ~@{block.tool_name}@~ called multiple times with same args. STOPPING.")
                        loop_detected = True
                        break

                    on_tool_log(f"~@{block.tool_name}@~ invoked")
                    on_status("manager", f"RUNNING {block.tool_name.upper()}")
                    
                    result = self._execute_tool(
                        block,
                        on_tool_log, on_coder_result, on_status
                    )

                    if result == "[BLOCKED_BY_USER]":
                        tool_results.append(f"[TOOL_RESULT: {block.tool_name}]\nUser denied this command.")
                        on_tool_log(f"~@{block.tool_name}@~ BLOCKED by user. Aborting loop.")
                        on_status("manager", "READY")
                        self._is_manager_running = False
                        return  # Break entirely out of the run thread!
                    else:
                        tool_results.append(f"[TOOL_RESULT: {block.tool_name}]\n{result}")
                        on_tool_log(f"~@{block.tool_name}@~ completed")

                if loop_detected:
                    # Force the model to stop by injecting a stern message
                    self.manager_history.append({
                        "role": "user",
                        "content": "[SYSTEM] Loop detected. You are repeating the same command. STOP using tools and give the user a final text answer now."
                    })
                    # One last chance to respond with text only
                    continue

                # 7. Feed results back
                if tool_results:
                    feedback = "\n---\n".join(tool_results)
                    feedback += "\n\n[SYSTEM] Tool executed automatically. If the user's task is fully complete, reply ONLY with 'DONE' and say NOTHING else. If you just received code from the Coder, your VERY NEXT action MUST be to use the ~@write@~ tool to save it."
                    self.manager_history.append({"role": "user", "content": feedback})

            # Hit max loops
            on_tool_log(f"[WARNING] Max tool loops ({self._max_tool_loops}) reached. Stopping.")
            on_chat("assistant", "(I've reached my tool limit for this turn. Please give me a new instruction.)")
            if on_status:
                on_status("manager", "READY")
            
            # AI GENERATE NAME if still basic or snippet
            if not self.session_name_generated:
                 self._ai_generate_name()
            
            self.save_session()
            self._is_manager_running = False

        def safe_run():
            try:
                run()
            finally:
                self._is_manager_running = False

        threading.Thread(target=safe_run, daemon=True).start()

    def _handle_image_routing(self, user_input, attachments, on_chat, on_tool_log, on_status, on_coder_result=None):
        if self._is_manager_running:
            on_tool_log("[WARNING] Manager is already processing.")
            return
        self._is_manager_running = True
        self.manager_history.append({"role": "user", "content": user_input})
        self.save_session()

        def run():
            try:
                if not self._supports_vision("coder"):
                    msg = "I cannot process the attached image because neither the Manager nor the Coder is configured for image input."
                    self.manager_history.append({"role": "assistant", "content": msg})
                    self.save_session()
                    on_chat("assistant", msg)
                    on_status("manager", "READY")
                    return

                on_tool_log("[ROUTER] Manager has no vision. Delegating image task to Coder.")
                result = self._delegate_to_coder(user_input, on_tool_log, on_coder_result, on_status, attachments=attachments)
                assistant_text = result.replace("[CODER_RESPONSE]\n", "", 1)
                self.manager_history.append({"role": "assistant", "content": assistant_text})
                self.save_session()
                on_chat("assistant", assistant_text)
                on_status("manager", "READY")
            finally:
                self._is_manager_running = False

        threading.Thread(target=run, daemon=True).start()

    # ----------------------------------------------------------------
    # Tool Execution
    # ----------------------------------------------------------------
    def _execute_tool(self, block, on_tool_log, on_coder_result=None, on_status=None) -> str:
        tool_name = block.tool_name
        try:
            if tool_name == "read":
                filepath = parse_read_block(block)
                on_tool_log(f"  Reading: {filepath}")
                return self.tools.read(filepath)

            elif tool_name == "write":
                filepath, content = parse_write_block(block)
                on_tool_log(f"  Writing: {filepath}")

                # --- WRITE APPROVAL ---
                if self._write_approve_fn:
                    approved, edited_content = self._write_approve_fn(filepath, content)
                    if not approved:
                        return "[BLOCKED_BY_USER] Write denied."
                    content = edited_content

                return self.tools.write(filepath, content)

            elif tool_name == "replace":
                filepath, old, new = parse_replace_block(block)
                on_tool_log(f"  Replacing snippet in: {filepath}")

                if self._write_approve_fn:
                    clean_path = filepath.strip().strip('"').strip("'")
                    if not os.path.exists(clean_path):
                        return f"[ERROR] File not found: {filepath}"
                    with open(clean_path, 'r', encoding='utf-8', errors='replace') as f:
                        current = f.read()
                    count = current.count(old)
                    if count == 0:
                        return "[ERROR] Old snippet was not found. Read the file first and use an exact snippet."
                    if count > 1:
                        return f"[ERROR] Old snippet matched {count} places. Use a larger unique snippet."
                    updated = current.replace(old, new, 1)
                    approved, edited_content = self._write_approve_fn(filepath, updated)
                    if not approved:
                        return "[BLOCKED_BY_USER] Write denied."
                    return self.tools.write(filepath, edited_content)

                return self.tools.replace(filepath, old, new)

            elif tool_name == "terminal":
                command = parse_terminal_block(block)
                on_tool_log(f"  Command: {command}")

                # --- TERMINAL APPROVAL ---
                if self._terminal_approve_fn:
                    approved = self._terminal_approve_fn(command)
                    if not approved:
                        return "[BLOCKED_BY_USER]"

                return self.tools.terminal(command)

            elif tool_name == "explorer":
                path = parse_explorer_block(block)
                on_tool_log(f"  Exploring: {path}")
                return self.tools.explorer(path)

            elif tool_name == "delegate":
                task = parse_delegate_block(block)
                on_tool_log(f"  Delegating to Expert Coder...")
                return self._delegate_to_coder(task, on_tool_log, on_coder_result, on_status)

            elif tool_name == "search":
                query = block.raw_content.strip()
                search_cfg = self.config.get("search", {})
                provider = search_cfg.get("provider", "duckduckgo")
                on_tool_log(f"  Searching ({provider}): {query}")
                if provider == "brave":
                    api_key = search_cfg.get("brave_api_key") or self.config.get("brave_api_key", "")
                    return self.tools.web_search(query, api_key)
                if provider == "google":
                    return self.tools.google_search(
                        query,
                        search_cfg.get("google_api_key", ""),
                        search_cfg.get("google_cx", "")
                    )
                return self.tools.duck_search(query)

            elif tool_name == "ddg":
                query = block.raw_content.strip()
                on_tool_log(f"  DDG Searching: {query}")
                return self.tools.duck_search(query)

            else:
                return f"[ERROR] Unknown tool: {tool_name}"

        except Exception as e:
            return f"[ERROR] Tool '{tool_name}' crashed: {e}"

    # ----------------------------------------------------------------
    # Coder Delegation
    # ----------------------------------------------------------------
    def _delegate_to_coder(self, task: str, on_tool_log, on_coder_result=None, on_status=None, attachments=None) -> str:
        attachments = attachments or []
        content = self._multimodal_content(task, attachments) if attachments and self._supports_vision("coder") else task
        self.coder_history.append({"role": "user", "content": content})
        try:
            if on_status:
                on_status("coder", "WRITING CODE...")
                on_status("manager", "WAITING FOR CODER")

            model_id = self._get_model_id("coder")
            on_tool_log(f"  Coder model: {model_id}")
            response = requests.post(
                f"{self.coder_url}/chat/completions",
                json={
                    "model": model_id,
                    "messages": self.coder_history,
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "repetition_penalty": 1.15,
                    "max_tokens": self.config['coder'].get('max_tokens', 8192)
                },
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            content = data['choices'][0]['message']['content']
            self.coder_history.append({"role": "assistant", "content": content})
            
            if on_status:
                on_status("coder", "STANDBY")
                on_status("manager", "PROCESSING CODER RESULT")

            if on_coder_result:
                on_coder_result(content)
            return f"[CODER_RESPONSE]\n{content}"
        except Exception as e:
            return f"[ERROR] Coder request failed: {e}"

    # ----------------------------------------------------------------
    # Session Management
    # ----------------------------------------------------------------
    def _ensure_session_dir(self):
        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        if not os.path.exists(sess_dir):
            os.makedirs(sess_dir)

    def _session_filepath(self, session_id=None):
        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        return os.path.join(sess_dir, f"{session_id or self.session_id}.json")

    @staticmethod
    def _created_at_from_id(session_id: str) -> float:
        try:
            raw = int(session_id)
            return raw / 1000 if raw > 10_000_000_000 else float(raw)
        except (TypeError, ValueError):
            return time.time()

    def _existing_created_at(self, session_id=None):
        filepath = self._session_filepath(session_id)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get("created_at") or data.get("timestamp") or self._created_at_from_id(data.get("id"))
            except Exception:
                pass
        return self._created_at_from_id(session_id or self.session_id)

    def reset_session(self, save_placeholder=False):
        """Start a fresh session with a new ID."""
        self.session_id = str(int(time.time() * 1000))
        self.session_name = "New Chat"
        self.session_name_generated = False
        self.manager_history = self._initial_manager_history()
        self.coder_history = self._initial_coder_history()
        self._cancel_flag = False
        if save_placeholder:
            self.save_session(allow_empty=True)

    def save_session(self, allow_empty=False):
        """Persist current histories to disk."""
        first_msg = self._first_real_user_message()
        if not first_msg and not allow_empty:
            return False

        # Auto-name based on first user message if still "New Chat"
        if first_msg and (self.session_name == "New Chat" or self._is_synthetic_session_name(self.session_name)):
            self.session_name = self._session_title_from_message(first_msg)
        
        self._ensure_session_dir()
        filepath = self._session_filepath()
        created_at = self._existing_created_at()
        data = {
            "id": self.session_id,
            "name": self.session_name,
            "manager_history": self.manager_history,
            "coder_history": self.coder_history,
            "created_at": created_at,
            "updated_at": time.time(),
            "timestamp": created_at,
            "is_placeholder": not bool(first_msg)
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True


    def load_session(self, session_id: str):
        """Reload a session from disk."""
        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        filepath = os.path.join(sess_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.session_id = data['id']
                self.session_name = data.get('name', "Untitled")
                self.manager_history = data['manager_history']
                self.coder_history = data['coder_history']
            return True
        return False

    def _ai_generate_name(self):
        """Hidden LLM call to get a 3-5 word professional title for the session."""
        try:
            first_msg = self._first_real_user_message()
            if not first_msg: return
            
            prompt = f"Summarize this AI session topic into exactly 3-5 words. Use NO quotes or special chars. Topic: {first_msg}"
            
            model_id = self._get_model_id("manager")
            response = requests.post(
                f"{self.manager_url}/chat/completions",
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 15
                },
                timeout=10
            )
            if response.status_code == 200:
                name = response.json()['choices'][0]['message']['content'].strip()
                if name:
                    # Clean up quotes if model added them
                    name = name.replace('"', '').replace("'", "").strip()
                    self.session_name = name
                    self.session_name_generated = True
                    self.save_session()
        except:
            pass # Fallback to snippet remains

    def list_sessions(self):
        """Return list of session metadata sorted by time."""
        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        sessions = []
        if not os.path.exists(sess_dir): return []
        for f in os.listdir(sess_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(sess_dir, f), 'r', encoding='utf-8') as s:
                        data = json.load(s)
                        first_msg = self._first_real_user_message(data.get('manager_history', []))
                        is_placeholder = data.get("is_placeholder") or data.get("name") == "New Chat"
                        if not first_msg and not is_placeholder:
                            continue
                        name = data.get('name') or "New Chat"
                        if first_msg and (name == "New Chat" or self._is_synthetic_session_name(name)):
                            name = self._session_title_from_message(first_msg)
                        created_at = data.get("created_at") or data.get("timestamp") or self._created_at_from_id(data.get("id"))
                        sessions.append({
                            "id": data['id'],
                            "name": name,
                            "time": created_at
                        })
                except: continue
        return sorted(sessions, key=lambda x: x['time'], reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session file from disk. Returns True if deleted."""
        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        filepath = os.path.join(sess_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            # If we deleted the active session, reset to a new one
            if session_id == self.session_id:
                self.reset_session(save_placeholder=True)
            return True
        return False
