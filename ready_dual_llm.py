"""
Ready Dual LLM - Strategic AI Orchestration Console
A premium GUI for dual-LLM workflows with the ~@sigil@~ tool protocol.
"""

import customtkinter as ctk
import os
import sys
import threading
import webbrowser
from datetime import datetime

# Ensure imports work from any CWD
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.engine import Engine

# Appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ReadyDualLLM(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Engine
        config_path = os.path.join(SCRIPT_DIR, "config.json")
        self.engine = Engine(config_path)

        # Window
        self.title("Ready Dual LLM")
        self.geometry("1150x720")
        self.minsize(900, 550)

        # Layout: sidebar | chat | console
        self.grid_columnconfigure(0, weight=0, minsize=180)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_chat_pane()
        self._build_console_pane()
        self._build_status_bar()

        # Focus the input field on start
        self.after(100, self.user_input.focus)

    # ============================================================
    # SIDEBAR
    # ============================================================
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0,
                                     fg_color="#1a1a2e")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        # Logo
        ctk.CTkLabel(self.sidebar, text="⚡ Ready\nDual LLM",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#e94560").grid(row=0, column=0, padx=20, pady=(25, 5))

        ctk.CTkLabel(self.sidebar, text="Strategic Console",
                     font=ctk.CTkFont(size=10),
                     text_color="#6c757d").grid(row=1, column=0, padx=20, pady=(0, 15))

        # Buttons
        ctk.CTkButton(self.sidebar, text="⟳  New Session",
                      command=self.new_session,
                      fg_color="#16213e", hover_color="#0f3460",
                      anchor="w").grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="⚙  Settings",
                      command=self.open_settings,
                      fg_color="#16213e", hover_color="#0f3460",
                      anchor="w").grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        ctk.CTkButton(self.sidebar, text="📋  Tool Guide",
                      command=self.show_tool_guide,
                      fg_color="#16213e", hover_color="#0f3460",
                      anchor="w").grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        # Theme selector
        ctk.CTkLabel(self.sidebar, text="Theme", text_color="#6c757d",
                     font=ctk.CTkFont(size=10)).grid(row=6, column=0, padx=15, pady=(10, 0))
        ctk.CTkOptionMenu(self.sidebar, values=["Dark", "Light", "System"],
                          command=lambda v: ctk.set_appearance_mode(v),
                          width=140).grid(row=7, column=0, padx=15, pady=(5, 10))

        # Creator credit
        credit_btn = ctk.CTkButton(self.sidebar, text="Created by Ali Dheyaa",
                                    font=ctk.CTkFont(size=10),
                                    fg_color="transparent", hover_color="#16213e",
                                    text_color="#6c757d", height=20,
                                    command=lambda: webbrowser.open("https://www.linkedin.com/in/ali-dheyaa-abdulwahab-6bbbb1239/"))
        credit_btn.grid(row=8, column=0, padx=15, pady=(5, 12))

    # ============================================================
    # CHAT PANE (Left main area)
    # ============================================================
    def _build_chat_pane(self):
        self.chat_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#0f0f23")
        self.chat_frame.grid(row=0, column=1, padx=(15, 8), pady=15, sticky="nsew")
        self.chat_frame.grid_rowconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Header
        ctk.CTkLabel(self.chat_frame, text="MANAGER CHAT",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#e94560").grid(row=0, column=0, padx=18, pady=(12, 5), sticky="w")

        # Chat display
        self.chat_display = ctk.CTkTextbox(self.chat_frame, wrap="word",
                                            font=ctk.CTkFont(family="Segoe UI", size=12),
                                            fg_color="#0a0a1a",
                                            text_color="#e0e0e0",
                                            border_width=0)
        self.chat_display.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.chat_display.configure(state="disabled")

        # Input area
        input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        input_frame.grid(row=2, column=0, padx=10, pady=(0, 12), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.user_input = ctk.CTkEntry(input_frame,
                                        placeholder_text="Talk to the Manager...",
                                        font=ctk.CTkFont(size=12),
                                        height=38)
        self.user_input.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.user_input.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(input_frame, text="SEND", width=75, height=38,
                                       font=ctk.CTkFont(weight="bold"),
                                       fg_color="#e94560", hover_color="#c81e45",
                                       command=self.send_message)
        self.send_btn.grid(row=0, column=1)

    # ============================================================
    # CONSOLE PANE (Right side)
    # ============================================================
    def _build_console_pane(self):
        self.console_frame = ctk.CTkFrame(self, corner_radius=12, fg_color="#0f0f23")
        self.console_frame.grid(row=0, column=2, padx=(8, 15), pady=15, sticky="nsew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        # Header
        ctk.CTkLabel(self.console_frame, text="TOOL CONSOLE",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#10b981").grid(row=0, column=0, padx=18, pady=(12, 5), sticky="w")

        # Console display
        self.console_display = ctk.CTkTextbox(self.console_frame,
                                               font=ctk.CTkFont(family="Consolas", size=11),
                                               fg_color="#0a0a1a",
                                               text_color="#10b981",
                                               wrap="word",
                                               border_width=0)
        self.console_display.grid(row=1, column=0, padx=10, pady=(5, 12), sticky="nsew")
        self.console_display.configure(state="disabled")

    # ============================================================
    # STATUS BAR
    # ============================================================
    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="#1a1a2e")
        self.status_bar.grid(row=1, column=0, columnspan=3, sticky="ew")

        self.manager_status_label = ctk.CTkLabel(self.status_bar,
            text="● MANAGER: READY", font=ctk.CTkFont(size=10),
            text_color="#10b981")
        self.manager_status_label.pack(side="left", padx=20)

        self.coder_status_label = ctk.CTkLabel(self.status_bar,
            text="● CODER: STANDBY", font=ctk.CTkFont(size=10),
            text_color="#6c757d")
        self.coder_status_label.pack(side="left", padx=20)

        self.loop_label = ctk.CTkLabel(self.status_bar,
            text="", font=ctk.CTkFont(size=10),
            text_color="#6c757d")
        self.loop_label.pack(side="right", padx=20)

    # ============================================================
    # UI HELPERS (Thread-safe via after())
    # ============================================================
    def _log_chat(self, role: str, text: str):
        """Thread-safe chat logging."""
        def do():
            prefix = "YOU" if role == "user" else "MANAGER"
            color = "#64b5f6" if role == "user" else "#ffd54f"
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"{prefix}:\n", "prefix")
            self.chat_display.insert("end", f"{text}\n\n")
            self.chat_display.see("end")
            self.chat_display.configure(state="disabled")
        self.after(0, do)

    def _log_console(self, text: str):
        """Thread-safe console logging."""
        def do():
            ts = datetime.now().strftime("%H:%M:%S")
            self.console_display.configure(state="normal")
            self.console_display.insert("end", f"[{ts}] {text}\n")
            self.console_display.see("end")
            self.console_display.configure(state="disabled")
        self.after(0, do)

    def _set_status(self, role: str, state: str):
        """Thread-safe status updates."""
        def do():
            label = self.manager_status_label if role == "manager" else self.coder_status_label
            color = "#10b981" if "READY" in state else "#fbbf24" if "THINK" in state else "#ef4444"
            display_role = role.upper()
            label.configure(text=f"● {display_role}: {state}", text_color=color)
        self.after(0, do)

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

        # Disable send while processing
        self.send_btn.configure(state="disabled")

        def on_done_wrapper(role, text):
            self._log_chat(role, text)
            self.after(0, lambda: self.send_btn.configure(state="normal"))

        self.engine.send_to_manager(
            user_input=msg,
            on_chat=lambda role, text: self._log_chat(role, text),
            on_tool_log=lambda text: self._log_console(text),
            on_status=lambda role, state: self._set_status(role, state),
            on_coder_result=lambda text: self._log_console(f"[CODER OUTPUT]\n{text[:500]}...")
        )

        # Re-enable send after a safety timeout
        self.after(5000, lambda: self.send_btn.configure(state="normal"))

    def new_session(self):
        self.engine.reset_session()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        self.chat_display.configure(state="disabled")
        self._log_console("Session reset. Manager memory cleared.")

    def open_settings(self):
        """Open a settings dialog for model configuration."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ready Dual LLM - Settings")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Manager API URL:",
                     font=ctk.CTkFont(weight="bold")).pack(padx=20, pady=(20, 5), anchor="w")
        mgr_url = ctk.CTkEntry(dialog, width=400)
        mgr_url.insert(0, self.engine.config['manager']['url'])
        mgr_url.pack(padx=20)

        ctk.CTkLabel(dialog, text="Manager Model (or 'auto'):",
                     font=ctk.CTkFont(weight="bold")).pack(padx=20, pady=(15, 5), anchor="w")
        mgr_model = ctk.CTkEntry(dialog, width=400)
        mgr_model.insert(0, self.engine.config['manager']['model'])
        mgr_model.pack(padx=20)

        ctk.CTkLabel(dialog, text="Coder API URL:",
                     font=ctk.CTkFont(weight="bold")).pack(padx=20, pady=(15, 5), anchor="w")
        coder_url = ctk.CTkEntry(dialog, width=400)
        coder_url.insert(0, self.engine.config['coder']['url'])
        coder_url.pack(padx=20)

        ctk.CTkLabel(dialog, text="Coder Model (or 'auto'):",
                     font=ctk.CTkFont(weight="bold")).pack(padx=20, pady=(15, 5), anchor="w")
        coder_model = ctk.CTkEntry(dialog, width=400)
        coder_model.insert(0, self.engine.config['coder']['model'])
        coder_model.pack(padx=20)

        def save():
            self.engine.config['manager']['url'] = mgr_url.get()
            self.engine.config['manager']['model'] = mgr_model.get()
            self.engine.config['coder']['url'] = coder_url.get()
            self.engine.config['coder']['model'] = coder_model.get()
            self.engine.manager_url = mgr_url.get()
            self.engine.coder_url = coder_url.get()
            # Persist
            import json
            cfg_path = os.path.join(SCRIPT_DIR, "config.json")
            with open(cfg_path, 'w') as f:
                json.dump(self.engine.config, f, indent=2)
            self._log_console("Settings saved and applied.")
            dialog.destroy()

        ctk.CTkButton(dialog, text="Save & Apply", fg_color="#e94560",
                      hover_color="#c81e45", command=save).pack(pady=25)

    def show_tool_guide(self):
        """Show the sigil tool reference."""
        guide = (
            "~@sigil@~ TOOL PROTOCOL\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "~@read@~ filepath ~@exit@~\n"
            "  → Reads a file\n\n"
            "~@write@~ filepath\n"
            "content here\n"
            "~@exit@~\n"
            "  → Writes content to file\n\n"
            "~@terminal@~ command ~@exit@~\n"
            "  → Runs a shell command\n\n"
            "~@explorer@~ path ~@exit@~\n"
            "  → Lists directory contents\n\n"
            "~@delegate@~ task ~@exit@~\n"
            "  → Sends task to Expert Coder\n\n"
            "To MENTION a tool without invoking:\n"
            "  Wrap in quotes: '~@read@~'\n"
        )
        self._log_console(guide)


if __name__ == "__main__":
    app = ReadyDualLLM()
    app.mainloop()
