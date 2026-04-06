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
from typing import List, Optional


@dataclass
class SigilBlock:
    """A parsed tool invocation extracted from model output."""
    tool_name: str       # e.g. "read", "write", "terminal"
    raw_content: str     # Everything between ~@tool@~ and ~@exit@~
    start_pos: int       # Character position in original text
    end_pos: int         # Character position in original text


@dataclass
class ParsedResponse:
    """The result of parsing a full model response."""
    chat_segments: List[str]       # Plain text segments for the user
    tool_calls: List[SigilBlock]   # Tool invocations to execute
    has_tools: bool                # Quick check


# The master regex:
#   ~@(toolname)@~  (content)  ~@exit@~
# Flags: DOTALL so . matches newlines (important for ~@write@~)
SIGIL_PATTERN = re.compile(
    r'~@(\w+)@~\s*(.*?)\s*~@exit@~',
    re.DOTALL
)


def parse_sigils(text: str) -> ParsedResponse:
    """
    Parse a model's raw text output into chat segments and tool calls.
    
    Rules:
    - ~@toolname@~ content ~@exit@~  →  tool invocation
    - Everything else  →  plain chat text
    - Quoted sigils (inside ' or ") are NOT parsed (escape mechanism)
    """
    tool_calls = []
    chat_segments = []
    last_end = 0

    for match in SIGIL_PATTERN.finditer(text):
        tool_name = match.group(1).lower()
        raw_content = match.group(2).strip()
        start = match.start()
        end = match.end()

        # Check if this sigil is "escaped" (wrapped in quotes)
        # Look at the character immediately before the ~@
        if start > 0 and text[start - 1] in ("'", '"', '`'):
            # This is escaped/quoted - treat as plain text, skip
            continue

        # Capture any plain text BEFORE this tool call
        preceding_text = text[last_end:start].strip()
        if preceding_text:
            chat_segments.append(preceding_text)

        tool_calls.append(SigilBlock(
            tool_name=tool_name,
            raw_content=raw_content,
            start_pos=start,
            end_pos=end
        ))
        last_end = end

    # Capture any trailing plain text after the last tool call
    trailing_text = text[last_end:].strip()
    if trailing_text:
        chat_segments.append(trailing_text)

    return ParsedResponse(
        chat_segments=chat_segments,
        tool_calls=tool_calls,
        has_tools=len(tool_calls) > 0
    )


def parse_write_block(raw_content: str) -> tuple:
    """
    Special parser for ~@write@~ blocks.
    First line = file path, rest = file content.
    
    Returns (filepath, content)
    """
    lines = raw_content.split('\n', 1)
    filepath = lines[0].strip()
    content = lines[1] if len(lines) > 1 else ""
    return filepath, content


def parse_read_block(raw_content: str) -> str:
    """Parser for ~@read@~ blocks. Content = file path."""
    return raw_content.strip()


def parse_terminal_block(raw_content: str) -> str:
    """Parser for ~@terminal@~ blocks. Content = command string."""
    return raw_content.strip()


def parse_explorer_block(raw_content: str) -> str:
    """Parser for ~@explorer@~ blocks. Content = directory path."""
    return raw_content.strip() or "."


def parse_delegate_block(raw_content: str) -> str:
    """Parser for ~@delegate@~ blocks. Content = task for the Coder."""
    return raw_content.strip()
