# AI Browser Agent

An AI-powered browser automation tool that lets you control your web browser using natural language. Give it a task in plain English and watch it navigate, search, click, and extract information — all on its own.

Built with **Browser-Use**, **Pydantic AI**, and the **Chrome DevTools Protocol (CDP)**.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows)

---

## Features

- **Natural Language Control** — Describe what you want in plain English and the AI agent handles the rest
- **Web UI Dashboard** — Clean browser-based interface with real-time agent logs, an AI chatbot, and in-app API key management
- **Microsoft Edge Support** — Pre-configured to work with Edge out of the box (Chrome/Chromium also supported)
- **Multi-LLM Support** — Works with Google Gemini, Groq, OpenAI GPT-4o, Anthropic Claude, or Browser-Use Cloud
- **Live Browser View** — Runs in a visible browser window so you can watch the agent work in real-time
- **CLI & Script Mode** — Run tasks from the command line or integrate into your own Python scripts

---

## Screenshots

### Web UI
The Web UI provides a dual-panel interface:
- **Browser Agent Panel** — Enter a task, pick your LLM, and watch the agent execute with live logs
- **AI Chatbot Panel** — Chat with Gemini or Groq for quick Q&A alongside the browser agent

### CLI Mode
```
[+] Starting Browser-Use Agent with Microsoft Edge...
[+] Task: Navigate to https://www.bing.com, search for 'Microsoft Edge AI', and summarize the top result.

==================================================
Agent Final Result:
==================================================
Microsoft Edge now integrates AI-powered features including...
```

---

## Quick Start

### Prerequisites
- **Python 3.11+**
- **Microsoft Edge** (or Chrome/Chromium)
- At least one LLM API key (see below)

### 1. Clone the Repository
```bash
git clone https://github.com/Ayush23072005/ai-browser-agent.git
cd ai-browser-agent
```

### 2. Create a Virtual Environment
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -e .
```

### 4. Configure API Keys
Copy the example environment file and add your keys:
```bash
cp .env.example .env
```

Open `.env` and set at least one of the following:

| Provider | Key | Free Tier | Get a Key |
|----------|-----|-----------|-----------|
| **Google Gemini** | `GOOGLE_API_KEY` | ✅ Yes | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **Groq** | `GROQ_API_KEY` | ✅ Yes | [console.groq.com](https://console.groq.com/keys) |
| **Browser-Use Cloud** | `BROWSER_USE_API_KEY` | ✅ $1 credit | [cloud.browser-use.com](https://cloud.browser-use.com/new-api-key) |
| **OpenAI** | `OPENAI_API_KEY` | ❌ Paid | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Anthropic** | `ANTHROPIC_API_KEY` | ❌ Paid | [console.anthropic.com](https://console.anthropic.com/) |

> **Tip:** Google Gemini and Groq both offer generous free tiers — no credit card required.

### 5. Run

**Option A — Web UI (Recommended)**
```bash
python web_ui.py
```
This opens a local web dashboard in your browser where you can enter tasks, manage API keys, and chat with the AI.

On Windows, you can also double-click `start_web_ui.bat`.

**Option B — CLI Script**
```bash
python run_edge.py
```
Runs a predefined task directly in Microsoft Edge from the terminal.

---

## Project Structure

```
ai-browser-agent/
├── browser_use/          # Core agent engine
│   ├── agent/            # Agent loop, prompts, and task orchestration
│   ├── browser/          # Browser connection and CDP management
│   ├── repl/             # REPL session, page capture, and highlighting
│   ├── mcp/              # MCP (Model Context Protocol) server
│   ├── llm/              # LLM provider abstractions
│   ├── skills/           # Built-in agent skills
│   └── telemetry/        # Anonymous usage telemetry
├── examples/             # Example scripts
├── tests/                # Test suite
├── static/               # Static assets (images)
├── web_ui.py             # Web UI server (Starlette + Uvicorn)
├── run_edge.py           # CLI runner for Microsoft Edge
├── start_web_ui.bat      # Windows batch launcher
├── pyproject.toml        # Project config and dependencies
├── Dockerfile            # Docker support
├── .env.example          # Template for environment variables
└── README.md
```

---

## Configuration

All configuration is done through the `.env` file. Key options:

```env
# LLM API Keys (set at least one)
GOOGLE_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Browser (optional — defaults to Edge)
# EDGE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe

# Logging: debug, info, warning, error
BROWSER_USE_LOGGING_LEVEL=info

# Disable telemetry
# ANONYMIZED_TELEMETRY=false
```

---

## Usage Examples

### Python Script
```python
from browser_use import Agent, Browser, ChatGoogle

agent = Agent(
    task="Go to GitHub trending and tell me the top 3 repositories today",
    llm=ChatGoogle("gemini-2.0-flash"),
    browser=Browser("edge", headless=False),
)

result = agent.run_sync()
print(result.final_result())
```

### Web UI
1. Start with `python web_ui.py`
2. Enter your task: *"Search Amazon for wireless earbuds under $30 and list the top 3 results"*
3. Click **Run** and watch the agent work in a live Edge window
4. View results and step-by-step logs in the dashboard

---

## Docker

```bash
docker build -t ai-browser-agent .
docker run --env-file .env ai-browser-agent
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | [Browser-Use](https://github.com/browser-use/browser-use) + [Pydantic AI](https://github.com/pydantic/pydantic-ai) |
| Browser Control | Chrome DevTools Protocol (CDP) |
| Web UI | Starlette + Uvicorn |
| LLM Providers | Google Gemini, Groq, OpenAI, Anthropic |
| Language | Python 3.11+ |

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

- [Browser-Use](https://github.com/browser-use/browser-use) — The core browser agent engine
- [Pydantic AI](https://github.com/pydantic/pydantic-ai) — Agent orchestration framework
- [Google Gemini](https://ai.google.dev/) — Default LLM provider
