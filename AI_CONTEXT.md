# Ready AI Agent: Comprehensive Architecture & Context Blueprint

This document explains the entire architecture, current capabilities, and planned structural overhauls for the **Ready Agentic LLM** application. It is designed to be provided to an AI assistant as "context" to immediately understand the repository's purpose, design patterns, and internal logic.

## 1. High-Level Purpose
Ready Agentic LLM is a local-first, autonomous AI orchestrator. It acts as a bridge between a local LLM (running via LM Studio/Ollama) and the user's local operating system. Instead of relying on complex JSON-based tool calling (which small local models struggle with), it uses a **lightweight, text-based sigil protocol** (`~@command@~ ... ~@exit@~`). 

The application acts as a **Translator Engine**:
1. The LLM outputs simple text delimiters.
2. The Python backend intercepts these delimiters from the streaming response.
3. The backend executes the native OS action (or translates it to an MCP server request).
4. The result is injected back into the LLM's context as plain text.

## 2. Directory Structure & File Roles

### `ready_dual_qt.py` (The Antigravity UI)
*   **Role**: The main PySide6 Graphical User Interface.
*   **Design Paradigm**: A bifurcated, professional "Premiere-style" workstation layout.
    *   **Left Column**: Chat & Logs (Manager Chat, Tool Console).
    *   **Right Column**: The Workspace (Expert Canvas, Code Viewer).
*   **Features (Current & Planned)**:
    *   **Collapsible Thinking State**: Intercepts `<think>...</think>` tags and places them in an accordion labeled "Agent is reasoning...".
    *   **Terminal Loader**: Displays a spinning loader when destructive `~@terminal@~` commands are running.
    *   **Human-in-the-Loop Modal**: Pauses execution and asks for UI Approval/Rejection for destructive operations.
    *   **Layout Persistence**: Saves window geometry/state to `layout.bin` so custom dock arrangements persist across sessions.

### `core/engine.py` (The Orchestrator)
*   **Role**: The cognitive core handling the AI API loops, streaming logic, and tool dispatch.
*   **Features (Current & Planned)**:
    *   **Streaming Text Interception**: Buffers text as it streams from LM Studio. The moment `~@` is detected, it halts UI output and captures the block until `~@exit@~`.
    *   **Failsafe Parsing**: Auto-closes tool blocks if the model forgets the `~@exit@~` tag after a set number of tokens.
    *   **Fully Asynchronous Operations**: Wraps text parsing and MCP background calls in `async/await` to prevent the UI from freezing during 30-second terminal operations.
    *   **Graceful Text Injection**: Injects execution errors back into the context (e.g., `[System Log: Command failed with error...]`) to allow the model to self-correct instead of crashing.
    *   **Loop Protection**: Hard limits the number of autonomous tool calls to prevent infinite loops.

### `core/tools.py` (The Translator Engine / Action Layer)
*   **Role**: The native implementations of the text protocol commands.
*   **Routing Map (Text-to-MCP / Text-to-OS)**:
    *   `~@read@~ <path> ~@exit@~`: Reads file contents (Translates to MCP `read_file`).
    *   `~@write@~ <path>\n<content> ~@exit@~`: Writes files (Translates to MCP `write_file`).
    *   `~@terminal@~ <command> ~@exit@~`: Executes shell commands securely.
    *   `~@explorer@~ <path> ~@exit@~`: Lists directory contents.
    *   `~@search@~ / ~@ddg@~`: Native web searching.

### `core/sigil_parser.py` (The Protocol Parser)
*   **Role**: Uses Regex to isolate chat text from `~@tool@~ ... ~@exit@~` blocks.
*   **Feature**: Ensures that tool logic is completely stripped from the user-facing chat window, keeping the dialogue clean while the backend handles the technical payload.

### `core/dataset.py` (Synthetic Memory Injection)
*   **Role**: Provides "few-shot" training examples.
*   **Feature**: Injects perfect examples of tool usage into the model's system prompt/history at the start of a session, teaching the local model how to format sigils correctly.

## 3. Advanced Subsystems & Features

### Dual LLM Orchestration (`~@delegate@~`)
This feature pairs a lightweight local model (Worker) with a cloud-based frontier model (Architect/Planner like Gemini Pro).
*   **The Workflow**:
    1. The user asks the local model to build a complex feature.
    2. The local model outputs `~@delegate@~ Plan the architecture for X ~@exit@~`.
    3. The backend intercepts this, pauses the local stream, and sends the prompt to the Gemini API.
    4. Gemini returns a detailed markdown plan.
    5. The backend injects Gemini's plan into the local model's stream as `[Expert Coder Response: Here is the plan...]`.
    6. The local model then uses `~@write@~` and `~@terminal@~` to autonomously build the architecture.

### Automatic Model Discovery
*   Instead of hardcoding models, the engine automatically fetches available models from the LM Studio `/v1/models` endpoint.
*   This is handled asynchronously via a `ModelLoader` thread to ensure the settings dialog opens instantly without freezing the UI.

## 4. Current Objectives for AI Assistants
When loaded into a new AI session, the primary goals are:
1. **Implement the Streaming Parser**: Transition `engine.py` to intercept LM Studio SSE streams in real-time.
2. **Build the Antigravity UI**: Implement the bifurcated layout, thinking accordions, and terminal loaders in `ready_dual_qt.py`.
3. **Solidify Asynchronous Execution**: Ensure all tool executions and fail-safes are wrapped in robust async architectures to prevent UI locks.
4. **Finalize the Translator Layer**: Map the sigil actions to their respective native Python implementations or actual MCP servers.
