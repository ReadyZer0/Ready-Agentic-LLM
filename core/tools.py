"""
Tools - Native OS tools for Ready Dual LLM.
Each tool maps directly to a sigil name.
"""

import os
import subprocess
import json


class Tools:
    """Hardcoded OS tools invoked by sigil dispatch."""

    @staticmethod
    def read(filepath: str) -> str:
        """~@read@~ handler: Read a file and return its contents."""
        try:
            filepath = filepath.strip().strip('"').strip("'")
            if not os.path.exists(filepath):
                return f"[ERROR] File not found: {filepath}"
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            line_count = content.count('\n') + 1
            return f"[FILE: {filepath} | {line_count} lines]\n{content}"
        except Exception as e:
            return f"[ERROR] read failed: {e}"

    @staticmethod
    def write(filepath: str, content: str) -> str:
        """~@write@~ handler: Write content to a file."""
        try:
            filepath = filepath.strip().strip('"').strip("'")
            os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            line_count = content.count('\n') + 1
            return f"[OK] Written {line_count} lines to {filepath}"
        except Exception as e:
            return f"[ERROR] write failed: {e}"

    @staticmethod
    def terminal(command: str) -> str:
        """~@terminal@~ handler: Execute a shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8',
                errors='replace'
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[EXIT CODE: {result.returncode}]"
            return output.strip() or "[OK] Command completed (no output)"
        except subprocess.TimeoutExpired:
            return "[ERROR] Command timed out after 30 seconds"
        except Exception as e:
            return f"[ERROR] terminal failed: {e}"

    @staticmethod
    def explorer(path: str) -> str:
        """~@explorer@~ handler: List directory contents."""
        try:
            path = path.strip().strip('"').strip("'") or "."
            if not os.path.exists(path):
                return f"[ERROR] Path not found: {path}"
            
            items = os.listdir(path)
            lines = []
            for item in sorted(items):
                full = os.path.join(path, item)
                if os.path.isdir(full):
                    lines.append(f"  [DIR]  {item}/")
                else:
                    size = os.path.getsize(full)
                    lines.append(f"  [FILE] {item} ({size} bytes)")
            
            header = f"[EXPLORER: {path} | {len(items)} items]"
            return header + "\n" + "\n".join(lines)
        except Exception as e:
            return f"[ERROR] explorer failed: {e}"
