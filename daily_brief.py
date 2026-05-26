"""Daily Brief Agent — runtime script. Run via cron, e.g. `0 7 * * 1-5 ...`"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

AGENT_ID = os.environ["AGENT_ID"]
ENV_ID = os.environ["ENV_ID"]
GMAIL_TOKEN = os.environ.get("GMAIL_TOKEN_FILE", "gmail_token.json")
GMAIL_CREDS = os.environ.get("GMAIL_CREDS_FILE", "gmail_credentials.json")
OUTPUT_DIR = Path(os.environ.get("BRIEF_OUTPUT_DIR", "site"))
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

POLL_SECONDS = 5
MAX_WAIT_MINUTES = 30


def gmail_service():
    creds = None
    if Path(GMAIL_TOKEN).exists():
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(
                GMAIL_CREDS, SCOPES
            ).run_local_server(port=0)
        Path(GMAIL_TOKEN).write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def fetch_inbox():
    gmail = gmail_service()
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y/%m/%d")
    refs = gmail.users().messages().list(
        userId="me", q=f"is:unread after:{since}", maxResults=50
    ).execute().get("messages", [])

    inbox = []
    for ref in refs:
        msg = gmail.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["From", "Subject"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        inbox.append({
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "snippet": msg.get("snippet", ""),
        })
    return inbox


def run():
    client = anthropic.Anthropic()
    inbox = fetch_inbox()
    today = datetime.now().strftime("%A, %B %d, %Y")
    print(f"Fetched {len(inbox)} unread email(s) from the last 24h.", file=sys.stderr)

    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENV_ID,
        title=f"Daily brief — {today}",
    )
    print(f"Session: {session.id}", file=sys.stderr)

    kickoff = (
        f"Today is {today}. Generate today's brief.\n\n"
        f"News focus: tech and AI developments from the past 24 hours.\n\n"
        f"My inbox (last 24h unread, JSON):\n"
        f"```json\n{json.dumps(inbox, indent=2)}\n```\n\n"
        f"Write the HTML to /mnt/session/outputs/index.html."
    )
    client.beta.sessions.events.send(
        session_id=session.id,
        events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": kickoff}],
        }],
    )

    # Poll for progress. This is more robust than the SSE stream — each
    # request is short, so a brief network drop or laptop sleep just means
    # the next poll picks up where we left off.
    #
    # We detect "session done" by watching for a session.status_idle EVENT
    # with a terminal stop_reason. sessions.retrieve().status alone is not
    # reliable: it can show "idle" transiently between tool batches, and
    # stop_reason is often null on the retrieved snapshot even at true idle.
    deadline = time.monotonic() + MAX_WAIT_MINUTES * 60
    seen_event_ids = set()
    done = False

    while time.monotonic() < deadline and not done:
        try:
            events = sorted(
                client.beta.sessions.events.list(session_id=session.id),
                key=lambda e: getattr(e, "processed_at", None) or "",
            )
        except Exception as e:
            print(f"\n[poll error: {e}; retrying]", file=sys.stderr)
            time.sleep(POLL_SECONDS)
            continue

        for ev in events:
            if ev.id in seen_event_ids:
                continue
            seen_event_ids.add(ev.id)

            if ev.type == "agent.message":
                for block in ev.content:
                    if getattr(block, "type", None) == "text":
                        print(block.text, end="", flush=True)
            elif ev.type == "session.status_terminated":
                print("\n[session terminated]", file=sys.stderr)
                return
            elif ev.type == "session.status_idle":
                stop = getattr(ev, "stop_reason", None)
                stop_type = getattr(stop, "type", None) if stop else None
                if stop_type == "requires_action":
                    # Shouldn't happen for this agent (no custom tools).
                    print(f"\n[agent waiting on user input: {stop}]", file=sys.stderr)
                    return
                # Terminal idle: end_turn / retries_exhausted / unknown — done.
                done = True
                break

        if not done:
            time.sleep(POLL_SECONDS)

    if not done:
        print(f"\n[timed out after {MAX_WAIT_MINUTES} min]", file=sys.stderr)
        return

    # The HTML file appears in files.list() a few seconds AFTER status_idle
    # fires (indexing lag, observed up to ~10s). Retry until it shows up.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_deadline = time.monotonic() + 30
    html_files = []
    while time.monotonic() < file_deadline:
        html_files = [
            f for f in client.beta.files.list(
                scope_id=session.id,
                betas=["managed-agents-2026-04-01"],
            )
            if f.filename.endswith(".html")
        ]
        if html_files:
            break
        time.sleep(2)

    if not html_files:
        print("\n⚠ No HTML output found after 30s of retrying.", file=sys.stderr)
        return

    f = html_files[0]
    out = OUTPUT_DIR / "index.html"
    client.beta.files.download(f.id).write_to_file(str(out))
    print(f"\n✓ Saved {out.resolve()} ({f.size_bytes} bytes)", file=sys.stderr)


if __name__ == "__main__":
    run()
