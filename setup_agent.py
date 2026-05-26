"""One-time setup: create the Daily Brief agent + environment on Anthropic.

Run this ONCE, after putting your ANTHROPIC_API_KEY into .env.
It creates the agent and environment, then appends their IDs to .env so
daily_brief.py can find them.
"""

import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY in .env before running this.", file=sys.stderr)
    sys.exit(1)

env_path = Path(".env")
existing = env_path.read_text() if env_path.exists() else ""

if "AGENT_ID=" in existing and "agent_" in existing:
    print(
        "It looks like setup has already run (.env has AGENT_ID).\n"
        "If you really want to create a new agent, remove the AGENT_ID and "
        "ENV_ID lines from .env first.",
        file=sys.stderr,
    )
    sys.exit(1)

client = anthropic.Anthropic()

print("Creating environment...")
environment = client.beta.environments.create(
    name="daily-brief-env",
    config={"type": "cloud", "networking": {"type": "unrestricted"}},
)
print(f"  ENV_ID = {environment.id}")

print("Creating agent...")
agent = client.beta.agents.create(
    name="Daily Brief Agent",
    model="claude-opus-4-7",
    system=(
        "You generate a daily morning brief for the user. Each kickoff "
        "message includes a JSON summary of their last 24 hours of unread "
        "email (sender, subject, snippet).\n\n"
        "Your job each run:\n"
        "  1. Identify the small number of inbox items that genuinely need "
        "attention today. Group them as \"Action needed\", \"FYI\", and "
        "\"Low priority\".\n"
        "  2. Use web_search to find 3-5 of the most important developments "
        "in tech and AI from the past 24 hours that the user should know "
        "about. Cite sources.\n"
        "  3. Produce a single self-contained HTML document at "
        "/mnt/session/outputs/index.html. No external CSS or JS. Clean, "
        "readable design — warm typography, generous spacing, "
        "mobile-friendly. Date at the top. Brief over verbose."
    ),
    tools=[{"type": "agent_toolset_20260401"}],
)
print(f"  AGENT_ID = {agent.id}")

with env_path.open("a") as f:
    f.write(f"\nAGENT_ID={agent.id}\n")
    f.write(f"ENV_ID={environment.id}\n")

print(f"\n✓ Wrote IDs to {env_path.resolve()}")
print("Next: run `.venv/bin/python daily_brief.py` to generate your first brief.")
