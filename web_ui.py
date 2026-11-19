"""
Browser-Use Web UI (Dual-API: Browser-Use Cloud + Google Gemini & Groq AI Chatbot)
----------------------------------------------------------------------------------
Runs a local web server with a clean Web UI featuring:
1. Browser Agent (Microsoft Edge): Automates browsing tasks using Browser-Use, Gemini, or Groq.
2. AI Chatbot: Real-time conversational AI powered by Google Gemini or Groq API.
3. In-App Key Manager: Save free keys directly from the Web UI to .env.

Run with:
    .\\venv\\Scripts\\python.exe web_ui.py
"""

import os
import sys
import json
import asyncio
import logging
import threading
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
import uvicorn

from browser_use import Agent, Browser, ChatGoogle, ChatOpenAI, ChatAnthropic
from browser_use.auth import browser_use_api_key

# Global state
CURRENT_AGENT_TASK = None
CANCEL_EVENT = asyncio.Event()

def get_browser_agent_llm():
    """Detect available LLM for Browser-Use Agent."""
    load_dotenv(override=True)
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    # Prioritize Google Gemini (verified active, working with gemini-flash-lite-latest)
    if google_key:
        return ChatGoogle("gemini-flash-lite-latest", api_key=google_key)
    elif groq_key:
        return ChatOpenAI("qwen/qwen3.8-27b", base_url="https://api.groq.com/openai/v1", api_key=groq_key)
    elif openai_key:
        return ChatOpenAI("gpt-4o", api_key=openai_key)
    elif anthropic_key:
        return ChatAnthropic("claude-3-5-sonnet-latest", api_key=anthropic_key)

    # If Browser-Use API key explicitly set in .env
    if os.getenv("BROWSER_USE_API_KEY"):
        return None

    # If user has an AQ. key, still try ChatGoogle
    if google_key:
        return ChatGoogle("gemini-2.0-flash", api_key=google_key)

    # Check if Browser-Use Cloud has stored credentials
    try:
        if browser_use_api_key():
            return None
    except Exception:
        pass

    return None

