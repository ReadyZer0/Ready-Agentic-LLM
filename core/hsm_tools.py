import os
import subprocess
import json

class HSMTools:
    """Hardcoded OS tools invoked by the HSM Engine."""

    @staticmethod
    def explorer(path="."):
        """Safe directory listing tool."""
        try:
            items = os.listdir(path)
            result = []
            for item in items:
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                result.append({
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "size": os.path.getsize(full_path) if not is_dir else None
                })
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"EXPLORER_ERROR: {str(e)}"

    @staticmethod
    def read_file(path):
        """Standard file reader."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"READ_ERROR: {str(e)}"

    @staticmethod
    def write_file(path, content):
        """Standard file writer."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return "WRITE_SUCCESSFUL"
        except Exception as e:
            return f"WRITE_ERROR: {str(e)}"

    @staticmethod
    def terminal(command):
        """Controlled local command execution."""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        except Exception as e:
            return f"TERMINAL_ERROR: {str(e)}"
