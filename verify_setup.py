"""Diagnostic — confirm tokens.json is wired up correctly.

Run this any time you want a yes/no answer to "am I ready to send DMs?".

Checks:
  1. tokens.json exists and is valid JSON
  2. oauth.client_id and oauth.client_secret are present and non-placeholder
  3. For each entry in tokens["users"]: auth.test succeeds AND (if app_token
     is configured) the user_id matches users.lookupByEmail(email)
  4. If app_token is set: auth.test on it; verify audit_channel_id resolves
     via conversations.info

Exit code is 0 if all checks pass, non-zero otherwise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

ROOT = Path(__file__).resolve().parent
TOKENS_PATH = ROOT / "tokens.json"


def fail(msg: str) -> None:
    print(f"  FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"  OK:   {msg}")


def main() -> int:
    print(f"Reading {TOKENS_PATH} ...")
    if not TOKENS_PATH.exists():
        print(f"  FAIL: tokens.json not found. Copy tokens.example.json -> tokens.json and fill it in.")
        return 1
    try:
        tokens = json.loads(TOKENS_PATH.read_text())
    except json.JSONDecodeError as e:
        print(f"  FAIL: tokens.json is not valid JSON: {e}")
        return 1
    ok("tokens.json parsed")

    failures = 0

    print("\nChecking oauth.client_id / client_secret ...")
    oauth = tokens.get("oauth") or {}
    cid = oauth.get("client_id", "")
    csec = oauth.get("client_secret", "")
    if not cid or "PASTE" in str(cid):
        fail("oauth.client_id missing or still a placeholder")
        failures += 1
    else:
        ok(f"oauth.client_id present ({len(cid)} chars)")
    if not csec or "PASTE" in str(csec):
        fail("oauth.client_secret missing or still a placeholder")
        failures += 1
    else:
        ok(f"oauth.client_secret present ({len(csec)} chars)")

    app_token = tokens.get("app_token") or None

    print("\nChecking persona user tokens ...")
    users = tokens.get("users") or {}
    real_users = {k: v for k, v in users.items() if not k.startswith("_") and isinstance(v, str) and v}
    if not real_users:
        print("  (none captured yet — run `.venv/bin/python -u auth_user.py --email <email>`)")
    for email, token in real_users.items():
        try:
            r = WebClient(token=token).auth_test()
        except SlackApiError as e:
            fail(f"{email}: auth.test rejected — {e.response.get('error')}")
            failures += 1
            continue
        actual_id = r.get("user_id")
        actual_name = r.get("user")
        if app_token:
            try:
                lu = WebClient(token=app_token).users_lookupByEmail(email=email)
                expected_id = lu["user"]["id"]
            except SlackApiError as e:
                fail(f"{email}: users.lookupByEmail via app_token failed — {e.response.get('error')}")
                failures += 1
                continue
            if expected_id != actual_id:
                fail(
                    f"{email}: token belongs to {actual_name} ({actual_id}), "
                    f"but email resolves to {expected_id}. Re-run auth_user.py "
                    f"in incognito as {email}."
                )
                failures += 1
                continue
            ok(f"{email} -> {actual_id} ({actual_name}) [verified via lookupByEmail]")
        else:
            ok(f"{email} -> {actual_id} ({actual_name}) [auth.test only — add app_token for strict verification]")

    if app_token:
        print("\nChecking optional audit logging ...")
        try:
            r = WebClient(token=app_token).auth_test()
            ok(f"app_token valid (bot {r.get('user')} in team {r.get('team')})")
        except SlackApiError as e:
            fail(f"app_token rejected by auth.test — {e.response.get('error')}")
            failures += 1
        channel = tokens.get("audit_channel_id")
        if channel:
            try:
                WebClient(token=app_token).conversations_info(channel=channel)
                ok(f"audit_channel_id {channel} resolves")
            except SlackApiError as e:
                fail(f"audit_channel_id {channel} not accessible — {e.response.get('error')}")
                failures += 1
        else:
            print("  (audit_channel_id not set — audit_log() will silently no-op)")
    else:
        print("\nAudit logging not configured (app_token unset). That's fine — it's optional.")

    print()
    if failures:
        print(f"FAIL — {failures} check(s) failed. Fix the items above before sending DMs.")
        return 1
    print("READY — all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
