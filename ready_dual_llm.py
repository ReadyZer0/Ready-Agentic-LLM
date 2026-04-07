"""
Ready Dual LLM ⚡ - Strategic AI Orchestration Console
v2: Inline approvals, canvas pane, auto-approve toggle
"""

import customtkinter as ctk
import os
import sys
import threading
import webbrowser
import json
import subprocess
from datetime import datetime
from tkinter import messagebox, filedialog
from PIL import Image, ImageDraw, ImageTk

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_for_filename, get_lexer_by_name
    from pygments.formatter import Formatter
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False

class TkinterFormatter(Formatter):
    """Custom Pygments formatter for Tkinter Text tags."""
    def __init__(self, **options):
        super().__init__(**options)
        self.tag_map = {
            'Token.Keyword': '#ff79c6',
            'Token.Name.Function': '#50fa7b',
            'Token.Name.Class': '#50fa7b',
            'Token.String': '#f1fa8c',
            'Token.Comment': '#6272a4',
            'Token.Operator': '#ff79c6',
            'Token.Number': '#bd93f9',
            'Token.Name.Builtin': '#8be9fd',
        }

    def format(self, tokensource, outfile):
        return list(tokensource)

# Ensure imports work from any CWD
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.engine import Engine

# Appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ApprovalWidget(ctk.CTkFrame):
    """
    Inline approval widget that replaces Windows popups.
    Shows the command/content, lets user edit it, then approve or deny.
    """
    def __init__(self, master, title: str, content: str, on_result, editable=True, filepath=None, **kwargs):
        super().__init__(master, fg_color="#1e293b", corner_radius=8, border_width=2,
                         border_color="#f59e0b", **kwargs)

        self._result_event = threading.Event()
        self._approved = False
        self._edited_content = content
        self._on_result = on_result
        self._filepath = filepath

        # Title bar
        title_frame = ctk.CTkFrame(self, fg_color="#f59e0b", corner_radius=0, height=30)
        title_frame.pack(fill="x")
        ctk.CTkLabel(title_frame, text=f"⚠ {title}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#000000").pack(side="left", padx=10, pady=4)

        if filepath:
             ctk.CTkLabel(title_frame, text=os.path.basename(filepath),
                          font=ctk.CTkFont(size=11),
                          text_color="#334155").pack(side="right", padx=10)

        # Editable content area
        self.text_area = ctk.CTkTextbox(self, height=180,
                                         font=ctk.CTkFont(family="Consolas", size=11),
                                         fg_color="#0f172a", text_color="#e2e8f0",
                                         wrap="none")
        self.text_area.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.text_area.insert("0.0", content)
        if not editable:
            self.text_area.configure(state="disabled")

        if HAS_PYGMENTS:
            self._apply_highlighting(content)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkButton(btn_frame, text="✓ Approve", width=100, height=32,
                      fg_color="#10b981", hover_color="#059669",
                      font=ctk.CTkFont(weight="bold"),
                      command=self._approve).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="✗ Deny", width=100, height=32,
                      fg_color="#ef4444", hover_color="#dc2626",
                      font=ctk.CTkFont(weight="bold"),
                      command=self._deny).pack(side="left")

        if filepath:
            ctk.CTkButton(btn_frame, text="📂 Open", width=70, height=32,
                          fg_color="#334155", hover_color="#475569",
                          command=self._open_file).pack(side="left", padx=8)

        if editable:
            ctk.CTkLabel(btn_frame, text="(edit before approving)",
                         text_color="#6c757d", font=ctk.CTkFont(size=10)).pack(side="right")

    def _apply_highlighting(self, content):
        lexer = None
        if self._filepath:
            try: lexer = get_lexer_for_filename(self._filepath)
            except: pass
        if not lexer:
            lexer = get_lexer_by_name("python") # default

        formatter = TkinterFormatter()
        tokens = formatter.format(lexer.get_tokens(content), None)

        # Apply tags
        for tag, color in formatter.tag_map.items():
            self.text_area._textbox.tag_configure(tag, foreground=color)

        idx = "1.0"
        for ttype, value in tokens:
            tname = str(ttype)
            start = idx
            lines = value.split("\n")
            if len(lines) > 1:
                row, col = map(int, idx.split("."))
                end = f"{row + len(lines) - 1}.{len(lines[-1])}"
            else:
                row, col = map(int, idx.split("."))
                end = f"{row}.{col + len(value)}"

            if tname in formatter.tag_map:
                self.text_area._textbox.tag_add(tname, start, end)
            idx = end

    def _open_file(self):
        if self._filepath and os.path.exists(self._filepath):
            os.startfile(os.path.dirname(self._filepath))
            os.startfile(self._filepath)

    def _approve(self):
        self._edited_content = self.text_area.get("0.0", "end").strip()
        self._approved = True
        self._on_result(True, self._edited_content)
        self.destroy()

    def _deny(self):
        self._approved = False
        self._on_result(False, "")
        self.destroy()