class SSELogHandler(logging.Handler):
    """Captures agent loop logs and pushes to an asyncio queue."""
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.queue = queue
        self.loop = loop

    def emit(self, record):
        try:
            msg = self.format(record)
            if any(k in record.name for k in ("browser_use.agent", "browser_use.browser")):
                if "step " in msg.lower():
                    clean = msg
                else:
                    clean = f"[{record.levelname}] {record.getMessage()}"
                self.loop.call_soon_threadsafe(self.queue.put_nowait, clean)
        except Exception:
            pass

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Browser-Use & AI Assistant</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg: #0b1120;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: #334155;
            --primary: #0284c7;
            --primary-hover: #0369a1;
            --gemini-purple: #8b5cf6;
            --gemini-hover: #7c3aed;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --terminal-bg: #070b14;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 1.5rem 1rem 3rem 1rem;
        }

        .container {
            width: 100%;
            max-width: 980px;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        /* Header */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 0.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .brand-logo {
            width: 52px;
            height: 52px;
            border-radius: 12px;
            object-fit: cover;
            box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35);
            border: 2px solid rgba(56, 189, 248, 0.4);
        }

        .brand-icon {
            font-size: 2.5rem;
            line-height: 1;
        }

        .brand-text h1 {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
            letter-spacing: -0.025em;
        }

        .brand-text p {
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        .badge-bar {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .badge-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: rgba(2, 132, 199, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(2, 132, 199, 0.35);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-pill.gemini {
            background: rgba(139, 92, 246, 0.15);
            color: #c084fc;
            border-color: rgba(139, 92, 246, 0.35);
        }

        /* Dual Tabs Navigation */
        .tabs-nav {
            display: flex;
            gap: 0.75rem;
            background: #131d31;
            padding: 0.4rem;
            border-radius: 12px;
            border: 1px solid var(--border);
        }

        .tab-btn {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
            padding: 0.75rem 1.25rem;
            background: transparent;
            color: var(--text-muted);
            border: 1px solid transparent;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .tab-btn:hover {
            color: var(--text);
            background: rgba(255, 255, 255, 0.04);
        }

        .tab-btn.active {
            background: var(--surface);
            color: var(--text);
            border-color: rgba(56, 189, 248, 0.3);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        }

        .tab-btn.active.gemini-tab {
            border-color: rgba(168, 85, 247, 0.4);
        }

        .tab-tag {
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            border-radius: 9999px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }

        .tab-tag.tag-edge {
            background: rgba(2, 132, 199, 0.25);
            color: #38bdf8;
        }

        .tab-tag.tag-gemini {
            background: rgba(139, 92, 246, 0.25);
            color: #c084fc;
        }

        /* Cards & Content */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        label {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        textarea {
            width: 100%;
            height: 90px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem;
            color: var(--text);
            font-family: inherit;
            font-size: 0.95rem;
            resize: vertical;
            outline: none;
            transition: border-color 0.15s ease;
        }

        textarea:focus {
            border-color: var(--primary);
        }

        .chips {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            align-items: center;
        }

        .chip-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
        }

        .chip {
            background: #172033;
            border: 1px solid var(--border);
            padding: 0.35rem 0.7rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.15s ease;
            user-select: none;
        }

        .chip:hover {
            color: var(--text);
            background: var(--surface-hover);
            border-color: var(--primary);
        }

        .chip.gemini-chip:hover {
            border-color: var(--gemini-purple);
        }

        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
        }

        .toggle-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            color: var(--text-muted);
            cursor: pointer;
        }

        .toggle-group input[type="checkbox"] {
            accent-color: var(--primary);
            width: 16px;
            height: 16px;
            cursor: pointer;
        }

        .btn-run {
            background: var(--primary);
            color: white;
            border: none;
            padding: 0.7rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.15s ease;
            box-shadow: 0 2px 4px rgba(2, 132, 199, 0.4);
        }

        .btn-run:hover {
            background: var(--primary-hover);
        }

        .btn-run:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            background: #475569;
            box-shadow: none;
        }

        /* Status and Alerts */
        .status-bar {
            display: none;
            align-items: center;
            gap: 0.75rem;
            background: #172554;
            border: 1px solid #1e40af;
            color: #93c5fd;
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-size: 0.9rem;
        }

        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.2);
            border-top-color: #38bdf8;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .human-alert {
            display: none;
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid var(--warning);
            color: #fbbf24;
            padding: 0.85rem 1rem;
            border-radius: 8px;
            font-size: 0.875rem;
            animation: pulse-border 1.5s infinite;
        }

        @keyframes pulse-border {
            0%, 100% { border-color: var(--warning); }
            50% { border-color: #fef08a; }
        }

        /* Terminal Logs */
        .terminal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .terminal {
            background: var(--terminal-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            height: 240px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }

        .log-line {
            white-space: pre-wrap;
            word-break: break-all;
            color: #cbd5e1;
        }

        .log-step { color: #38bdf8; font-weight: 600; }
        .log-success { color: #34d399; font-weight: 600; }
        .log-error { color: #f87171; font-weight: 600; }

        /* Result Card */
        .result-card {
            display: none;
            background: #0f172a;
            border: 1px solid #10b981;
            border-radius: 12px;
            padding: 1.25rem;
            flex-direction: column;
            gap: 0.75rem;
            box-shadow: 0 4px 20px rgba(16, 185, 129, 0.15);
        }

        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .result-title {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 700;
            color: #34d399;
            font-size: 1rem;
        }

        .result-content {
            font-size: 0.95rem;
            line-height: 1.65;
            color: #e2e8f0;
            word-break: break-word;
        }

        /* ================= MARKDOWN TYPOGRAPHY ================= */
        .markdown-body {
            font-size: 0.95rem;
            line-height: 1.65;
            color: #e2e8f0;
            word-break: break-word;
        }
        .markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {
            color: #f8fafc;
            margin-top: 1.1rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }
        .markdown-body h1 { font-size: 1.35rem; border-bottom: 1px solid var(--border); padding-bottom: 0.35rem; }
        .markdown-body h2 { font-size: 1.2rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.25rem; }
        .markdown-body h3 { font-size: 1.05rem; color: #38bdf8; }
        .markdown-body h4 { font-size: 0.95rem; color: #c084fc; }
        .markdown-body p {
            margin-bottom: 0.75rem;
            line-height: 1.65;
        }
        .markdown-body ul, .markdown-body ol {
            margin-left: 1.5rem;
            margin-top: 0.4rem;
            margin-bottom: 0.75rem;
        }
        .markdown-body li {
            margin-bottom: 0.3rem;
            line-height: 1.55;
        }
        .markdown-body strong {
            color: #ffffff;
            font-weight: 600;
        }
        .markdown-body em {
            color: #cbd5e1;
        }
        .markdown-body a {
            color: #38bdf8;
            text-decoration: underline;
        }
        .markdown-body code {
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85em;
            color: #38bdf8;
        }
        .markdown-body pre {
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            overflow-x: auto;
            margin: 0.75rem 0;
        }
        .markdown-body pre code {
            background: transparent;
            border: none;
            padding: 0;
            color: #e2e8f0;
        }
        .markdown-body table {
            width: 100%;
            border-collapse: collapse;
            margin: 0.85rem 0;
            font-size: 0.9rem;
        }
        .markdown-body th, .markdown-body td {
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 0.55rem 0.85rem;
            text-align: left;
        }
        .markdown-body th {
            background: rgba(30, 41, 59, 0.75);
            color: #93c5fd;
            font-weight: 600;
        }
        .markdown-body tr:nth-child(even) {
            background: rgba(255, 255, 255, 0.02);
        }
        .markdown-body blockquote {
            border-left: 3px solid #8b5cf6;
            margin: 0.75rem 0;
            padding: 0.4rem 0.85rem;
            background: rgba(139, 92, 246, 0.08);
            color: #cbd5e1;
        }

        .btn-copy {
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 0.35rem 0.75rem;
            border-radius: 6px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .btn-copy:hover {
            color: var(--text);
            border-color: var(--primary);
        }

        /* ================= CHATBOT STYLES ================= */
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .chat-status-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #172033;
            border: 1px solid var(--border);
            padding: 0.6rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
        }

        .chat-status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-weight: 600;
            font-size: 0.8rem;
        }

        .chat-box {
            background: var(--terminal-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.25rem;
            height: 440px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .chat-msg {
            display: flex;
            gap: 0.75rem;
            max-width: 85%;
        }

        .chat-msg.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }

        .chat-msg.ai {
            align-self: flex-start;
        }

        .msg-avatar {
            width: 34px;
            height: 34px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            flex-shrink: 0;
        }

        .msg-avatar.user-avatar {
            background: #0284c7;
            color: white;
        }

        .msg-avatar.ai-avatar {
            background: #8b5cf6;
            color: white;
            box-shadow: 0 2px 8px rgba(139, 92, 246, 0.4);
        }

        .msg-bubble {
            background: #1e293b;
            border: 1px solid var(--border);
            padding: 0.85rem 1.1rem;
            border-radius: 12px;
            font-size: 0.92rem;
            line-height: 1.6;
            color: #f1f5f9;
            word-break: break-word;
        }

        .chat-msg.user .msg-bubble {
            background: #0369a1;
            border-color: #0284c7;
            color: #ffffff;
            border-bottom-right-radius: 2px;
        }

        .chat-msg.ai .msg-bubble {
            background: #151d30;
            border-color: #2a3754;
            border-bottom-left-radius: 2px;
        }

        .msg-bubble a { color: #38bdf8; text-decoration: underline; }
        .msg-bubble pre {
            background: #090d16;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 0.75rem;
            overflow-x: auto;
            margin: 0.5rem 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
        }
        .msg-bubble code {
            font-family: 'JetBrains Mono', monospace;
            background: rgba(0, 0, 0, 0.3);
            padding: 0.15rem 0.35rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }
        .msg-bubble p:not(:last-child) { margin-bottom: 0.6rem; }
        .msg-bubble ul, .msg-bubble ol { margin-left: 1.25rem; margin-bottom: 0.6rem; }

        .chat-input-row {
            display: flex;
            gap: 0.75rem;
        }

        .chat-input-row textarea {
            height: 52px;
            resize: none;
            font-size: 0.95rem;
        }

        .btn-send {
            background: var(--gemini-purple);
            color: white;
            border: none;
            padding: 0 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            transition: all 0.15s ease;
            box-shadow: 0 2px 6px rgba(139, 92, 246, 0.4);
            white-space: nowrap;
        }

        .btn-send:hover {
            background: var(--gemini-hover);
        }

        .btn-send:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            background: #475569;
        }

        .typing-indicator {
            display: none;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-muted);
            font-size: 0.85rem;
            font-style: italic;
            padding-left: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand">
                <img src="/logo.png" alt="Browser-Use Logo" class="brand-logo" onerror="this.style.display='none'; document.getElementById('fallbackIcon').style.display='inline-block';">
                <span id="fallbackIcon" class="brand-icon" style="display:none;">🌐</span>
                <div class="brand-text">
                    <h1>Browser-Use Assistant</h1>
                    <p>Automate web actions using AI and Microsoft Edge</p>
                </div>
            </div>
            <div class="badge-bar">
                <div class="badge-pill">
                    <span>✔</span> Microsoft Edge
                </div>
                <div class="badge-pill gemini">
                    <span>✨</span> Multi-AI Engine
                </div>
            </div>
        </header>

        <!-- Quick API Key Setup Card -->
        <div class="card" id="keyConfigCard" style="border-color: rgba(245, 158, 11, 0.4); background: #131b2e;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                <div>
                    <strong style="color: #fbbf24; font-size: 0.9rem;">🔑 Free API Key Setup</strong>
                    <span style="font-size: 0.8rem; color: var(--text-muted); display: block;">Trial credit ($1) is used up. Paste any free key below to run unlimited tasks:</span>
                </div>
                <div style="display: flex; gap: 0.75rem; font-size: 0.75rem;">
                    <a href="https://console.groq.com/keys" target="_blank" style="color: #38bdf8; text-decoration: underline; font-weight: 600;">⚡ Get Free Groq Key (30s)</a>
                    <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color: #c084fc; text-decoration: underline; font-weight: 600;">✨ Get Google Gemini Key</a>
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.4rem;">
                <input type="password" id="uiApiKeyInput" placeholder="Paste Groq (gsk_...) or Gemini (AIzaSy...) or Browser-Use (bu_...) key here" style="flex: 1; background: var(--bg); border: 1px solid var(--border); padding: 0.55rem 0.75rem; border-radius: 6px; color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">
                <button id="saveKeyBtn" onclick="saveApiKeyFromUI()" style="background: var(--primary); color: white; border: none; padding: 0.55rem 1.25rem; border-radius: 6px; font-weight: 600; cursor: pointer; white-space: nowrap;">💾 Save Key</button>
            </div>
            <div id="uiKeyStatus" style="display: none; font-size: 0.85rem; font-weight: 600; margin-top: 0.35rem;"></div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tabs-nav">
            <button class="tab-btn active" id="tabBrowserBtn" onclick="switchTab('browser')">
                <span>🌐 Browser Agent</span>
                <span class="tab-tag tag-edge">Edge Automation</span>
            </button>
            <button class="tab-btn gemini-tab" id="tabChatBtn" onclick="switchTab('chat')">
                <span>💬 AI Chatbot</span>
                <span class="tab-tag tag-gemini">Conversational AI</span>
            </button>
        </div>

        <!-- TAB 1: BROWSER AGENT -->
        <div id="sectionBrowser" style="display: flex; flex-direction: column; gap: 1.25rem;">
            <div class="card">
                <label for="taskInput">
                    <span>Enter Your Web Automation Task</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: normal;">What should Edge do?</span>
                </label>
                <textarea id="taskInput" placeholder="Example: do web research and tell me top three latest AI news..."></textarea>

                <div class="chips">
                    <span class="chip-label">Quick Tasks:</span>
                    <div class="chip" onclick="setTask('do web research and tell me top three latest AI news')">⚡ Top 3 AI News</div>
                    <div class="chip" onclick="setTask('Go to amazon.com, search for smartphones, find the top 3 most expensive phones, and list their names and prices.')">🛍️ Amazon Top 3 Phones</div>
                    <div class="chip" onclick="setTask('Go to https://www.wikipedia.org and summarize Quantum Computing in 3 bullet points.')">📖 Wikipedia Summary</div>
                    <div class="chip" onclick="setTask('Navigate to https://www.bing.com, search for \'Latest Space Discoveries\', and summarize the top result.')">🚀 Space News</div>
                </div>

                <div class="controls">
                    <label class="toggle-group">
                        <input type="checkbox" id="headlessToggle">
                        <span>Show Browser Window (Watch Edge work live)</span>
                    </label>
                    <button id="runBtn" class="btn-run" onclick="startTask()">
                        <span>▶ Run Task</span>
                    </button>
                </div>

                <div id="statusBar" class="status-bar">
                    <div class="spinner"></div>
                    <span id="statusText">Microsoft Edge is running your task...</span>
                </div>

                <div id="humanAlert" class="human-alert">
                    ⚠️ <strong>Human Verification or Login Required!</strong><br>
                    Please solve the verification / log in directly on the open <strong>Microsoft Edge</strong> window.<br>
                    The agent will pause and wait for you to complete it!
                </div>
            </div>

            <div class="card">
                <div class="terminal-header">
                    <span>Live Action Logs (Edge CDP Loop)</span>
                    <span id="logCounter">0 logs</span>
                </div>
                <div id="terminal" class="terminal">
                    <div class="log-line" style="color: var(--text-muted);">Ready. Enter a task above and click 'Run Task'.</div>
                </div>
            </div>

            <div id="resultCard" class="result-card">
                <div class="result-header">
                    <div id="resultTitle" class="result-title">
                        <span>✔</span> Task Completed Successfully!
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
                        <button id="askChatbotBtn" onclick="sendResultToChatbot()" style="display: none; background: linear-gradient(135deg, #8b5cf6, #6366f1); color: white; border: none; padding: 0.45rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600; cursor: pointer; align-items: center; gap: 0.45rem; box-shadow: 0 2px 8px rgba(139, 92, 246, 0.4); transition: all 0.15s ease;">
                            <span>💬 Ask AI Chatbot About This Result ➔</span>
                        </button>
                        <button class="btn-copy" onclick="copyResult()">📋 Copy Result</button>
                    </div>
                </div>
                <div id="resultContent" class="result-content markdown-body"></div>
                <div id="chatbotSyncNotice" style="display: none; margin-top: 0.85rem; padding: 0.75rem 1rem; background: rgba(139, 92, 246, 0.12); border: 1px solid rgba(139, 92, 246, 0.35); border-radius: 8px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
                    <div style="font-size: 0.85rem; color: #c084fc; display: flex; align-items: center; gap: 0.5rem;">
                        <span>✨</span>
                        <span><strong>AI Chatbot Synced:</strong> These web research findings are loaded into Gemini. You can ask any question without copy-pasting.</span>
                    </div>
                    <button onclick="sendResultToChatbot()" style="background: var(--gemini-purple); color: white; border: none; padding: 0.35rem 0.85rem; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer;">Open Chatbot ➔</button>
                </div>
            </div>
        </div>

        <!-- TAB 2: AI CHATBOT -->
        <div id="sectionChat" style="display: none; flex-direction: column; gap: 1.25rem;">
            <div class="card chat-container">
                <div class="chat-status-bar">
                    <div class="chat-status-pill" id="keyStatusBadge">
                        <span style="color: #34d399;">●</span>
                        <span>Conversational AI Engine (Gemini / Groq)</span>
                    </div>
                    <button class="btn-copy" onclick="clearChat()">🗑️ Clear Chat</button>
                </div>

                <!-- Active Research Context Card -->
                <div id="chatContextBanner" style="display: none; background: #0f172a; border: 1px solid rgba(139, 92, 246, 0.45); border-radius: 12px; padding: 1rem 1.25rem; flex-direction: column; gap: 0.85rem; box-shadow: 0 4px 16px rgba(139, 92, 246, 0.15);">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(139, 92, 246, 0.25); padding-bottom: 0.65rem; flex-wrap: wrap; gap: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.6rem; color: #c084fc; font-weight: 700; font-size: 0.95rem;">
                            <span style="font-size: 1.2rem;">🌐</span>
                            <span id="chatContextTitle">Web Research Result</span>
                        </div>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            <button id="toggleContextBtn" onclick="toggleContextView()" style="background: rgba(139, 92, 246, 0.2); border: 1px solid rgba(139, 92, 246, 0.4); color: #e9d5ff; padding: 0.3rem 0.75rem; border-radius: 6px; font-size: 0.78rem; font-weight: 600; cursor: pointer;">▲ Collapse</button>
                            <button class="btn-copy" onclick="copyContextData()">📋 Copy</button>
                            <button onclick="clearChatContext()" style="background: transparent; border: 1px solid rgba(248, 113, 113, 0.4); color: #f87171; padding: 0.3rem 0.75rem; border-radius: 6px; font-size: 0.78rem; cursor: pointer;">✕ Remove</button>
                        </div>
                    </div>
                    <div id="contextDataPreview" class="markdown-body" style="font-size: 0.95rem; line-height: 1.65; color: #e2e8f0; max-height: 550px; overflow-y: auto; padding: 0.5rem 0.25rem;"></div>
                    <div style="font-size: 0.8rem; color: #a78bfa; border-top: 1px solid rgba(139, 92, 246, 0.2); padding-top: 0.5rem; display: flex; align-items: center; gap: 0.4rem;">
                        <span>💡</span>
                        <span><strong>Gemini already has this research in memory.</strong> Ask any query below (or click a quick chip) without mentioning or copy-pasting the text!</span>
                    </div>
                </div>

                <div id="chatBox" class="chat-box">
                    <div class="chat-msg ai">
                        <div class="msg-avatar ai-avatar">✨</div>
                        <div class="msg-bubble">
                            <strong>Hello! I am your AI Assistant.</strong><br>
                            You can ask me anything — from explaining complex topics and writing code to brainstorming ideas or analyzing information!
                        </div>
                    </div>
                </div>

                <div class="typing-indicator" id="typingIndicator">
                    <div class="spinner" style="border-top-color: #c084fc;"></div>
                    <span>AI is thinking...</span>
                </div>

                <div class="chips" id="chatChipsContainer">
                    <span class="chip-label">Try Asking:</span>
                    <div class="chip gemini-chip" onclick="setChatMessage('Explain Quantum Computing like I am 10 years old.')">⚛️ Explain Quantum Computing</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('Write a clean Python script using asyncio and aiohttp to fetch a web page.')">🐍 Python Asyncio Example</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('What are the top 3 high-impact AI trends in 2026?')">📈 2026 AI Trends</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('Give me 5 creative ideas for an engineering college AI project.')">💡 College AI Projects</div>
                </div>

                <div class="chat-input-row">
                    <textarea id="chatInput" placeholder="Ask AI anything... (Press Enter to send, Shift+Enter for newline)"></textarea>
                    <button id="sendBtn" class="btn-send" onclick="sendChatMessage()">
                        <span>Send ✨</span>
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Save API key from UI
        async function saveApiKeyFromUI() {
            const key = document.getElementById('uiApiKeyInput').value.trim();
            const statusDiv = document.getElementById('uiKeyStatus');
            const saveBtn = document.getElementById('saveKeyBtn');

            if (!key) {
                alert('Please paste an API key first!');
                return;
            }

            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            try {
                const resp = await fetch('/api/save-key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: key })
                });
                const data = await resp.json();
                if (data.success) {
                    statusDiv.style.display = 'block';
                    statusDiv.style.color = '#34d399';
                    statusDiv.innerHTML = `✔ ${data.message} You can now click <strong>Run Task</strong>!`;
                    document.getElementById('uiApiKeyInput').value = '';
                } else {
                    statusDiv.style.display = 'block';
                    statusDiv.style.color = '#f87171';
                    statusDiv.textContent = '❌ ' + (data.error || 'Failed to save key.');
                }
            } catch (e) {
                statusDiv.style.display = 'block';
                statusDiv.style.color = '#f87171';
                statusDiv.textContent = '❌ Network error: ' + e.message;
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = '💾 Save Key';
            }
        }

        // Tab switching
        function switchTab(tab) {
            const secBrowser = document.getElementById('sectionBrowser');
            const secChat = document.getElementById('sectionChat');
            const btnBrowser = document.getElementById('tabBrowserBtn');
            const btnChat = document.getElementById('tabChatBtn');

            if (tab === 'browser') {
                secBrowser.style.display = 'flex';
                secChat.style.display = 'none';
                btnBrowser.classList.add('active');
                btnChat.classList.remove('active');
            } else {
                secBrowser.style.display = 'none';
                secChat.style.display = 'flex';
                btnBrowser.classList.remove('active');
                btnChat.classList.add('active');
                document.getElementById('chatInput').focus();
            }
        }

        // ================= TAB 1: BROWSER AGENT =================
        let eventSource = null;
        const taskInput = document.getElementById('taskInput');
        const runBtn = document.getElementById('runBtn');
        const statusBar = document.getElementById('statusBar');
        const statusText = document.getElementById('statusText');
        const humanAlert = document.getElementById('humanAlert');
        const terminal = document.getElementById('terminal');
        const logCounter = document.getElementById('logCounter');
        const resultCard = document.getElementById('resultCard');
        const resultTitle = document.getElementById('resultTitle');
        const resultContent = document.getElementById('resultContent');
        const headlessToggle = document.getElementById('headlessToggle');

        // Check visible Edge window by default
        headlessToggle.checked = true;

        let logCount = 0;

        function setTask(text) {
            taskInput.value = text;
            taskInput.focus();
        }

        function appendLog(text, className = '') {
            const line = document.createElement('div');
            line.className = 'log-line ' + className;
            line.textContent = text;
            terminal.appendChild(line);
            terminal.scrollTop = terminal.scrollHeight;
            logCount++;
            logCounter.textContent = `${logCount} logs`;
        }

        function startTask() {
            const task = taskInput.value.trim();
            if (!task) {
                alert('Please enter a task description first!');
                return;
            }

            terminal.innerHTML = '';
            logCount = 0;
            logCounter.textContent = '0 logs';
            resultCard.style.display = 'none';
            resultContent.textContent = '';
            humanAlert.style.display = 'none';
            statusBar.style.display = 'flex';
            statusText.textContent = 'Starting Microsoft Edge...';
            runBtn.disabled = true;
            runBtn.innerHTML = '<span>⏳ Running...</span>';

            appendLog(`[START] Task: "${task}"`, 'log-step');
            appendLog(`[BROWSER] Launching Microsoft Edge (Visible: ${headlessToggle.checked})...`);

            const headless = !headlessToggle.checked;
            const url = `/api/run?task=${encodeURIComponent(task)}&headless=${headless}`;

            if (eventSource) {
                eventSource.close();
            }

            eventSource = new EventSource(url);

            eventSource.onopen = () => {
                appendLog('[SYSTEM] Connected to agent engine...', 'log-step');
            };

            let isDone = false;

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'log') {
                    let cls = '';
                    if (data.text.includes('step ')) cls = 'log-step';
                    else if (data.text.includes('error') || data.text.includes('FAIL') || data.text.includes('Warning') || data.text.includes('Out of Browser Use credits')) cls = 'log-error';
                    appendLog(data.text, cls);

                    const lower = data.text.toLowerCase();
                    if (lower.includes('human_verification') || lower.includes('unusual-browser-activity') || (lower.includes('challenge') && lower.includes('detected'))) {
                        humanAlert.style.display = 'block';
                    }
                } else if (data.type === 'status') {
                    statusText.textContent = data.text;
                } else if (data.type === 'result') {
                    humanAlert.style.display = 'none';
                    const isSuccess = data.success !== false;

                    if (isSuccess) {
                        appendLog(`[SUCCESS] Task completed!`, 'log-success');
                        resultCard.style.borderColor = '#10b981';
                        resultTitle.innerHTML = '<span>✔</span> Task Completed Successfully!';
                        resultTitle.style.color = '#34d399';
                    } else {
                        appendLog(`[NOTICE] Task finished without verified result.`, 'log-error');
                        resultCard.style.borderColor = '#f59e0b';
                        resultTitle.innerHTML = '<span>⚠️</span> Task Incomplete / Notice';
                        resultTitle.style.color = '#fbbf24';
                    }

                    resultContent.innerHTML = renderMarkdown(data.text);
                    resultCard.style.display = 'flex';
                    resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

                    if (data.text && data.text.trim().length > 10 && !data.text.includes('Task completed without text output')) {
                        latestResearchContext = data.text;
                        latestResearchTask = taskInput.value.trim();
                        const askBtn = document.getElementById('askChatbotBtn');
                        const syncNotice = document.getElementById('chatbotSyncNotice');
                        if (askBtn) {
                            askBtn.style.display = 'inline-flex';
                            askBtn.innerHTML = '<span>💬 Ask AI Chatbot About This Result ➔</span>';
                        }
                        if (syncNotice) {
                            syncNotice.style.display = 'flex';
                        }
                        syncResearchToChatbot(latestResearchTask, latestResearchContext);
                    }
                } else if (data.type === 'done') {
                    isDone = true;
                    humanAlert.style.display = 'none';
                    finishTask();
                } else if (data.type === 'error') {
                    appendLog(`[ERROR] ${data.text}`, 'log-error');
                    isDone = true;
                    humanAlert.style.display = 'none';
                    finishTask();
                }
            };

            eventSource.onerror = (err) => {
                if (!isDone) {
                    appendLog('[SYSTEM] Connection closed.', 'log-error');
                    finishTask();
                }
            };
        }

        function finishTask() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            humanAlert.style.display = 'none';
            statusBar.style.display = 'none';
            runBtn.disabled = false;
            runBtn.innerHTML = '<span>▶ Run Task</span>';
        }

        function renderMarkdown(text) {
            if (window.marked && typeof marked.parse === 'function') {
                return marked.parse(text);
            }
            return text
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
                .split('\n').join('<br>');
        }

        function copyResult() {
            navigator.clipboard.writeText(resultContent.textContent);
            alert('Result copied to clipboard!');
        }

        // ================= TAB 2: AI CHATBOT =================
        let latestResearchContext = "";
        let latestResearchTask = "";

        const chatBox = document.getElementById('chatBox');
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        const typingIndicator = document.getElementById('typingIndicator');
        let chatHistory = [];

        function sendResultToChatbot() {
            switchTab('chat');
            document.getElementById('chatInput').focus();
        }

        function toggleContextView() {
            const preview = document.getElementById('contextDataPreview');
            const btn = document.getElementById('toggleContextBtn');
            if (!preview) return;
            if (preview.style.display === 'none' || !preview.style.display) {
                preview.style.display = 'block';
                if (btn) btn.textContent = '▲ Collapse';
            } else {
                preview.style.display = 'none';
                if (btn) btn.textContent = '▼ Show Full Research';
            }
        }

        function copyContextData() {
            if (latestResearchContext) {
                navigator.clipboard.writeText(latestResearchContext);
                alert('Research result copied to clipboard!');
            }
        }

        function clearChatContext() {
            latestResearchContext = "";
            latestResearchTask = "";
            document.getElementById('chatContextBanner').style.display = 'none';
            const preview = document.getElementById('contextDataPreview');
            if (preview) {
                preview.style.display = 'none';
                preview.innerHTML = '';
            }
            restoreDefaultChatChips();
        }

        function restoreDefaultChatChips() {
            const chipsContainer = document.getElementById('chatChipsContainer');
            if (chipsContainer) {
                chipsContainer.innerHTML = `
                    <span class="chip-label">Try Asking:</span>
                    <div class="chip gemini-chip" onclick="setChatMessage('Explain Quantum Computing like I am 10 years old.')">⚛️ Explain Quantum Computing</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('Write a clean Python script using asyncio and aiohttp to fetch a web page.')">🐍 Python Asyncio Example</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('What are the top 3 high-impact AI trends in 2026?')">📈 2026 AI Trends</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('Give me 5 creative ideas for an engineering college AI project.')">💡 College AI Projects</div>
                `;
            }
        }

        function syncResearchToChatbot(task, contextText) {
            latestResearchContext = contextText;
            latestResearchTask = task;

            const banner = document.getElementById('chatContextBanner');
            const titleEl = document.getElementById('chatContextTitle');
            const preview = document.getElementById('contextDataPreview');
            const btn = document.getElementById('toggleContextBtn');

            if (banner) {
                banner.style.display = 'flex';
            }
            if (titleEl) {
                titleEl.textContent = `Web Research Findings: "${task || 'Web Research'}"`;
            }
            if (preview) {
                // Render fully human-readable HTML markdown
                preview.innerHTML = renderMarkdown(contextText);
                preview.style.display = 'block';
                if (btn) btn.textContent = '▲ Collapse';
            }

            // Add greeting only once per loaded research
            const existingIntro = document.getElementById('researchIntroMsg');
            if (existingIntro) {
                existingIntro.remove();
            }

            const msgDiv = document.createElement('div');
            msgDiv.id = 'researchIntroMsg';
            msgDiv.className = 'chat-msg ai';
            msgDiv.innerHTML = `
                <div class="msg-avatar ai-avatar">✨</div>
                <div class="msg-bubble markdown-body">
                    <strong>Web research result automatically loaded into Gemini!</strong><br>
                    I have analyzed and memorized the complete findings for: <em>"${task || 'Web Research'}"</em>.<br><br>
                    You can ask me any question or summary request about these findings below — <strong>no need to copy or paste anything!</strong>
                </div>
            `;
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;

            const chipsContainer = document.getElementById('chatChipsContainer');
            if (chipsContainer) {
                let chipsHtml = '<span class="chip-label">Ask About Research:</span>';
                const lower = contextText.toLowerCase();
                if (lower.includes('airline') || lower.includes('flight') || lower.includes('jetblue')) {
                    chipsHtml += `<div class="chip gemini-chip" onclick="setChatMessage('Which airline supports AI booking agents and which airline restricts them?')">✈️ Airlines AI Policy</div>`;
                }
                if (lower.includes('exploit') || lower.includes('kernel') || lower.includes('cyber') || lower.includes('openai')) {
                    chipsHtml += `<div class="chip gemini-chip" onclick="setChatMessage('Explain the OpenAI Linux kernel exploit discovery in detail.')">🛡️ Linux Kernel Exploit</div>`;
                }
                if (lower.includes('hospital') || lower.includes('azure') || lower.includes('microsoft') || lower.includes('ohio')) {
                    chipsHtml += `<div class="chip gemini-chip" onclick="setChatMessage('What are the key goals of Ohio State and Microsoft Azure smart hospital partnership?')">🏥 Hospital AI Partnership</div>`;
                }
                if (lower.includes('subject') || lower.includes('aiml') || lower.includes('curriculum') || lower.includes('semester')) {
                    chipsHtml += `<div class="chip gemini-chip" onclick="setChatMessage('List all the 3rd and 4th semester subjects in a clean bulleted list.')">📚 Subjects List</div>`;
                }
                chipsHtml += `
                    <div class="chip gemini-chip" onclick="setChatMessage('Summarize these findings in 3 simple, easy-to-understand bullet points.')">📌 3-Bullet Summary</div>
                    <div class="chip gemini-chip" onclick="setChatMessage('What are the most critical takeaways and impacts of these findings?')">💡 Key Takeaways</div>
                `;
                chipsContainer.innerHTML = chipsHtml;
            }
        }

        function setChatMessage(text) {
            chatInput.value = text;
            chatInput.focus();
        }

        function appendChatMessage(role, text) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `chat-msg ${role}`;

            const avatarDiv = document.createElement('div');
            avatarDiv.className = `msg-avatar ${role}-avatar`;
            avatarDiv.textContent = role === 'user' ? '👤' : '✨';

            const bubbleDiv = document.createElement('div');
            bubbleDiv.className = 'msg-bubble';
            bubbleDiv.innerHTML = renderMarkdown(text);

            msgDiv.appendChild(avatarDiv);
            msgDiv.appendChild(bubbleDiv);
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function clearChat() {
            chatBox.innerHTML = `
                <div class="chat-msg ai">
                    <div class="msg-avatar ai-avatar">✨</div>
                    <div class="msg-bubble">
                        <strong>Chat cleared!</strong> How can I help you today?
                    </div>
                </div>
            `;
            chatHistory = [];
        }

        async function sendChatMessage() {
            const message = chatInput.value.trim();
            if (!message) return;

            // Display user message
            appendChatMessage('user', message);
            chatInput.value = '';
            chatInput.disabled = true;
            sendBtn.disabled = true;
            typingIndicator.style.display = 'flex';
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        history: chatHistory.slice(-8),
                        context: latestResearchContext
                    })
                });

                const data = await response.json();
                typingIndicator.style.display = 'none';

                if (data.reply) {
                    appendChatMessage('ai', data.reply);
                    chatHistory.push({ role: 'user', text: message });
                    chatHistory.push({ role: 'model', text: data.reply });
                } else if (data.error) {
                    appendChatMessage('ai', `⚠️ **Error:** ${data.error}`);
                }
            } catch (err) {
                typingIndicator.style.display = 'none';
                appendChatMessage('ai', `❌ **Network Error:** Could not contact server (${err.message}).`);
            } finally {
                chatInput.disabled = false;
                sendBtn.disabled = false;
                chatInput.focus();
            }
        }

        // Send on Enter (Shift+Enter for newline)
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    </script>
</body>
</html>
"""

async def homepage(request):
    return HTMLResponse(HTML_PAGE)

async def api_save_key(request):
    """Save an API key directly from the Web UI to .env."""
    try:
        body = await request.json()
        raw_key = body.get("key", "").strip()
        if not raw_key:
            return JSONResponse({"error": "Key is empty"}, status_code=400)

        env_var = "GROQ_API_KEY"
        provider = "Groq (Llama 3.3 70B)"

        if raw_key.startswith("gsk_"):
            env_var = "GROQ_API_KEY"
            provider = "Groq (Llama 3.3 70B)"
        elif raw_key.startswith("AIzaSy") or raw_key.startswith("AQ."):
            env_var = "GOOGLE_API_KEY"
            provider = "Google Gemini"
        elif raw_key.startswith("bu_"):
            env_var = "BROWSER_USE_API_KEY"
            provider = "Browser-Use Cloud"
        elif raw_key.startswith("sk-"):
            env_var = "OPENAI_API_KEY"
            provider = "OpenAI"

        for p in [Path(".env"), Path("browser-use-main/.env")]:
            if p.exists():
                lines = p.read_text(encoding="utf-8").splitlines()
                new_lines = []
                found = False
                for line in lines:
                    if line.strip().startswith(f"{env_var}="):
                        new_lines.append(f"{env_var}={raw_key}")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f"{env_var}={raw_key}")
                p.write_text("\n".join(new_lines), encoding="utf-8")

        load_dotenv(override=True)
        return JSONResponse({"success": True, "provider": provider, "message": f"Successfully configured {provider}!"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_chat(request):
    """AI Chatbot endpoint supporting Google Gemini and Groq with automatic Research Context."""
    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        context = body.get("context", "").strip()

        if not message:
            return JSONResponse({"error": "Empty message"}, status_code=400)

        load_dotenv(override=True)
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")

        if not api_key and not groq_key:
            return JSONResponse({
                "reply": (
                    "⚠️ **No Free API Key Detected in `.env`!**\n\n"
                    "To chat, add one of the following to your `.env` file (or paste it into the box at the top of the page):\n\n"
                    "**Option 1: Google Gemini API (Free)**\n"
                    "```env\nGOOGLE_API_KEY=AIzaSy...\n```\n"
                    "*(Create in a personal project at [Google AI Studio](https://aistudio.google.com/app/apikey))*\n\n"
                    "**Option 2: Groq API (Instant 100% Free - 30 seconds, No Verification)**\n"
                    "```env\nGROQ_API_KEY=gsk_...\n```\n"
                    "*(Get instantly at [console.groq.com/keys](https://console.groq.com/keys))*\n\n"
                    "Save `.env` and ask your question again!"
                )
            })

        # Try Google Gemini if key is present
        if api_key:
            from google import genai
            client = genai.Client(api_key=api_key)

            def call_gemini():
                models_to_try = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-flash-latest"]
                last_err = None
                contents_payload = []

                # Inject research context at turn 0 so Gemini has complete memory of findings
                if context:
                    contents_payload.append({
                        "role": "user",
                        "parts": [{
                            "text": (
                                "You are an intelligent AI assistant. The user just conducted automated web research using Microsoft Edge. "
                                "Here is the exact research information and findings retrieved from the web:\n\n"
                                "==================== WEB RESEARCH FINDINGS ====================\n"
                                f"{context}\n"
                                "===============================================================\n\n"
                                "Instructions:\n"
                                "1. Answer the user's queries directly, concisely, and accurately using the research findings above.\n"
                                "2. The user will ask queries about these findings without mentioning or copy-pasting the text.\n"
                                "3. If asked for summaries, comparisons, or details, provide clear, concise, and helpful answers.\n"
                            )
                        }]
                    })
                    contents_payload.append({
                        "role": "model",
                        "parts": [{
                            "text": "Understood! I have memorized the complete web research findings. I am ready to answer any questions about the results directly, clearly, and without requiring you to quote or repeat anything."
                        }]
                    })

                for h in history:
                    role = "user" if h.get("role") == "user" else "model"
                    contents_payload.append({
                        "role": role,
                        "parts": [{"text": str(h.get("text", ""))}]
                    })
                contents_payload.append({
                    "role": "user",
                    "parts": [{"text": message}]
                })

                fallback_prompt = message
                if context:
                    fallback_prompt = (
                        "Recent Web Research Findings:\n"
                        f"{context}\n\n"
                        f"User Query: {message}\n\n"
                        "Please answer the user query directly and accurately using the findings above."
                    )

                for model_name in models_to_try:
                    try:
                        res = client.models.generate_content(
                            model=model_name,
                            contents=contents_payload
                        )
                        return res.text
                    except Exception as e:
                        try:
                            res = client.models.generate_content(
                                model=model_name,
                                contents=fallback_prompt
                            )
                            return res.text
                        except Exception as e2:
                            last_err = e2
                            continue
                raise last_err

            reply = await asyncio.get_event_loop().run_in_executor(None, call_gemini)
            return JSONResponse({"reply": reply})

        # Otherwise try Groq if GROQ_API_KEY is present
        if groq_key:
            import openai
            def call_groq():
                client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
                messages = []
                if context:
                    messages.append({
                        "role": "system",
                        "content": (
                            "You are an intelligent AI assistant. The user just conducted automated web research using Microsoft Edge. "
                            "Here is the research information retrieved:\n\n"
                            "==================== WEB RESEARCH FINDINGS ====================\n"
                            f"{context}\n"
                            "===============================================================\n\n"
                            "Answer all questions directly, concisely, and accurately based on the findings above without requiring the user to quote or repeat anything."
                        )
                    })
                for h in history:
                    messages.append({"role": "user" if h.get("role") == "user" else "assistant", "content": str(h.get("text", ""))})
                messages.append({"role": "user", "content": message})
                resp = client.chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=messages,
                    temperature=0.7
                )
                return resp.choices[0].message.content

            reply = await asyncio.get_event_loop().run_in_executor(None, call_groq)
            return JSONResponse({"reply": reply})

    except Exception as e:
        err_str = str(e)
        if "403" in err_str and "PERMISSION_DENIED" in err_str:
            guidance = (
                "⚠️ **Google Gemini API: Free Tier Not Enabled on This Project (403)**\n\n"
                "Google returned: `403 PERMISSION_DENIED: The Gemini API free tier is not available for this project.`\n\n"
                "### 🛠️ Quick Solutions:\n\n"
                "**Solution A: Use Groq API (Instant - 30 seconds, No Credit Card, 100% Free)**\n"
                "1. Go to **[console.groq.com/keys](https://console.groq.com/keys)**.\n"
                "2. Sign in with Google / GitHub and click **'Create API Key'**.\n"
                "3. Copy the key (starts with `gsk_...`) and paste into `.env` (or top box on this page):\n"
                "   ```env\n   GROQ_API_KEY=gsk_...\n   ```\n\n"
                "**Solution B: Get a Free Gemini Key with Personal Account**\n"
                "1. Go to **[Google AI Studio](https://aistudio.google.com/app/apikey)** in an incognito window.\n"
                "2. Sign in with a **personal Gmail account**.\n"
                "3. Click **'Create API key'** ➔ **'Create API key in a new project'**.\n"
                "4. Copy the key (starts with `AIzaSy...`) and paste into `.env`:\n"
                "   ```env\n   GOOGLE_API_KEY=AIzaSy...\n   ```\n\n"
                "Save your `.env` file and try asking again!"
            )
            return JSONResponse({"reply": guidance})

        return JSONResponse({
            "error": str(e),
            "reply": f"❌ **Error from API:** {str(e)}"
        }, status_code=500)

async def run_task(request):
    task = request.query_params.get("task", "").strip()
    headless_param = request.query_params.get("headless", "false").lower()
    headless = headless_param == "true"

    if not task:
        async def err_gen():
            yield f"data: {json.dumps({'type': 'error', 'text': 'Task parameter is missing'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    handler = SSELogHandler(queue, loop)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger("browser_use")
    logger.addHandler(handler)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'status', 'text': 'Initializing Edge agent...'})}\n\n"

            llm = get_browser_agent_llm()
            browser = Browser("edge", headless=headless)

            clean_prompt = (
                "SEARCH & BROWSING INSTRUCTIONS:\n"
                "1. If the user request does not specify a website URL, always begin by navigating to Bing: `new_tab('https://www.bing.com')` and searching for the user query.\n"
                "2. If you encounter a CAPTCHA, bot check, or login wall AFTER navigating to a page, pause for 20 seconds so the human can complete it in Microsoft Edge. Do NOT print verification warnings or pause on blank or normal pages.\n"
                "3. Always return a detailed, formatted Markdown summary of your findings at the end of the task with clear bullet points and links. Never end a task with empty output."
            )
            agent = Agent(task=task, llm=llm, browser=browser, extend_system_message=clean_prompt, judge=False)

            async def run_agent():
                return await agent.run()

            agent_task = asyncio.create_task(run_agent())

            while not agent_task.done():
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.2)
                    yield f"data: {json.dumps({'type': 'log', 'text': msg})}\n\n"
                except asyncio.TimeoutError:
                    continue

            while not queue.empty():
                msg = queue.get_nowait()
                yield f"data: {json.dumps({'type': 'log', 'text': msg})}\n\n"

            result = await agent_task

            # Extract final result
            final_text = None
            if result.final_result() and result.final_result().strip():
                final_text = result.final_result().strip()
            elif result.text and result.text.strip():
                final_text = result.text.strip()
            elif result.output and str(result.output).strip() and str(result.output) != "None":
                final_text = str(result.output).strip()
            elif result.messages:
                from browser_use.agent.loop import last_text
                m_text = last_text(result.messages)
                if m_text and m_text.strip():
                    final_text = m_text.strip()

            is_success = (result.status == "completed" and not result.has_errors() and bool(final_text))

            if not final_text:
                err = result.error or ""
                if "402" in str(err) or "quota" in str(err).lower() or "credits" in str(err).lower():
                    final_text = (
                        "⚠️ **Browser-Use Cloud Free Credit Exhausted (402 Quota Limit)**\n\n"
                        "Your $1.00 free credit on Browser-Use Cloud has run out.\n\n"
                        "👉 **Solution:** Add a free API key to `.env` (or use the key box at the top of the page) to keep running unlimited tasks:\n"
                        "- **Groq API (Instant 100% Free):** `GROQ_API_KEY=gsk_...` from [console.groq.com/keys](https://console.groq.com/keys)\n"
                        "- **Google Gemini (Free):** `GOOGLE_API_KEY=AIzaSy...` from [Google AI Studio](https://aistudio.google.com/app/apikey)"
                    )
                    is_success = False
                elif result.status == "error":
                    final_text = f"❌ **Task Error:**\n\n{result.error or 'The browser agent encountered an error.'}"
                    is_success = False
                elif result.status == "timeout":
                    final_text = "⏱️ **Task Timed Out:** The browser task exceeded the execution time limit."
                    is_success = False
                elif result.status == "max_steps":
                    final_text = f"⚠️ **Step Limit Reached:** The agent reached the maximum step limit ({result.steps} steps) without completing the task."
                    is_success = False
                else:
                    final_text = f"⚠️ The agent finished in {result.steps} steps without returning text. Check the Live Action Logs above for details."
                    is_success = False

            yield f"data: {json.dumps({'type': 'result', 'text': final_text, 'success': is_success})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        finally:
            logger.removeHandler(handler)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

async def get_logo(request):
    logo_file = Path("logo.png")
    if not logo_file.exists():
        logo_file = Path(__file__).parent / "logo.png"
    if logo_file.exists():
        return FileResponse(logo_file, media_type="image/png")
    return HTMLResponse(status_code=404)

app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/api/run", run_task),
        Route("/api/chat", api_chat, methods=["POST"]),
        Route("/api/save-key", api_save_key, methods=["POST"]),
        Route("/logo.png", get_logo),
    ]
)

def open_browser():
    """Automatically open the Frontend in Microsoft Edge."""
    import time
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

def main():
    print("=" * 60)
    print("🚀 Starting Browser-Use Web UI on http://127.0.0.1:5000")
    print("✨ Features: Browser Agent (Edge) + Multi-AI Chatbot")
    print("Opening Microsoft Edge automatically...")
    print("=" * 60)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="warning")

if __name__ == "__main__":
    main()
