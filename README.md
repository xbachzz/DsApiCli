# 🚀 DeepSeek CLI & Python API Client (`DsApiCli`)

[![GitHub Stars](https://img.shields.io/github/stars/xbachzz/DsApiCli?style=flat-square&logo=github)](https://github.com/xbachzz/DsApiCli/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/xbachzz/DsApiCli?style=flat-square&logo=github)](https://github.com/xbachzz/DsApiCli/network/members)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg?style=flat-square&logo=python)](https://www.python.org/)
[![Model Support](https://img.shields.io/badge/Models-DeepSeek--R1%20%7C%20DeepSeek--V3-blueviolet?style=flat-square)](https://chat.deepseek.com)
[![PoW Solver](https://img.shields.io/badge/PoW_Engine-x86__64_JIT_Keccak-orange?style=flat-square)](pow_solver.py)

> **DsApiCli** is an ultra-fast, feature-rich **DeepSeek Command Line Interface (CLI)** and **Python SDK Client** powered by a reverse-engineered DeepSeek Web API. It comes with built-in **DeepSeek-R1 (DeepThink)** reasoning streaming, **Real-Time Web Search**, and a high-performance **native x86_64 JIT Keccak-f[1600] Proof-of-Work (PoW) solver**.

---

## 📑 Table of Contents

- [✨ Key Features](#-key-features)
- [🏗️ Technical Highlights & Architecture](#️-technical-highlights--architecture)
- [⚡ Quick Start & Installation](#-quick-start--installation)
- [🔑 How to Get DeepSeek Bearer Token](#-how-to-get-deepseek-bearer-token)
- [🖥️ CLI Interactive Usage](#️-cli-interactive-usage)
  - [Command Reference Table](#command-reference-table)
- [🐍 Python SDK / Programmatic Integration](#-python-sdk--programmatic-integration)
- [⚙️ Configuration (`config.json`)](#️-configuration-configjson)
- [⚡ JIT Proof-of-Work (PoW) Solver](#-jit-proof-of-work-pow-solver)
- [❓ FAQ & Troubleshooting](#-faq--troubleshooting)
- [⚠️ Disclaimer](#️-disclaimer)
- [📄 License](#-license)

---

## ✨ Key Features

- **🧠 DeepSeek-R1 DeepThink Reasoning**: Live real-time streaming of thinking tokens with elapsed execution time counter.
- **🌐 Real-Time Web Search**: Ground your answers with live web search results enabled directly from the CLI or SDK.
- **⚡ Native x86_64 JIT Keccak-f[1600] PoW Solver**: Instantaneous PoW challenge solving via ctypes memory buffer execution — solving challenges in sub-milliseconds with fallback to optimized pure Python.
- **🔄 Session Management**: Seamlessly create new chat sessions (`/new`), list conversation history (`/list`), or reload past sessions (`/load <id>`).
- **🎨 Rich Terminal UI**: Colorized console output, token usage stats, formatted markdown streaming, and interactive command shortcuts.
- **📦 Zero Heavy Dependencies**: Minimal dependency footprint (`requests`, `colorama`). No browser automation (Selenium/Playwright) required.
- **🧩 Dual Mode**: Use it as an **interactive CLI app** (`chat_cli.py`) or as a **reusable Python module** (`deepseek_client.py`).

---

## 🏗️ Technical Highlights & Architecture

```
                                  ┌───────────────────────────────┐
                                  │      User Prompt / Query      │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
┌─────────────────────────┐       ┌───────────────────────────────┐
│ chat.deepseek.com Server│ ◄──── │   DeepSeekClient (Python)     │
│   (Web API Endpoints)   │       └───────────────┬───────────────┘
└───────────┬─────────────┘                       │
            │ 1. PoW Challenge                    │ 2. Solve Challenge
            ▼                                     ▼
┌─────────────────────────┐       ┌───────────────────────────────┐
│ /api/v0/chat/create_pow │ ────► │ pow_solver (x86_64 JIT Engine)│
└─────────────────────────┘       └───────────────┬───────────────┘
                                                  │ 3. x-ds-pow-response
                                                  ▼
┌─────────────────────────┐       ┌───────────────────────────────┐
│ /api/v0/chat/completion │ ◄──── │ SSE Stream Receiver           │
│   (SSE Streaming Data)  │       │ (Thinking + Content + Tokens) │
└───────────┬─────────────┘       └───────────────┬───────────────┘
            │                                     │
            └─────────────────────────────────────┘
```

---

## ⚡ Quick Start & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/xbachzz/DsApiCli.git
cd DsApiCli
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the CLI
```bash
python chat_cli.py
```

---

## 🔑 How to Get DeepSeek Bearer Token

1. Open your browser and navigate to [https://chat.deepseek.com](https://chat.deepseek.com).
2. Log in to your DeepSeek account.
3. Press `F12` (or right-click and choose **Inspect**) to open **DevTools**, then switch to the **Network** tab.
4. Refresh the page or send a test message.
5. In the Network filter, search for `current` or `completion`.
6. Click on the request, inspect **Request Headers**, and copy the token value following `Authorization: Bearer <YOUR_TOKEN>`.
7. Paste this token when prompted on the first run of `chat_cli.py`, or save it in `config.json`.

---

## 🖥️ CLI Interactive Usage

When running `python chat_cli.py`, you will enter an interactive session:

```
====================================================================
   🤖 DEEPSEEK CLI CHAT TOOL (REVERSE-ENGINEERED WEB API)
====================================================================
 👤 Tài khoản : John Doe (user@example.com)
 🧠 DeepThink : BẬT (DeepSeek-R1 Reasoning)
 🌐 WebSearch : TẮT
 💡 Lệnh nhanh: /help, /new, /list, /think, /search, /status, /exit
====================================================================
```

### Command Reference Table

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/new` | None | Start a brand new chat session |
| `/list` | None | List recent chat sessions with titles and IDs |
| `/load <id>` | `session_id` | Load an existing chat session by ID |
| `/think` | `[on\|off]` | Toggle or view DeepSeek-R1 reasoning mode |
| `/search` | `[on\|off]` | Toggle or view live Web Search integration |
| `/status` | None | Display current account, session ID, and model flags |
| `/token <token>` | `token_str` | Update and save DeepSeek Bearer token |
| `/clear` | None | Clear terminal screen |
| `/help` | None | Show help menu and list of commands |
| `/exit` or `/quit` | None | Exit the application |

---

## 🐍 Python SDK / Programmatic Integration

You can easily integrate `DeepSeekClient` into your own scripts, chatbots, or AI agents:

```python
from deepseek_client import DeepSeekClient

# Initialize client with your DeepSeek Bearer token
client = DeepSeekClient(token="YOUR_DEEPSEEK_BEARER_TOKEN")

# 1. Fetch current user profile
user_info = client.get_user_info()
print("Logged in as:", user_info.get("id_profile", {}).get("name"))

# 2. Create a new chat session
session_id = client.create_session()

# 3. Stream chat completion with DeepSeek-R1
events = client.stream_chat(
    prompt="Explain Quantum Computing in simple terms.",
    session_id=session_id,
    thinking_enabled=True,   # Set to True for DeepSeek-R1, False for DeepSeek-V3
    search_enabled=False     # Set to True to enable Web Search
)

for event in events:
    if event.event_type == "think_start":
        print("\n[🧠 DeepThink Reasoning Started...]")
    elif event.event_type == "think_chunk":
        print(event.data, end="", flush=True)
    elif event.event_type == "think_done":
        print(f"\n[Thinking completed in {event.data}s]\n")
    elif event.event_type == "resp_start":
        print("[💬 Response]:\n")
    elif event.event_type == "resp_chunk":
        print(event.data, end="", flush=True)
    elif event.event_type == "finish":
        print(f"\n\n[Done | Total Tokens: {event.data.get('tokens')}]")
```

---

## ⚙️ Configuration (`config.json`)

The application automatically creates and maintains a local `config.json` configuration file:

```json
{
  "token": "YOUR_BEARER_TOKEN_HERE",
  "thinking_enabled": true,
  "search_enabled": false,
  "last_session_id": null
}
```

- `token`: Bearer authentication token from DeepSeek Web.
- `thinking_enabled`: `true` enables DeepSeek-R1 (DeepThink); `false` enables DeepSeek-V3 standard mode.
- `search_enabled`: `true` enables live web browsing integration.
- `last_session_id`: Automatically saves the last active session ID for easy resumption.

---

## ⚡ JIT Proof-of-Work (PoW) Solver

DeepSeek uses a custom **Keccak-f[1600] 23-round** Proof-of-Work challenge to protect its endpoints. 

`DsApiCli` features an integrated **Machine-Code JIT Solver (`pow_solver.py`)**:
- **Native x86_64 JIT**: Emits and executes raw machine code via Windows `VirtualAlloc` / Unix `mmap` for instant PoW nonce generation.
- **Pure Python Fallback**: Fully portable pure Python implementation ensuring cross-architecture compatibility (ARM64, Apple Silicon, Raspberry Pi, etc.).
- **Zero Configuration**: Solver automatically detects system architecture and chooses the fastest execution path.

---

## ❓ FAQ & Troubleshooting

<details>
<summary><b>1. Error: 401 Unauthorized / Token không hợp lệ</b></summary>
Your Bearer token has expired or is invalid. Open DevTools on <code>chat.deepseek.com</code>, copy a fresh Bearer token, and update it using <code>/token &lt;new_token&gt;</code> or editing <code>config.json</code>.
</details>

<details>
<summary><b>2. How to switch between DeepSeek-R1 and DeepSeek-V3?</b></summary>
Simply type <code>/think on</code> to enable DeepSeek-R1 (DeepThink Reasoning) or <code>/think off</code> to switch to DeepSeek-V3 standard mode.
</details>

<details>
<summary><b>3. Does this require paid API credits?</b></summary>
No. This tool connects to DeepSeek's Web Chat API using your user session token, so no commercial API balance is required.
</details>

<details>
<summary><b>4. Does it support streaming?</b></summary>
Yes, both reasoning thoughts and final responses are streamed character-by-character in real-time.
</details>

---

## ⚠️ Disclaimer

This project is intended strictly for educational and research purposes. It interacts with the DeepSeek web interface via reverse-engineered endpoints. This repository is not affiliated with, endorsed by, or associated with DeepSeek Inc. Please comply with DeepSeek's Terms of Service when using this tool.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/xbachzz">@xbachzz</a></sub>
</div>