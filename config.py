"""Shared config: token loading, Slack client init, optional audit logging."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

ROOT = Path(__file__).resolve().parent
TOKENS_PATH = ROOT / "tokens.json"


def load_tokens() -> dict[str, Any]:
    if not TOKENS_PATH.exists():
        return {}
    with TOKENS_PATH.open() as f:
        return json.load(f)


def save_tokens(tokens: dict[str, Any]) -> None:
    with TOKENS_PATH.open("w") as f:
        json.dump(tokens, f, indent=2)
        f.write("\n")


# Env vars that override the corresponding tokens.json entries when set.
# Lets CI / secret managers inject credentials without committing them to
# tokens.json. Code that needs these values should call get_oauth_config(),
# get_app_token(), or get_audit_channel_id() instead of poking tokens.json
# directly.
_ENV_OAUTH_CLIENT_ID = "SLACK_CLIENT_ID"
_ENV_OAUTH_CLIENT_SECRET = "SLACK_CLIENT_SECRET"
_ENV_APP_TOKEN = "SLACK_APP_TOKEN"
_ENV_AUDIT_CHANNEL = "SLACK_AUDIT_CHANNEL_ID"


def get_oauth_config() -> dict[str, str | None]:
    """Return OAuth credentials. Env vars win over tokens.json when both set."""
    oauth = load_tokens().get("oauth") or {}
    return {
        "client_id": os.environ.get(_ENV_OAUTH_CLIENT_ID) or oauth.get("client_id"),
        "client_secret": os.environ.get(_ENV_OAUTH_CLIENT_SECRET) or oauth.get("client_secret"),
        "redirect_uri": oauth.get("redirect_uri", "https://localhost:3000/oauth/callback"),
    }


def get_app_token() -> str | None:
    """App-level Slack token (xapp-/xoxb-) for audit logging + lookups."""
    return os.environ.get(_ENV_APP_TOKEN) or load_tokens().get("app_token")


def get_audit_channel_id() -> str | None:
    return os.environ.get(_ENV_AUDIT_CHANNEL) or load_tokens().get("audit_channel_id")


def user_client(email: str) -> WebClient:
    """Return a WebClient using the persona's xoxp- user token."""
    tokens = load_tokens()
    token = tokens.get("users", {}).get(email)
    if not token:
        raise RuntimeError(
            f"No user token for {email!r} in tokens.json. "
            f"Run `.venv/bin/python -u auth_user.py --email {email}` first."
        )
    return WebClient(token=token)


def audit_log(message: str) -> None:
    """Post a timestamped entry to the audit channel, if configured.

    No-ops silently if `app_token` or `audit_channel_id` is unavailable
    (either not in tokens.json or via env vars). Audit logging is opt-in
    (see SETUP.md, Step 8).
    """
    app_token = get_app_token()
    channel = get_audit_channel_id()
    if not app_token or not channel:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    try:
        WebClient(token=app_token).chat_postMessage(
            channel=channel, text=f"`{timestamp}` {message}"
        )
    except SlackApiError as e:
        print(f"[audit_log failed] {e.response['error']}: {message}")
