"""Delete DMs previously sent by personas.

Reads a manifest written by send_dms_as_users.py — a JSON file with a `sent`
list, where each entry has `sender_email`, `recipient_user_id`, and `ts`.

The probe-and-delete trick: a persona's xoxp- token has chat:write but not
im:read/im:write, so we cannot look up the DM channel ID directly. Instead
we post a one-character throwaway via chat.postMessage, capture the channel
ID from the response, then chat.delete both the throwaway and the target ts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from slack_sdk.errors import SlackApiError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import audit_log, user_client  # noqa: E402


def delete_one(sender_email: str, recipient_user_id: str, target_ts: str) -> tuple[bool, str]:
    client = user_client(sender_email)

    try:
        probe = client.chat_postMessage(channel=recipient_user_id, text=".")
    except SlackApiError as e:
        return False, f"probe post failed: {e.response.get('error')}"
    channel = probe["channel"]
    probe_ts = probe["ts"]

    target_err = None
    try:
        client.chat_delete(channel=channel, ts=target_ts)
    except SlackApiError as e:
        target_err = e.response.get("error")

    try:
        client.chat_delete(channel=channel, ts=probe_ts)
    except SlackApiError as e:
        if target_err is None:
            return False, f"target deleted but probe cleanup failed: {e.response.get('error')}"

    if target_err:
        return False, f"chat.delete failed: {target_err}"
    return True, channel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON from send_dms_as_users.py")
    args = parser.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)

    failures = 0
    for entry in manifest.get("sent", []):
        sender = entry["sender_email"]
        recipient = entry["recipient_user_id"]
        ts = entry["ts"]
        try:
            ok, info = delete_one(sender, recipient, ts)
        except RuntimeError as e:
            print(f"[skip] {sender}: {e}", file=sys.stderr)
            failures += 1
            continue
        if ok:
            print(f"[deleted] {sender} ts={ts} channel={info}")
            audit_log(
                f":wastebasket: DM deleted — {sender} -> <@{recipient}> "
                f"(`ts={ts}`, channel=`{info}`)"
            )
        else:
            print(f"[fail] {sender} ts={ts} — {info}", file=sys.stderr)
            audit_log(
                f":warning: DM delete failed — {sender} -> <@{recipient}> "
                f"(`ts={ts}`) — {info}"
            )
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
