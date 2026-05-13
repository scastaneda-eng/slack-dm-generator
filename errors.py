"""Translate raw Slack API error codes into human-readable messages.

Slack returns short snake_case codes like `not_in_channel` or `token_revoked`.
This helper maps the codes the user is most likely to hit when seeding/deleting
demo DMs into actionable hints. Unknown codes pass through with the raw code.
"""
from __future__ import annotations

from slack_sdk.errors import SlackApiError

_FRIENDLY = {
    "ratelimited": "Slack rate-limited the request. The retry decorator should handle this; if you see it bare, raise the retry count.",
    "token_revoked": "Token was revoked. Re-run `auth_user.py --email <email>` for this persona.",
    "invalid_auth": "Slack rejected the token. It may have been rotated or the workspace was reinstalled.",
    "account_inactive": "Persona's Slack account is deactivated. Reactivate the user (or pick a different persona).",
    "user_not_found": "Recipient user ID not found in this workspace. Double-check it's a U... ID from this Slack org.",
    "channel_not_found": "DM channel not found. The recipient may have been deleted, or the channel ID is stale.",
    "cant_dm_bot": "Personas can't DM bots. Pick a human recipient.",
    "message_not_found": "The target message no longer exists (already deleted, or the timestamp is wrong).",
    "missing_scope": "The token is missing a scope. Check manifest.json and reinstall the app.",
    "not_authed": "No token sent. Likely a bug in token loading — check tokens.json.",
    "no_permission": "Token has scopes but Slack denied this specific action (org-level restrictions).",
}


def friendly_slack_error(error: SlackApiError) -> str:
    """Return a human-readable message for a SlackApiError."""
    code = error.response.get("error", "unknown")
    hint = _FRIENDLY.get(code)
    return f"{code} — {hint}" if hint else code
