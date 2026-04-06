import json
import requests
import threading
import os
import re
from core.hsm_tools import HSMTools

class HSMEngine:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.manager_url = self.config['manager']['url']
        self.coder_url = self.config['coder']['url']
        
        self.manager_history = [{"role": "system", "content": self.config['manager']['system_message']}]
        self.coder_history = [{"role": "system", "content": self.config['coder']['system_message']}]
        self.tools = HSMTools()

    def send_to_manager(self, user_input, callback):
        """Sends user input to the Manager LLM."""
        self.manager_history.append({"role": "user", "content": user_input})
        self._manager_request(callback)

    def _manager_request(self, callback):
        def run():
            try:
                response = requests.post(
                    f"{self.manager_url}/chat/completions",
                    json={
                        "model": self.config['manager']['model'],
                        "messages": self.manager_history,
                        "temperature": 0.7
                    },
                    timeout=120
                )
                response.raise_for_status()
                data = response.json()
                content = data['choices'][0]['message']['content']
                
                self.manager_history.append({"role": "assistant", "content": content})
                callback(content)
                
                # Check for Tool Calls after responding
                self.dispatch_tool_calls(content, callback)
            except Exception as e:
                callback(f"ERROR_MANAGER: {str(e)}")

        threading.Thread(target=run, daemon=True).start()

    def send_to_coder(self, task, files_context, callback):
        """Delegates a coding task to the Coder LLM."""
        prompt = f"TASK: {task}\n\nCONTEXT:\n{files_context}"
        self.coder_history.append({"role": "user", "content": prompt})
        
        def run():
            try:
                response = requests.post(
                    f"{self.coder_url}/chat/completions",
                    json={
                        "model": self.config['coder']['model'],
                        "messages": self.coder_history,
                        "temperature": 0.1
                    },
                    timeout=180
                )
                response.raise_for_status()
                data = response.json()
                content = data['choices'][0]['message']['content']
                
                self.coder_history.append({"role": "assistant", "content": content})
                callback(content)
            except Exception as e:
                callback(f"ERROR_CODER: {str(e)}")

        threading.Thread(target=run, daemon=True).start()

    def dispatch_tool_calls(self, content, callback):
        """
        Parses and executes [HSM_TOOL: name(args)] patterns.
        Automatically feeds results back to the Manager.
        """
        tool_pattern = r"\[HSM_TOOL:\s*(\w+)\((.*?)\)\]"
        matches = re.findall(tool_pattern, content)
        
        for tool_name, args_str in matches:
            result = f"TOOL_{tool_name.upper()} NO_RESPONSE"
            
            try:
                if tool_name == "explorer":
                    result = self.tools.explorer(args_str.strip("'\"") or ".")
                elif tool_name == "read_file":
                    result = self.tools.read_file(args_str.strip("'\""))
                elif tool_name == "terminal":
                    result = self.tools.terminal(args_str.strip("'\""))
                elif tool_name == "delegate_to_coder":
                    # For delegation, we let the app handle the UI flow
                    callback("[DELEGATE_SIGNAL]")
                    return
                
                # Feed Tool Result back to Manager for the next thought
                self.manager_history.append({"role": "user", "content": f"TOOL_RESULT ({tool_name}):\n{result}"})
                self._manager_request(callback)
            except Exception as e:
                self.manager_history.append({"role": "user", "content": f"TOOL_ERROR ({tool_name}): {str(e)}"})
                self._manager_request(callback)
