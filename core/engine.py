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
from datetime import datetime

from core.sigil_parser import (
    parse_sigils, parse_write_block, parse_read_block,
    parse_terminal_block, parse_explorer_block, parse_delegate_block
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

        self.manager_history = [
            {"role": "system", "content": self.config['manager']['system_message']}
        ] + SYNTHETIC_MEMORY
        
        self.coder_history = [
            {"role": "system", "content": self.config['coder']['system_message']}
        ]

        self.tools = Tools()
        self._max_tool_loops = 50         # Safety: max consecutive tool-use rounds
        self._max_duplicate_calls = 1     # If same tool+args called this many times, STOP
        self._cancel_flag = False         # UI can set this to abort
        self._is_manager_running = False  # Track if manager is busy
        self._write_approve_fn = None     # Callback for write approval
        
        # New Chat/History support
        self.session_id = str(int(time.time()))
        self.session_name = "New Chat"
        self._ensure_session_dir()

    # ----------------------------------------------------------------
    # Cancellation
    # ----------------------------------------------------------------
    def cancel(self):
        """Called by UI to abort the current tool loop."""
        self._cancel_flag = True

    def _is_cancelled(self) -> bool:
        return self._cancel_flag

    # ----------------------------------------------------------------
    # Auto-detect model from LM Studio
    # ----------------------------------------------------------------
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

    def _get_model_id(self, role: str) -> str:
        cfg_model = self.config[role]['model']
        if cfg_model == "auto":
            url = self.manager_url if role == "manager" else self.coder_url
            return self._detect_model(url)
        return cfg_model

    # ----------------------------------------------------------------
    # Manager Communication
    # ----------------------------------------------------------------
    def send_to_manager(self, user_input: str, on_chat, on_tool_log, on_status,
                        on_coder_result=None, terminal_approve_fn=None,
                        write_approve_fn=None):
        """
        Send user input to the Manager with full tool loop.

        terminal_approve_fn(command: str) -> bool
        write_approve_fn(filepath: str, content: str) -> (bool, str)
        """
        if self._is_manager_running:
            on_tool_log("[WARNING] Manager is already processing.")
            return

        self._is_manager_running = True
        self.manager_history.append({"role": "user", "content": user_input})
        self._cancel_flag = False
        self._terminal_approve_fn = terminal_approve_fn
        self._write_approve_fn = write_approve_fn

        def run():
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
                    response = requests.post(
                        f"{self.manager_url}/chat/completions",
                        json={
                            "model": model_id,
                            "messages": self.manager_history,
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
                    result = self._execute_tool(
                        block,
                        on_tool_log, on_coder_result
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
            on_status("manager", "READY")
            self._is_manager_running = False

        def safe_run():
            try:
                run()
            finally:
                self._is_manager_running = False

        threading.Thread(target=safe_run, daemon=True).start()

    # ----------------------------------------------------------------
    # Tool Execution
    # ----------------------------------------------------------------
    def _execute_tool(self, block, on_tool_log, on_coder_result=None) -> str:
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
                return self._delegate_to_coder(task, on_tool_log, on_coder_result)

            elif tool_name == "search":
                query = block.raw_content.strip()
                on_tool_log(f"  Searching: {query}")
                api_key = self.config.get("brave_api_key", "")
                return self.tools.web_search(query, api_key)

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
    def _delegate_to_coder(self, task: str, on_tool_log, on_coder_result=None) -> str:
        self.coder_history.append({"role": "user", "content": task})
        try:
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

    def reset_session(self):
        """Start a fresh session with a new ID."""
        self.session_id = str(int(time.time()))
        self.session_name = "New Chat"
        self.manager_history = [
            {"role": "system", "content": self.config['manager']['system_message']}
        ] + SYNTHETIC_MEMORY
        self.coder_history = [
            {"role": "system", "content": self.config['coder']['system_message']}
        ]
        self._cancel_flag = False

    def save_session(self):
        """Persist current histories to disk."""
        # Auto-name based on first user message if still "New Chat"
        if self.session_name == "New Chat":
            for msg in self.manager_history:
                if msg['role'] == 'user':
                    # Only name if there's actual user content
                    content = msg['content'].strip()
                    if content:
                        self.session_name = content[:40].strip() + ("..." if len(content) > 40 else "")
                        break

        sess_dir = os.path.join(os.path.dirname(self.config_path), "sessions")
        filepath = os.path.join(sess_dir, f"{self.session_id}.json")
        data = {
            "id": self.session_id,
            "name": self.session_name,
            "manager_history": self.manager_history,
            "coder_history": self.coder_history,
            "timestamp": time.time()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


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
                        sessions.append({
                            "id": data['id'],
                            "name": data.get('name', 'Untitled'),
                            "time": data.get('timestamp', 0)
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
                self.reset_session()
            return True
        return False


