"""Send DMs as different personas to a single recipient.

Reads a JSON config file with a list of messages, each specifying:
  - sender_email: must match a key in tokens.json["users"]
  - recipient_user_id: Slack user ID (starts with U) of the DM recipient
  - text: message body

Optionally writes a manifest of (sender_email, channel_id, ts) tuples that
delete_dms.py can read to clean up the seeded DMs later.

Example config:
    {
      "messages": [
        {
          "sender_email": "boss@yourorg.com",
          "recipient_user_id": "U01ABCDEFGH",
          "text": "Quick one — can you send me the latest forecast?"
        }
      ]
    }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from slack_sdk.errors import SlackApiError

# Make `from config import ...` and `from retry import ...` work whether run
# from repo root or examples/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import audit_log, user_client  # noqa: E402
from errors import friendly_slack_error  # noqa: E402
from retry import retry_on_rate_limit  # noqa: E402

# Slack user IDs are uppercase alphanumeric, prefixed with U or W (workspace).
USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{8,}$")
# Slack rejects messages over 40K chars but the API error is opaque; cap at
# 5K with a friendly message — long demo prep DMs are rarely intentional and
# usually a stray paste from the wrong source.
MAX_TEXT_CHARS = 5000


@retry_on_rate_limit()
def send_one(sender_email: str, recipient_user_id: str, text: str) -> dict:
    if not USER_ID_RE.match(recipient_user_id):
        raise RuntimeError(
            f"recipient_user_id {recipient_user_id!r} doesn't look like a Slack user ID "
            f"(expected something like U01ABCDEFGH)"
        )
    if len(text) > MAX_TEXT_CHARS:
        raise RuntimeError(
            f"text is {len(text)} chars (limit {MAX_TEXT_CHARS}). Likely an "
            f"unintended paste — trim the message in your config file."
        )
    client = user_client(sender_email)
    resp = client.chat_postMessage(channel=recipient_user_id, text=text)
    return {
        "sender_email": sender_email,
        "recipient_user_id": recipient_user_id,
        "channel_id": resp["channel"],
        "ts": resp["ts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to messages JSON config")
    parser.add_argument("--manifest", help="Optional path to write a manifest of sent messages")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    sent = []
    failures = 0
    for msg in config.get("messages", []):
        try:
            entry = send_one(msg["sender_email"], msg["recipient_user_id"], msg["text"])
        except (SlackApiError, RuntimeError) as e:
            err = friendly_slack_error(e) if isinstance(e, SlackApiError) else str(e)
            print(f"[fail] {msg.get('sender_email')!r}: {err}", file=sys.stderr)
            audit_log(
                f":warning: DM seed failed — {msg.get('sender_email')} -> "
                f"<@{msg.get('recipient_user_id')}> error=`{err}`"
            )
            failures += 1
            continue
        sent.append(entry)
        print(f"[sent] {entry['sender_email']} -> <@{entry['recipient_user_id']}> ts={entry['ts']}")
        audit_log(
            f":inbox_tray: DM seeded — {entry['sender_email']} -> "
            f"<@{entry['recipient_user_id']}> (`ts={entry['ts']}`)"
        )

    if args.manifest:
        with open(args.manifest, "w") as f:
            json.dump({"sent": sent}, f, indent=2)
        print(f"\nManifest written to {args.manifest}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