class CanvasPane(ctk.CTkFrame):
    """
    Canvas/Artifact pane for previewing files, code, and results.
    Replaces the right side when there's content to display.
    """
    def __init__(self, master, on_close, **kwargs):
        super().__init__(master, corner_radius=12, fg_color="#0f0f23", **kwargs)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header with close button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(8, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(header, text="CANVAS",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#818cf8")
        self.title_label.grid(row=0, column=0, sticky="w", padx=8)

        ctk.CTkButton(header, text="✕", width=30, height=24,
                      fg_color="#374151", hover_color="#ef4444",
                      command=on_close).grid(row=0, column=1)

        # Content area
        self.content = ctk.CTkTextbox(self,
                                       font=ctk.CTkFont(family="Consolas", size=11),
                                       fg_color="#0a0a1a",
                                       text_color="#c4b5fd",
                                       wrap="word", border_width=0)
        self.content.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")

        # File path label
        self.path_label = ctk.CTkLabel(self, text="", text_color="#6c757d",
                                        font=ctk.CTkFont(size=10))
        self.path_label.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

    def show_content(self, title: str, content: str, filepath: str = ""):
        self.title_label.configure(text=f"CANVAS: {title}")
        self.content.configure(state="normal")
        self.content.delete("0.0", "end")
        self.content.insert("0.0", content)
        self.content.configure(state="disabled")
        self.path_label.configure(text=filepath)


class ReadyDualLLM(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Engine
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        self.engine = Engine(config_path)

        # Settings
        self.auto_approve = self.engine.config.get("auto_approve", False)

        # Window
        self.title("⚡ ReadyAI Agent")
        self.geometry("1200x750")
        self.minsize(900, 550)

        # Layout
        self.grid_columnconfigure(0, weight=0, minsize=180)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_chat_pane()
        self._build_console_pane()
        self._build_status_bar()

        self.canvas_pane = None  # Created on demand
        self.after(100, self.user_input.focus)

    def create_agent_logo(self, size=256):
        """Programmatically generates the ReadyAI Agent logo."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Scale factors
        s = size / 256
        
        # Draw Chip pins (silver)
        pin_color = "#94a3b8"
        for i in range(5):
            # top
            draw.rectangle([s*(60 + i*35), s*20, s*(75 + i*35), s*45], fill=pin_color)
            # bottom
            draw.rectangle([s*(60 + i*35), s*211, s*(75 + i*35), s*236], fill=pin_color)
            # left
            draw.rectangle([s*20, s*(60 + i*35), s*45, s*(75 + i*35)], fill=pin_color)
            # right
            draw.rectangle([s*211, s*(60 + i*35), s*236, s*(75 + i*35)], fill=pin_color)

        # Draw main chip (Dark Slate)
        chip_color = "#1e293b"
        draw.rounded_rectangle([s*40, s*40, s*216, s*216], radius=20*s, fill=chip_color, outline="#334155", width=int(2*s))
        
        # Draw Lightning Bolt (Yellow)
        bolt_color = "#facc15"
        bolt_coords = [
            (s*140, s*70), (s*90, s*140), (s*125, s*140),
            (s*110, s*190), (s*165, s*110), (s*130, s*110),
            (s*140, s*70)
        ]
        draw.polygon(bolt_coords, fill=bolt_color, outline="#854d0e", width=int(s))
        
        return img

    # ============================================================
    # SIDEBAR
    # ============================================================
    def _build_sidebar(self):
        # 1. Update window icon (coded logo)
        try:
            icon_img = self.create_agent_logo(size=32)
            self.logo_icon_tk = ImageTk.PhotoImage(icon_img) # Keep reference to avoid GC
            self.tk.call('wm', 'iconphoto', self._w, self.logo_icon_tk)
        except Exception as e:
            print(f"Icon error: {e}")

        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color="#1a1a2e")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        # Logo generated via code
        img = self.create_agent_logo(size=512) # high res for scaling
        self.logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
        ctk.CTkLabel(self.sidebar, text="", image=self.logo_img).grid(row=0, column=0, padx=20, pady=(25, 0))
        
        ctk.CTkLabel(self.sidebar, text="ReadyAI Agent",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#e94560").grid(row=1, column=0, padx=20, pady=(5, 5))

        ctk.CTkLabel(self.sidebar, text="Strategic Console",
                     font=ctk.CTkFont(size=10),
                     text_color="#6c757d").grid(row=2, column=0, padx=20, pady=(0, 15))

        ctk.CTkButton(self.sidebar, text="⟳  New Session", command=self.new_session,
                      fg_color="#16213e", hover_color="#0f3460",
                      anchor="w").grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="⚙  Settings", command=self.open_settings,
                      fg_color="#16213e", hover_color="#0f3460",
                      anchor="w").grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="📋  Tool Guide", command=self.show_tool_guide,
                      fg_color="#16213e", hover_color="#0f3460",
                      anchor="w").grid(row=5, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="🏋️  Train Agent", command=self.open_training_ui,
                      fg_color="#0f766e", hover_color="#0c4a6e",
                      anchor="w").grid(row=6, column=0, padx=15, pady=5, sticky="ew")

        # Theme
        ctk.CTkLabel(self.sidebar, text="Theme", text_color="#6c757d",
                     font=ctk.CTkFont(size=10)).grid(row=8, column=0, padx=15, pady=(10, 0))
        ctk.CTkOptionMenu(self.sidebar, values=["Dark", "Light", "System"],
                          command=lambda v: ctk.set_appearance_mode(v),
                          width=140).grid(row=9, column=0, padx=15, pady=(5, 10))

        # Credit
        ctk.CTkButton(self.sidebar, text="Created by Ali Dheyaa",
                      font=ctk.CTkFont(size=10), fg_color="transparent",
                      hover_color="#16213e", text_color="#6c757d", height=20,
                      command=lambda: webbrowser.open("https://www.linkedin.com/in/ali-dheyaa-abdulwahab-6bbbb1239/")
                      ).grid(row=8, column=0, padx=15, pady=(5, 12))

    # ============================================================
    # CHAT PANE
    # ============================================================
    def _build_chat_pane(self):
        self.chat_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#0f0f23")
        self.chat_frame.grid(row=0, column=1, padx=(15, 8), pady=15, sticky="nsew")
        self.chat_frame.grid_rowconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.chat_frame, text="MANAGER CHAT",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#e94560").grid(row=0, column=0, padx=18, pady=(12, 5), sticky="w")

        self.chat_display = ctk.CTkTextbox(self.chat_frame, wrap="word",
                                            font=ctk.CTkFont(family="Segoe UI", size=12),
                                            fg_color="#0a0a1a", text_color="#e0e0e0",
                                            border_width=0)
        self.chat_display.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.chat_display.configure(state="disabled")

        # Approval area (between chat and input)
        self.approval_container = ctk.CTkFrame(self.chat_frame, fg_color="transparent", height=0)
        self.approval_container.grid(row=2, column=0, padx=10, pady=0, sticky="ew")

        # Input
        input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        input_frame.grid(row=3, column=0, padx=10, pady=(0, 12), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.user_input = ctk.CTkEntry(input_frame,
                                        placeholder_text="Talk to the Manager...",
                                        font=ctk.CTkFont(size=12), height=38)
        self.user_input.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.user_input.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(input_frame, text="SEND", width=75, height=38,
                                       font=ctk.CTkFont(weight="bold"),
                                       fg_color="#e94560", hover_color="#c81e45",
                                       command=self.send_message)
        self.send_btn.grid(row=0, column=1, padx=(0, 4))

        self.stop_btn = ctk.CTkButton(input_frame, text="⏹", width=40, height=38,
                                       font=ctk.CTkFont(size=16),
                                       fg_color="#6c757d", hover_color="#ef4444",
                                       command=self.stop_generation)
        self.stop_btn.grid(row=0, column=2)

    # ============================================================
    # CONSOLE PANE
    # ============================================================
    def _build_console_pane(self):
        self.console_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#0f0f23")
        self.console_frame.grid(row=0, column=2, padx=(8, 15), pady=15, sticky="nsew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.console_frame, text="TOOL CONSOLE",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#10b981").grid(row=0, column=0, padx=18, pady=(12, 5), sticky="w")

        self.console_display = ctk.CTkTextbox(self.console_frame,
                                               font=ctk.CTkFont(family="Consolas", size=11),
                                               fg_color="#0a0a1a", text_color="#10b981",
                                               wrap="word", border_width=0)
        self.console_display.grid(row=1, column=0, padx=10, pady=(5, 12), sticky="nsew")
        self.console_display.configure(state="disabled")

    # ============================================================
    # STATUS BAR
    # ============================================================
    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="#1a1a2e")
        self.status_bar.grid(row=1, column=0, columnspan=3, sticky="ew")

        self.manager_status_label = ctk.CTkLabel(self.status_bar,
            text="● MANAGER: READY", font=ctk.CTkFont(size=10), text_color="#10b981")
        self.manager_status_label.pack(side="left", padx=20)

        self.coder_status_label = ctk.CTkLabel(self.status_bar,
            text="● CODER: STANDBY", font=ctk.CTkFont(size=10), text_color="#6c757d")
        self.coder_status_label.pack(side="left", padx=20)

        # Auto-approve indicator
        self.auto_label = ctk.CTkLabel(self.status_bar,
            text="AUTO-APPROVE: ON" if self.auto_approve else "AUTO-APPROVE: OFF",
            font=ctk.CTkFont(size=10),
            text_color="#fbbf24" if self.auto_approve else "#6c757d")
        self.auto_label.pack(side="right", padx=20)

    # ============================================================
    # CANVAS
    # ============================================================
    def open_canvas(self, title: str, content: str, filepath: str = ""):
        if self.canvas_pane:
            self.canvas_pane.show_content(title, content, filepath)
            return
        # Hide console, show canvas in its place
        self.console_frame.grid_forget()
        self.canvas_pane = CanvasPane(self, on_close=self.close_canvas)
        self.canvas_pane.grid(row=0, column=2, padx=(8, 15), pady=15, sticky="nsew")
        self.canvas_pane.show_content(title, content, filepath)

    def close_canvas(self):
        if self.canvas_pane:
            self.canvas_pane.destroy()
            self.canvas_pane = None
        self.console_frame.grid(row=0, column=2, padx=(8, 15), pady=15, sticky="nsew")

    # ============================================================
    # UI HELPERS (Thread-safe)
    # ============================================================
    def _log_chat(self, role: str, text: str):
        def do():
            prefix = "YOU" if role == "user" else "MANAGER"
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"{prefix}:\n")
            self.chat_display.insert("end", f"{text}\n\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")
        self.after(0, do)

    def _log_console(self, text: str):
        def do():
            ts = datetime.now().strftime("%H:%M:%S")
            self.console_display.configure(state="normal")
            self.console_display.insert("end", f"[{ts}] {text}\n")
            self.console_display.see("end")
            self.console_display.configure(state="disabled")
        self.after(0, do)

    def _set_status(self, role: str, state: str):
        def do():
            label = self.manager_status_label if role == "manager" else self.coder_status_label
            color = "#10b981" if "READY" in state else "#fbbf24" if "THINK" in state else "#ef4444" if "ERROR" in state else "#f97316"
            label.configure(text=f"● {role.upper()}: {state}", text_color=color)
        self.after(0, do)

    # ============================================================
    # INLINE APPROVAL (replaces Windows popups)
    # ============================================================
    def _request_approval(self, title: str, content: str, editable: bool = True, filepath=None) -> tuple:
        """
        Shows inline approval widget. Blocks engine thread until user responds.
        Returns (approved: bool, edited_content: str)
        """
        if self.auto_approve:
            return True, content

        result_event = threading.Event()
        result_data = [False, content]

        def on_result(approved, edited):
            result_data[0] = approved
            result_data[1] = edited
            result_event.set()

        def show():
            widget = ApprovalWidget(
                self.approval_container,
                title=title,
                content=content,
                on_result=on_result,
                editable=editable,
                filepath=filepath
            )
            widget.pack(fill="x", pady=(5, 5))

        self.after(0, show)
        result_event.wait(timeout=120)
        return result_data[0], result_data[1]

    def _approve_terminal(self, command: str) -> bool:
        """Terminal approval callback for the engine."""
        approved, edited = self._request_approval(
            "TERMINAL COMMAND", command, editable=True
        )
        return approved

    def _approve_write(self, filepath: str, content: str) -> tuple:
        """Write approval callback. Returns (approved, edited_content)."""
        approved, edited = self._request_approval(
            "FILE WRITE REQUEST", content, editable=True, filepath=filepath
        )
        return approved, edited

    # ============================================================
    # ACTIONS
    # ============================================================
    def send_message(self):
        msg = self.user_input.get().strip()
        if not msg:
            return

        self.user_input.delete(0, "end")
        self._log_chat("user", msg)
        self._log_console("Manager processing...")
        self.send_btn.configure(state="disabled")
        self.stop_btn.configure(fg_color="#ef4444")

        self.engine.send_to_manager(
            user_input=msg,
            on_chat=lambda role, text: self._log_chat(role, text),
            on_tool_log=lambda text: self._log_console(text),
            on_status=lambda role, state: self._update_status_and_buttons(role, state),
            on_coder_result=lambda text: self.after(0, lambda: self.open_canvas("Coder Response", text)),
            terminal_approve_fn=self._approve_terminal,
            write_approve_fn=self._approve_write
        )

    def _update_status_and_buttons(self, role, state):
        self._set_status(role, state)
        if state in ("READY", "ERROR", "STOPPED"):
            self.after(0, lambda: self.send_btn.configure(state="normal"))
            self.after(0, lambda: self.stop_btn.configure(fg_color="#6c757d"))

    def stop_generation(self):
        self.engine.cancel()
        self._log_console("[USER] Stop requested.")
        self._set_status("manager", "STOPPING...")

    def new_session(self):
        self.engine.reset_session()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        self.chat_display.configure(state="disabled")
        self._log_console("Session reset.")

    # ============================================================
    # SETTINGS
    # ============================================================
    def open_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚡ Settings")
        dialog.geometry("520x600")
        dialog.transient(self)
        dialog.grab_set()

        scroll = ctk.CTkScrollableFrame(dialog, width=480, height=500)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        def add_field(parent, label_text, default_val, show=""):
            ctk.CTkLabel(parent, text=label_text,
                         font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(12, 3), anchor="w")
            entry = ctk.CTkEntry(parent, width=440, show=show if show else None)
            entry.insert(0, default_val)
            entry.pack(padx=10)
            return entry

        ctk.CTkLabel(scroll, text="Both URLs can be the same for single-model mode",
                     text_color="#6c757d", font=ctk.CTkFont(size=11)).pack(pady=(5, 0))

        mgr_url = add_field(scroll, "Manager API URL:", self.engine.config['manager']['url'])
        mgr_model = add_field(scroll, "Manager Model (or 'auto'):", self.engine.config['manager']['model'])
        coder_url = add_field(scroll, "Coder API URL:", self.engine.config['coder']['url'])
        coder_model = add_field(scroll, "Coder Model (or 'auto'):", self.engine.config['coder']['model'])

        ctk.CTkLabel(scroll, text="━━━━━━━━ Web Search ━━━━━━━━",
                     text_color="#6c757d").pack(pady=(15, 0))
        brave_key = add_field(scroll, "Brave Search API Key:", self.engine.config.get('brave_api_key', ''), show="•")

        ctk.CTkLabel(scroll, text="━━━━━━━━ Safety ━━━━━━━━",
                     text_color="#6c757d").pack(pady=(15, 0))

        auto_var = ctk.BooleanVar(value=self.auto_approve)
        auto_switch_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        auto_switch_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(auto_switch_frame, text="Auto-Approve All Actions:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkSwitch(auto_switch_frame, text="", variable=auto_var,
                      onvalue=True, offvalue=False).pack(side="right", padx=10)

        ctk.CTkLabel(scroll, text="When ON, terminal commands and file writes execute\nwithout asking. Use with caution!",
                     text_color="#ef4444", font=ctk.CTkFont(size=10)).pack(padx=10, anchor="w")

        def save():
            self.engine.config['manager']['url'] = mgr_url.get()
            self.engine.config['manager']['model'] = mgr_model.get()
            self.engine.config['coder']['url'] = coder_url.get()
            self.engine.config['coder']['model'] = coder_model.get()
            self.engine.config['brave_api_key'] = brave_key.get()
            self.engine.config['auto_approve'] = auto_var.get()
            self.engine.manager_url = mgr_url.get()
            self.engine.coder_url = coder_url.get()
            self.auto_approve = auto_var.get()
            # Update status bar indicator
            self.auto_label.configure(
                text="AUTO-APPROVE: ON" if self.auto_approve else "AUTO-APPROVE: OFF",
                text_color="#fbbf24" if self.auto_approve else "#6c757d"
            )
            cfg_path = os.path.join(SCRIPT_DIR, "config.json")
            with open(cfg_path, 'w') as f:
                json.dump(self.engine.config, f, indent=2)
            self._log_console("Settings saved.")
            dialog.destroy()

        ctk.CTkButton(dialog, text="Save & Apply", fg_color="#e94560",
                      hover_color="#c81e45", command=save).pack(pady=15)

    def show_tool_guide(self):
        guide = (
            "XML TOOL PROTOCOL\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            '<tool name="read">filepath</tool>\n  → Reads a file\n\n'
            '<tool name="write" path="filepath">\ncontent\n</tool>\n  → Writes to file (APPROVAL REQUIRED)\n\n'
            '<tool name="terminal">command</tool>\n  → Runs command (APPROVAL REQUIRED)\n\n'
            '<tool name="explorer" path="C:\\"> </tool>\n  → Lists directory\n\n'
            '<tool name="search">query</tool>\n  → Web search (Brave)\n\n'
            '<tool name="delegate">task</tool>\n  → Send to Expert Coder\n'
        )
        self._log_console(guide)

    # ============================================================
    # TRAINING UI
    # ============================================================
    def open_training_ui(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("🏋️ Train Agent (LoRA & GGUF)")
        dialog.geometry("540x510")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Train your own model with Unsloth!", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(dialog, text="This generates a training script. You must have PyTorch and Unsloth installed.", text_color="#ef4444", font=ctk.CTkFont(size=10)).pack(pady=(0, 20))

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(fill="x", padx=20)
        
        ctk.CTkLabel(frame, text="HF Model ID or Local Folder (safetensors):").pack(anchor="w")
        
        md_entry_frame = ctk.CTkFrame(frame, fg_color="transparent")
        md_entry_frame.pack(fill="x", pady=(0, 10))
        
        model_entry = ctk.CTkEntry(md_entry_frame)
        model_entry.insert(0, "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct")
        model_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def browse_model():
            folderpath = filedialog.askdirectory(title="Select Local Model Folder")
            if folderpath:
                model_entry.delete(0, "end")
                model_entry.insert(0, folderpath)
                
        ctk.CTkButton(md_entry_frame, text="Browse Folder...", width=100, command=browse_model).pack(side="right")
        
        dataset_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dataset_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(dataset_frame, text="Dataset (.jsonl), Optional:").pack(anchor="w")
        
        ds_entry_frame = ctk.CTkFrame(dataset_frame, fg_color="transparent")
        ds_entry_frame.pack(fill="x")
        
        dataset_entry = ctk.CTkEntry(ds_entry_frame)
        dataset_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def browse_file():
            filepath = filedialog.askopenfilename(
                title="Select Training Dataset",
                filetypes=(("JSONL Files", "*.jsonl"), ("CSV Files", "*.csv"), ("All Files", "*.*"))
            )
            if filepath:
                dataset_entry.delete(0, "end")
                dataset_entry.insert(0, filepath)
                
        ctk.CTkButton(ds_entry_frame, text="Browse File...", width=100, command=browse_file).pack(side="right")

        ctk.CTkLabel(frame, text="Target GGUF Export (For LM Studio):").pack(anchor="w")
        quant_menu = ctk.CTkOptionMenu(frame, values=["q4_k_m", "q8_0", "f16"], width=480)
        quant_menu.set("q4_k_m")
        quant_menu.pack(pady=(0, 15))

        ctk.CTkLabel(frame, text="GGUF is generated at the end of training and auto-saved to LM Studio.",
                     text_color="#fbbf24", font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 10))

        def generate_script():
            model_id = model_entry.get().strip()
            dataset_path = dataset_entry.get().strip()
            target_quant = quant_menu.get()
            
            # Formulate LM Studio output directory
            lm_studio_path = os.path.expanduser("~/.cache/lm-studio/models/ReadyAI_Custom_GGUF").replace("\\", "/")
            
            ds_load_code = "print('👉 TODO: Add your custom SFTTrainer dataset logic here.')"
            if dataset_path:
                ds_load_code = f"""
# 3. Load Selected Dataset
from datasets import load_dataset
try:
    dataset = load_dataset('json', data_files='{dataset_path}', split='train')
    print("\\n✅ Custom dataset '{dataset_path}' successfully loaded! Rows:", len(dataset))
    print("👉 Now, map your dataset columns to the model inputs inside SFTTrainer.")
except Exception as e:
    print("\\n❌ Error loading dataset:", e)
"""

            script_content = f"""# Auto-generated Unsloth Training Script for ReadyAI Agent
from unsloth import FastLanguageModel
import torch

# 1. Load Model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{model_id}",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True
)

# 2. Add LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16, # Rank
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth"
)

print("\\n✅ Model loaded from {model_id} and wrapped for LoRA training.")
{ds_load_code}

print("\\n-----------------------------------------------------------")
print("👉 TODO: Provide your SFTTrainer logic above to train the model.")
print(f"👉 Once trained, it will automatically export to: {lm_studio_path}")
print("-----------------------------------------------------------")

# 4. GGUF Export Output
import os
os.makedirs("{lm_studio_path}", exist_ok=True)
output_name = "{lm_studio_path}/adapter_model"
print(f"\\n⏳ Exporting trained model as GGUF ({target_quant})... This will take time.")
try:
    model.save_pretrained_gguf('{lm_studio_path}', tokenizer, quantization_method='{target_quant}')
    print("\\n✅ GGUF Export successful! Check LM Studio.")
except Exception as e:
    print("\\n❌ GGUF Export failed:", e)
"""
            script_path = os.path.join(SCRIPT_DIR, "train_lora.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            
            self._log_console("Training script 'train_lora.py' generated in workspace.")
            
            try:
                # Open terminal to the workspace directory
                subprocess.Popen(['cmd.exe', '/c', 'start', 'cmd.exe', '/K', f'cd /d "{SCRIPT_DIR}" && echo Ready to train! Run: python train_lora.py'])
                self._log_console("Terminal launched. Ensure you are in your Unsloth environment.")
            except Exception as e:
                self._log_console(f"Failed to open terminal: {e}")
            dialog.destroy()

        ctk.CTkButton(dialog, text="Generate & Launch Script", fg_color="#10b981", hover_color="#059669", command=generate_script).pack(pady=30)


if __name__ == "__main__":
    app = ReadyDualLLM()
    app.mainloop()
