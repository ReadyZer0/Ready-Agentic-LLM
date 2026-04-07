"""
Tool Parser - The core innovation of Ready Dual LLM.

Parses <tool name="..."> ... </tool> blocks from raw LLM output.

Protocol:
  <tool name="read">filepath</tool>
  <tool name="terminal">command</tool>
  <tool name="write" path="filepath">
content
  </tool>
"""

import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ToolBlock:
    """A parsed tool invocation extracted from model output."""
    tool_name: str       # e.g. "read", "write", "terminal"
    raw_content: str     # Inner content
    path: Optional[str]  # Optional path attribute for write/explorer
    start_pos: int       
    end_pos: int         

@dataclass
class ParsedResponse:
    chat_segments: List[str]       
    tool_calls: List[ToolBlock]   
    has_tools: bool                

# Regex to match: <tool name="X" [path="Y"]> Z </tool>
# Captures:
# group 1: name attr (required)
# group 2: path attr (optional, can be None)
# group 3: inner content
TOOL_PATTERN = re.compile(
    r'<tool\s+name="([^"]+)"(?:\s+path="([^"]+)")?\s*>(.*?)</tool>',
    re.DOTALL
)

def parse_sigils(text: str) -> ParsedResponse:
    tool_calls = []
    chat_segments = []
    last_end = 0

    for match in TOOL_PATTERN.finditer(text):
        tool_name = match.group(1).lower()
        path = match.group(2) if match.group(2) else None
        raw_content = match.group(3).strip()
        
        start = match.start()
        end = match.end()

        # Check if escaped (e.g. inside backticks ` <tool>... `)
        if start > 0 and text[start - 1] in ("'", '"', '`'):
            continue

        preceding_text = text[last_end:start].strip()
        if preceding_text:
            chat_segments.append(preceding_text)

        tool_calls.append(ToolBlock(
            tool_name=tool_name,
            raw_content=raw_content,
            path=path,
            start_pos=start,
            end_pos=end
        ))
        last_end = end

    trailing_text = text[last_end:].strip()
    if trailing_text:
        chat_segments.append(trailing_text)

    return ParsedResponse(
        chat_segments=chat_segments,
        tool_calls=tool_calls,
        has_tools=len(tool_calls) > 0
    )

def parse_write_block(block: ToolBlock) -> tuple:
    # Uses path attribute if available, otherwise expects path on first line
    if block.path:
        return block.path.strip(), block.raw_content
    else:
        lines = block.raw_content.split('\n', 1)
        filepath = lines[0].strip()
        content = lines[1] if len(lines) > 1 else ""
        return filepath, content

def parse_read_block(block: ToolBlock) -> str:
    return block.raw_content.strip()

def parse_terminal_block(block: ToolBlock) -> str:
    return block.raw_content.strip()

def parse_explorer_block(block: ToolBlock) -> str:
    return block.path.strip() if block.path else (block.raw_content.strip() or ".")

def parse_delegate_block(block: ToolBlock) -> str:
    return block.raw_content.strip()
