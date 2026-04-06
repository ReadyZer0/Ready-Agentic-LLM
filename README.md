# Ready Dual LLM ⚡

A premium GUI application for orchestrating local LLMs with a dead-simple tool protocol.

## ⚡ The Sigil Protocol

Unlike complex JSON function-calling schemas, Ready Dual LLM uses a simple text-based protocol that **any** local model can learn:

```
~@read@~ E:\path\to\file.py ~@exit@~          → Reads a file
~@write@~ E:\path\to\file.py                   → Writes to a file
content here
~@exit@~
~@terminal@~ dir /b ~@exit@~                   → Runs a command
~@explorer@~ E:\project ~@exit@~               → Lists directory
~@delegate@~ Fix the bug in app.py ~@exit@~    → Sends to Expert Coder
```

## 🚀 Quick Start

1. Install dependencies:
```bash
pip install customtkinter requests pillow
```

2. Have a model running in [LM Studio](https://lmstudio.ai/) on port 1234

3. Launch:
```bash
python ready_dual_llm.py
```

## 🏗️ Architecture

- **Single Model Mode**: Both Manager and Coder use the same model (default)
- **Dual Model Mode**: Run two LM Studio instances on different ports
- **Autonomous Tool Loop**: Model uses tools → gets results → thinks → uses more tools → until done

## 📁 Project Structure

```
ready_dual_llm.py     ← Main app (launch this)
config.json           ← Model endpoints & system prompts
core/
├── engine.py         ← Orchestration loop
├── sigil_parser.py   ← ~@tool@~ ... ~@exit@~ parser
└── tools.py          ← read, write, terminal, explorer, delegate
```

## 🔧 Configuration

Edit `config.json` to set your model endpoints, or use the in-app Settings dialog.

## 👤 Created by

[Ali Dheyaa](https://www.linkedin.com/in/ali-dheyaa-abdulwahab-6bbbb1239/)
