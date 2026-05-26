"""Push the local agent.yaml to your agent on Anthropic.

Run this whenever you edit agent.yaml (e.g. tweak the system prompt). Each
update creates a new immutable version on Anthropic's side; future sessions
automatically use the latest.
"""

import os
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv

load_dotenv(".env")
client = anthropic.Anthropic()
AGENT_ID = os.environ["AGENT_ID"]

config = yaml.safe_load(Path("agent.yaml").read_text())

# Fetch current version for optimistic locking — the API uses this to detect
# concurrent edits. If you've edited via another tool since this script last
# ran, the update will fail safely instead of clobbering.
current = client.beta.agents.retrieve(AGENT_ID)

updated = client.beta.agents.update(
    agent_id=AGENT_ID,
    version=current.version,
    name=config["name"],
    model=config["model"],
    system=config["system"],
    tools=config["tools"],
)

print(f"✓ Updated agent {updated.id}")
print(f"  New version: {updated.version}")
print(f"  System prompt: {len(updated.system)} chars")
print(f"  Tools: {[t.type for t in updated.tools]}")
