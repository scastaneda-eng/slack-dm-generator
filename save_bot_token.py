"""Save an already-issued bot xoxb- token into tokens.json.

Use after reinstalling the app — paste the new Bot User OAuth Token from the
"Install App" page. Token is hidden during input via getpass.
"""
from __future__ import annotations

import getpass
import sys

from slack_sdk import WebClient

from config import audit_log, load_tokens, save_tokens


def main() -> int:
    token = getpass.getpass("Paste the Bot User OAuth Token (xoxb-...) and press Enter: ").strip()
    if not token.startswith("xoxb-"):
        print("That doesn't look like a bot token (should start with 'xoxb-').", file=sys.stderr)
        return 1

    print("Validating token with Slack...")
    resp = WebClient(token=token).auth_test()
    if not resp.get("ok"):
        print(f"Slack rejected the token: {resp.get('error')}", file=sys.stderr)
        return 1

    bot_user_id = resp.get("bot_id")
    if not bot_user_id:
        print(
            "That token authenticated as a user, not a bot — auth.test returned no bot_id. "
            "Make sure you're pasting the Bot User OAuth Token (under 'Install App'), "
            "not the User OAuth Token.",
            file=sys.stderr,
        )
        return 1
    user_name = resp.get("user", "?")
    team = resp.get("team", "?")
    enterprise = resp.get("enterprise_id") or resp.get("enterprise") or "(none)"

    print(f"  bot:        {user_name} ({bot_user_id})")
    print(f"  team:       {team}")
    print(f"  enterprise: {enterprise}")
    confirm = input("Save this as app_token? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return 1

    tokens = load_tokens()
    tokens["app_token"] = token
    save_tokens(tokens)
    # audit_log uses the new app_token now that it's saved
    audit_log(f":key: Bot token rotated and saved (bot_id `{bot_user_id}`)")
    print("\nSaved. Bot token is live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
