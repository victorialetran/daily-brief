# Daily Brief Agent

> A scheduled AI agent that triages my inbox and curates a personalized morning brief across the three contexts I want to stay sharp on — my PM work, my AI fluency, and the family business I help modernize.

Quick Demo - https://github.com/user-attachments/assets/539a34d4-2638-4eb5-951a-6755547735e9

## Why I built this

I wear three hats as a PM:

- **PowerPoint at Microsoft** by day — I need to track presentation and productivity AI broadly, both for competitive context and to keep my own product thinking sharp.
- **AI fluency on the side** — I want to stay current on what the leading AI products are shipping, and use side-project ideas to keep my craft fresh.
- **My parents' beauty/barber school in San Jose** — I help them think through how AI and small-business tools could modernize the school's operations and marketing.

Each context has its own news diet, and I was burning 30 minutes every morning bouncing between newsletters and the open web to keep up.

This agent is the morning brief I always wished I had: it knows my three contexts, reads my Gmail, scans the web, and produces a single self-contained HTML page with three labeled sections summarizing what matters today.

## What it does, in five steps

1. A cron job on my Mac triggers `daily_brief.py` each weekday morning.
2. The script reads the last 24 hours of unread email via the Gmail API (sender, subject, snippet — no message bodies leave my machine).
3. It starts a session with a pre-configured **Managed Agent** on Anthropic.
4. The agent's system prompt is structured around my three hats. It searches the web for relevant releases per hat, then writes a styled HTML brief.
5. The HTML is downloaded back to my Mac and (next iteration) auto-published to GitHub Pages.

## Architecture

| Component | Choice | Why |
|---|---|---|
| **Agent runtime** | [Anthropic Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) with Claude Opus 4.7 | The agent loop runs server-side in an Anthropic-managed sandbox, so my laptop sleeping doesn't kill the run mid-flight. Persistent agent config (versioned) means I can iterate on the prompt without redeploying any infrastructure. |
| **Gmail access** | Local pre-fetch with `google-api-python-client` | I considered an MCP server but the agent doesn't need to *write* to Gmail — just read metadata. Pre-fetching kept the credential surface smaller and the architecture simpler. |
| **Scheduling** | `cron` (local, weekdays at 7 AM) | Simplest thing that works for now. GitHub Actions migration is the next step so it can run when my laptop is closed. |
| **Output** | Self-contained HTML, no external CSS/JS | One file, no build step, opens anywhere. |

```
cron (7am)
  └─> daily_brief.py
        ├─ Gmail API ─────> inbox metadata
        └─> Anthropic Managed Agent (Claude Opus 4.7)
              ├─ web_search × N (per hat)
              ├─ bash / read / write tools (sandboxed)
              └─> /mnt/session/outputs/index.html
                    └─> downloaded to ./site/index.html
```

## The system prompt — three-hats radar

The system prompt is the actual product. A few moves that came out of iteration on real output:

**1. Operator context up front.** The prompt names my three contexts explicitly — without it, the agent produced generic AI news rather than personalized signal.

**2. Inbox items lead with the takeaway, not the email subject line.** My first version produced "Subject: The AI paradox..." with the substance buried as commentary below. Useless at 7 AM. Now: the bold heading is the takeaway ("PMs are net winners as agents proliferate"), the email metadata is small and muted below it.

**3. Explicit link rules.** First-run output included scraped `/cdn-cgi/email-protection` anchors that 404 when the HTML is viewed locally. The prompt now mandates absolute URLs with `target="_blank"` and forbids relative-path or obfuscated anchors.

**4. Three distinct visual sections.** Each section (Inbox, Radar, News) gets its own accent color (terracotta / amber / sage) so the brief scans as three discrete chunks rather than a wall of text.

See [`agent.yaml`](./agent.yaml) for the current prompt.

## Cost

Roughly **$0.20–0.35 per run** on Claude Opus 4.7 with adaptive thinking and 6–10 web searches. At ~20 runs/month (weekday cron), that's **$4–7/month** — comfortably within a hobby budget.

## Setup

If you want to run this yourself:

1. Create an Anthropic API key at [console.anthropic.com](https://console.anthropic.com) and add a few dollars of credit.
2. Create a Google Cloud project, enable the Gmail API, create OAuth credentials of type "Desktop app," download as `gmail_credentials.json`.
3. Clone this repo, copy `.env.example` → `.env`, paste your Anthropic API key in.
4. Set up the Python environment:
   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
5. Create the agent and environment on Anthropic's side (one-time):
   ```sh
   .venv/bin/python setup_agent.py
   ```
6. Run it:
   ```sh
   .venv/bin/python daily_brief.py
   ```
7. After tweaking `agent.yaml`, push prompt changes to your agent with:
   ```sh
   .venv/bin/python update_agent.py
   ```

## What's next

- [ ] Auto-publish to GitHub Pages so the brief gets a stable URL
- [ ] Move scheduling from local cron to GitHub Actions (run when laptop is closed)
- [ ] Add a "buried lede" detector — flag items that are more important than their headline suggests
- [ ] Multi-recipient support (e.g. weekly digest for my parents in plain language)

## Built with

- [Anthropic Claude API](https://platform.claude.com) — Managed Agents (beta) + Claude Opus 4.7
- [Anthropic Claude Code](https://claude.com/claude-code) — paired with Claude Code throughout the build and iteration
- Python 3, Google Workspace APIs
