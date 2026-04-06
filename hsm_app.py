import customtkinter as ctk
import os
import json
from core.hsm_engine import HSMEngine

# Set Appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class HybridManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Initialize Engine (Requires hsm_config.json)
        # Use absolute path relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "hsm_config.json")
        self.engine = HSMEngine(config_path)

        # Window Settings
        self.title("Hybrid Strategic Manager (HSM) - Strategic Architect Console")
        self.geometry("1100x700")

        # Configure Grid Layout
        self.grid_columnconfigure(1, weight=3) # Manager Chat
        self.grid_columnconfigure(2, weight=2) # Tool Console
        self.grid_rowconfigure(0, weight=1)

        # ------------------- SIDEBAR -------------------
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="HSM ADVISOR", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_btn_1 = ctk.CTkButton(self.sidebar_frame, text="New Session", command=self.new_session_event)
        self.sidebar_btn_1.grid(row=1, column=0, padx=20, pady=10)

        self.sidebar_btn_2 = ctk.CTkButton(self.sidebar_frame, text="Model Settings", command=self.dummy_event)
        self.sidebar_btn_2.grid(row=2, column=0, padx=20, pady=10)

        self.sidebar_btn_3 = ctk.CTkButton(self.sidebar_frame, text="Tool Manifest", command=self.dummy_event)
        self.sidebar_btn_3.grid(row=3, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Theme:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Dark", "Light", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.set("Dark")
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))

        # ------------------- MANAGER CHAT PANE (LEFT) -------------------
        self.chat_frame = ctk.CTkFrame(self, corner_radius=10)
        self.chat_frame.grid(row=0, column=1, padx=(20, 10), pady=20, sticky="nsew")
        self.chat_frame.grid_rowconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        self.chat_label = ctk.CTkLabel(self.chat_frame, text="MANAGER CHAT", font=ctk.CTkFont(size=14, weight="bold"))
        self.chat_label.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="nw")

        self.chat_display = ctk.CTkTextbox(self.chat_frame, wrap="word", font=ctk.CTkFont(size=13))
        self.chat_display.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.chat_display.configure(state="disabled")

        self.entry_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.entry_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.entry_frame.grid_columnconfigure(0, weight=1)

        self.user_input = ctk.CTkEntry(self.entry_frame, placeholder_text="Enter prompt for Strategic Manager...")
        self.user_input.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.user_input.bind("<Return>", lambda e: self.send_message_event())

        self.send_button = ctk.CTkButton(self.entry_frame, text="SEND", width=80, command=self.send_message_event)
        self.send_button.grid(row=0, column=1)

        # ------------------- LOGIC & TOOL CONSOLE (RIGHT) -------------------
        self.console_frame = ctk.CTkFrame(self, corner_radius=10)
        self.console_frame.grid(row=0, column=2, padx=(10, 20), pady=20, sticky="nsew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        self.console_label = ctk.CTkLabel(self.console_frame, text="LOGIC & TOOL CONSOLE", font=ctk.CTkFont(size=14, weight="bold"))
        self.console_label.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="nw")

        self.console_display = ctk.CTkTextbox(self.console_frame, font=ctk.CTkFont(family="Consolas", size=11), wrap="none", text_color="#10b981")
        self.console_display.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.console_display.configure(state="disabled")

        # Bottom Status Bar
        self.status_bar = ctk.CTkFrame(self, height=25, corner_radius=0)
        self.status_bar.grid(row=1, column=0, columnspan=3, sticky="ew")
        
        self.manager_status = ctk.CTkLabel(self.status_bar, text="MANAGER: READY", font=ctk.CTkFont(size=10))
        self.manager_status.pack(side="left", padx=20)

        self.coder_status = ctk.CTkLabel(self.status_bar, text="CODER: READY", font=ctk.CTkFont(size=10))
        self.coder_status.pack(side="left", padx=20)

    def log_console(self, text):
        """Append log messages to the tool console."""
        self.console_display.configure(state="normal")
        self.console_display.insert("end", f"> {text}\n")
        self.console_display.see("end")
        self.console_display.configure(state="disabled")

    def log_chat(self, role, content):
        """Append messages to the chat history display."""
        prefix = "YOU" if role == "user" else "MANAGER"
        
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{prefix}: ", "bold")
        self.chat_display.insert("end", f"{content}\n\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def send_message_event(self):
        msg = self.user_input.get()
        if not msg: return
        
        self.user_input.delete(0, "end")
        self.log_chat("user", msg)
        self.log_console(f"Strategist assessing mission parameters...")
        self.manager_status.configure(text="MANAGER: THINKING...")
        
        # Engine Request
        self.engine.send_to_manager(msg, self.handle_manager_response_ui)

    def handle_manager_response_ui(self, content):
        """Processes Manager responses and handles UI updates."""
        if content == "[DELEGATE_SIGNAL]":
            self.log_console("CRITICAL DELEGATION INITIATED: Calling Expert Coder Instance...")
            self.coder_status.configure(text="CODER: PROCESSING...")
            return
            
        if "ERROR_MANAGER" in content:
            self.log_console(f"CRITICAL: {content}")
            self.manager_status.configure(text="MANAGER: ERROR")
            return

        self.manager_status.configure(text="MANAGER: READY")
        
        # Check for Tool Call patterns (to log in console)
        if "[HSM_TOOL:" in content:
            tool_name = content.split("[HSM_TOOL:")[1].split("(")[0].strip()
            self.log_console(f"Strategic Tool Call: {tool_name}")
        else:
            self.log_chat("assistant", content)

    def new_session_event(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        self.chat_display.configure(state="disabled")
        self.log_console("New Mission Control session started. Identity Locked.")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def dummy_event(self):
        self.log_console("Orchestration level feature restricted in BETA.")

if __name__ == "__main__":
    app = HybridManagerApp()
    app.mainloop()
