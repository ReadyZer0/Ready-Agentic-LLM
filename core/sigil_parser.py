"""
Sigil Parser - The core innovation of Ready Dual LLM.

Parses ~@toolname@~ ... ~@exit@~ blocks from raw LLM output.
Designed to be simple enough for even tiny models to learn.

Protocol:
  ~@read@~ filepath ~@exit@~
  ~@write@~ filepath\ncontent\n~@exit@~
  ~@terminal@~ command ~@exit@~
  ~@delegate@~ task description ~@exit@~
  ~@explorer@~ directory ~@exit@~

Anything NOT inside sigils is plain chat text for the user.
"""

import re
from dataclasses import dataclass
from typing import List

@dataclass
class ToolBlock:
    """A parsed tool invocation extracted from model output."""
    tool_name: str       # e.g. "read", "write", "terminal"
    raw_content: str     # Everything between ~@tool@~ and ~@exit@~
    start_pos: int       
    end_pos: int         

@dataclass
class ParsedResponse:
    chat_segments: List[str]       
    tool_calls: List[ToolBlock]   
    has_tools: bool                

# Regex to match: ~@name@~ content ~@exit@~
SIGIL_PATTERN = re.compile(
    r'~@(\w+)@~\s*(.*?)\s*~@exit@~',
    re.DOTALL
)

def parse_sigils(text: str) -> ParsedResponse:
    tool_calls = []
    chat_segments = []
    last_end = 0

    for match in SIGIL_PATTERN.finditer(text):
        tool_name = match.group(1).lower()
        raw_content = match.group(2).strip()
        
        start = match.start()
        end = match.end()

        # Check if escaped (e.g. inside backticks or quotes)
        if start > 0 and text[start - 1] in ("'", '"', '`'):
            continue

        preceding_text = text[last_end:start].strip()
        if preceding_text:
            chat_segments.append(preceding_text)

        tool_calls.append(ToolBlock(
            tool_name=tool_name,
            raw_content=raw_content,
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
    lines = block.raw_content.split('\n', 1)
    filepath = lines[0].strip()
    content = lines[1] if len(lines) > 1 else ""
    return filepath, content

def parse_read_block(block: ToolBlock) -> str:
    return block.raw_content.strip()

def parse_terminal_block(block: ToolBlock) -> str:
    return block.raw_content.strip()

def parse_explorer_block(block: ToolBlock) -> str:
    return block.raw_content.strip() or "."

def parse_delegate_block(block: ToolBlock) -> str:
    return block.raw_content.strip()
