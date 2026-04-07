"""
Tools - Native OS tools for Ready Dual LLM.
Each tool maps directly to a sigil name.
"""

import os
import subprocess
import json
import requests
from duckduckgo_search import DDGS


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
                return f"[CRASH ERROR] The command failed with exit code {result.returncode}.\n\n[STDOUT]\n{result.stdout}\n\n[STDERR]\n{result.stderr}"
            
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

    @staticmethod
    def web_search(query: str, api_key: str = "") -> str:
        """~@search@~ handler: Search the web using Brave Search API."""
        if not api_key:
            return "[ERROR] No Brave Search API key configured. Add it in Settings."
        try:
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key
            }
            params = {"q": query, "count": 5}
            r = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers, params=params, timeout=10
            )
            r.raise_for_status()
            data = r.json()

            results = []
            for item in data.get("web", {}).get("results", [])[:5]:
                title = item.get("title", "")
                url = item.get("url", "")
                desc = item.get("description", "")
                results.append(f"- {title}\n  {url}\n  {desc}")
            if results:
                return f"[SEARCH RESULTS for: {query}]\n" + "\n\n".join(results)
            else:
                return f"[SEARCH] No results found for: {query}"
        except Exception as e:
            return f"[ERROR] search failed: {e}"

    @staticmethod
    def duck_search(query: str) -> str:
        """~@ddg@~ handler: Search the web for free using DuckDuckGo."""
        try:
            results = []
            with DDGS() as ddgs:
                ddgs_gen = ddgs.text(query, max_results=8)
                for r in ddgs_gen:
                    title = r.get("title", "No Title")
                    href = r.get("href", "No URL")
                    body = r.get("body", "No Description")
                    results.append(f"- {title}\n  {href}\n  {body}")
            
            if results:
                return f"[DDG SEARCH RESULTS for: {query}]\n\n" + "\n\n".join(results)
            else:
                return f"[DDG SEARCH] No results found for: {query}"
        except Exception as e:
            return f"[ERROR] ddg search failed: {e}"
