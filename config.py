"""Shared config: token loading, Slack client init, optional audit logging."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

ROOT = Path(__file__).resolve().parent
TOKENS_PATH = ROOT / "tokens.json"


def load_tokens() -> dict[str, Any]:
    with TOKENS_PATH.open() as f:
        return json.load(f)


def save_tokens(tokens: dict[str, Any]) -> None:
    with TOKENS_PATH.open("w") as f:
        json.dump(tokens, f, indent=2)
        f.write("\n")


def user_client(email: str) -> WebClient:
    """Return a WebClient using the persona's xoxp- user token."""
    tokens = load_tokens()
    token = tokens.get("users", {}).get(email)
    if not token:
        raise RuntimeError(
            f"No user token for {email!r} in tokens.json. "
            f"Run `python auth_user.py --email {email}` first."
        )
    return WebClient(token=token)


def audit_log(message: str) -> None:
    """Post a timestamped entry to the audit channel, if configured.

    No-ops silently if `app_token` or `audit_channel_id` is missing from
    tokens.json. Audit logging is opt-in (see SETUP.md, Step 8).
    """
    tokens = load_tokens()
    app_token = tokens.get("app_token")
    channel = tokens.get("audit_channel_id")
    if not app_token or not channel:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    try:
        WebClient(token=app_token).chat_postMessage(
            channel=channel, text=f"`{timestamp}` {message}"
        )
    except SlackApiError as e:
        print(f"[audit_log failed] {e.response['error']}: {message}")
