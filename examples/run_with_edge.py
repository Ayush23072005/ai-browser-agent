"""
Browser-Use with Microsoft Edge Example
---------------------------------------
This script runs a Browser-Use agent using your local Microsoft Edge browser.

Before running:
1. Make sure you set at least one LLM API key in your `.env` file:
   - GOOGLE_API_KEY (Gemini)
   - OPENAI_API_KEY (ChatGPT / GPT-4o)
   - ANTHROPIC_API_KEY (Claude)
   - BROWSER_USE_API_KEY (Browser-Use Cloud default)
2. Run this script using the virtual environment:
   .\venv\Scripts\python.exe run_edge.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from browser_use import Agent, Browser, ChatGoogle, ChatOpenAI, ChatAnthropic

def get_llm():
    """Detect which API key is configured and return the appropriate LLM."""
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        print("Using Google Gemini model (gemini-2.0-flash)...")
        return ChatGoogle("gemini-2.0-flash")
    elif os.getenv("OPENAI_API_KEY"):
        print("Using OpenAI model (gpt-4o)...")
        return ChatOpenAI("gpt-4o")
    elif os.getenv("ANTHROPIC_API_KEY"):
        print("Using Anthropic model (claude-3-5-sonnet-latest)...")
        return ChatAnthropic("claude-3-5-sonnet-latest")
    elif os.getenv("BROWSER_USE_API_KEY"):
        print("Using default Browser-Use model (bu-4.0)...")
        return None  # Defaults to bu-4.0
    try:
        from browser_use.auth import browser_use_api_key
        if browser_use_api_key():
            print("Using signed-in Browser-Use model (bu-4.0)...")
            return None
    except Exception:
        pass
    else:
        print("\n[!] No LLM API key found in .env!")
        print("Please open the .env file in this directory and set one of the following:")
        print("  - GOOGLE_API_KEY=your_key_here     (Get at: https://aistudio.google.com/app/apikey)")
        print("  - OPENAI_API_KEY=your_key_here     (Get at: https://platform.openai.com/api-keys)")
        print("  - ANTHROPIC_API_KEY=your_key_here  (Get at: https://console.anthropic.com/)")
        print("  - BROWSER_USE_API_KEY=your_key_here(Get $1 free credit at: https://cloud.browser-use.com/new-api-key)")
        sys.exit(1)

def main():
    llm = get_llm()

    # Define your task
    task = "Navigate to https://www.bing.com, search for 'Microsoft Edge AI', and summarize the top result."

    print(f"\n[+] Starting Browser-Use Agent with Microsoft Edge...")
    print(f"[+] Task: {task}\n")

    # Launch agent with Microsoft Edge (visible window: headless=False)
    agent = Agent(
        task=task,
        llm=llm,
        browser=Browser("edge", headless=False),
    )

    result = agent.run_sync()

    print("\n" + "=" * 50)
    print("Agent Final Result:")
    print("=" * 50)
    print(result.final_result())

if __name__ == "__main__":
    main()
