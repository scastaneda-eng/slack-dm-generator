"""One-time OAuth flow to capture a user's xoxp- token.

Usage:
    python -u auth_user.py --email persona@yourorg.com

The `-u` flag (unbuffered) ensures the OAuth URL prints before the script
blocks on the local callback server — important when you need to copy the
URL into an incognito browser window (see SETUP.md, Step 5).
"""
from __future__ import annotations

import argparse
import http.server
import secrets
import ssl
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import ROOT, audit_log, load_tokens, save_tokens

CERT_DIR = ROOT / ".certs"
CERT_FILE = CERT_DIR / "localhost.pem"
KEY_FILE = CERT_DIR / "localhost.key"
PORT = 3000

USER_SCOPES = ["chat:write"]


def ensure_cert() -> None:
    if CERT_FILE.exists() and KEY_FILE.exists():
        return
    CERT_DIR.mkdir(exist_ok=True)
    print("Generating self-signed cert for https://localhost:3000 ...")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(KEY_FILE), "-out", str(CERT_FILE),
            "-days", "365", "-subj", "/CN=localhost",
        ],
        check=True,
    )


def build_authorize_url(client_id: str, scopes: list[str], state: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id,
        "user_scope": ",".join(scopes),
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"https://slack.com/oauth/v2/authorize?{urllib.parse.urlencode(params)}"


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured: dict = {}

    def log_message(self, format, *args):  # quiet the default access log
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/oauth/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = dict(urllib.parse.parse_qsl(parsed.query))
        CallbackHandler.captured.update(params)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = b"<h2>Authorized.</h2><p>You can close this tab.</p>"
        self.wfile.write(body)


def run_server_until_callback(state: str) -> dict:
    httpd = http.server.HTTPServer(("localhost", PORT), CallbackHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    while not CallbackHandler.captured:
        httpd.handle_request()
    captured = dict(CallbackHandler.captured)
    CallbackHandler.captured.clear()
    if captured.get("state") != state:
        raise RuntimeError("OAuth state mismatch — possible CSRF, aborting.")
    if "error" in captured:
        raise RuntimeError(f"OAuth error: {captured['error']}")
    return captured


def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    resp = requests.post(
        "https://slack.com/api/oauth.v2.access",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    ).json()
    if not resp.get("ok"):
        raise RuntimeError(f"Token exchange failed: {resp.get('error')}")
    return resp


def verify_token_matches_email(token: str, expected_email: str, app_token: str | None) -> tuple[bool, str]:
    """Confirm the captured xoxp- token belongs to the email passed via --email.

    Catches the wrong-user-OAuth trap: if the user authorized in their default
    browser logged in as someone else (e.g. their admin), Slack happily issues
    THAT user's token and we'd silently save it under the wrong email. We
    cross-check by calling auth.test on the new token AND looking up the
    expected email; both must resolve to the same user_id.

    users.lookupByEmail requires `users:read.email`, which the user-scoped
    app does NOT have. So the lookup goes through the bot/app token if
    available; if not, we fall back to comparing auth.test's `user` field to
    the local-part of the email as a best-effort check.
    """
    try:
        actual = WebClient(token=token).auth_test()
    except SlackApiError as e:
        return False, f"auth.test on new token failed: {e.response.get('error')}"
    actual_user_id = actual.get("user_id")
    actual_user_name = actual.get("user", "?")

    if app_token:
        try:
            looked_up = WebClient(token=app_token).users_lookupByEmail(email=expected_email)
            expected_user_id = looked_up["user"]["id"]
        except SlackApiError as e:
            return False, (
                f"users.lookupByEmail({expected_email!r}) via app_token failed: "
                f"{e.response.get('error')}. Cannot verify token<->email match."
            )
        if actual_user_id != expected_user_id:
            return False, (
                f"WRONG USER. Token belongs to {actual_user_name} ({actual_user_id}), "
                f"but you passed --email {expected_email} which is "
                f"{looked_up['user'].get('name', '?')} ({expected_user_id}). "
                f"Re-run in an incognito window logged in as {expected_email}."
            )
        return True, f"verified: {expected_email} -> {actual_user_id} ({actual_user_name})"

    # No app_token configured — best-effort heuristic check.
    local = expected_email.split("@", 1)[0].lower()
    if local not in actual_user_name.lower() and actual_user_name.lower() not in local:
        return False, (
            f"LIKELY WRONG USER (heuristic). Token belongs to {actual_user_name} "
            f"({actual_user_id}), which doesn't look like {expected_email}. "
            f"Re-run in an incognito window logged in as {expected_email}, OR "
            f"add an app_token to tokens.json so we can verify properly via "
            f"users.lookupByEmail."
        )
    return True, (
        f"saved (heuristic match only): {expected_email} -> {actual_user_id} "
        f"({actual_user_name}). Configure app_token for strict verification."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="Email of the user you're authorizing as")
    args = parser.parse_args()

    tokens = load_tokens()
    oauth = tokens.get("oauth") or {}
    client_id = oauth.get("client_id")
    client_secret = oauth.get("client_secret")
    redirect_uri = oauth.get("redirect_uri", "https://localhost:3000/oauth/callback")
    if not client_id or not client_secret or "PASTE" in str(client_id) or "PASTE" in str(client_secret):
        print("Missing or unset oauth.client_id / client_secret in tokens.json", file=sys.stderr)
        print("Copy these from your Slack app's Basic Information page (see SETUP.md, Step 3).", file=sys.stderr)
        return 1

    state = secrets.token_urlsafe(16)
    ensure_cert()
    url = build_authorize_url(client_id, USER_SCOPES, state, redirect_uri)

    print()
    print("=" * 70)
    print(f"Authorize as: {args.email}")
    print("=" * 70)
    print()
    print("OAuth URL:")
    print(f"  {url}")
    print()
    print("IMPORTANT — copy that URL into an INCOGNITO browser window logged in")
    print(f"as {args.email}. Do NOT use your default browser if you're logged in")
    print("there as a different user — Slack will silently grant the wrong user's")
    print("token and the verification step below will reject it.")
    print()
    print("(I'll also try to open your default browser as a convenience — ignore")
    print("it if you don't need it.)")
    print()
    print("Note: your browser will warn about the self-signed cert on localhost —")
    print("click 'advanced -> proceed' to continue.")
    print()
    webbrowser.open(url)

    captured = run_server_until_callback(state)
    result = exchange_code(captured["code"], client_id, client_secret, redirect_uri)

    authed_user = result.get("authed_user") or {}
    user_token = authed_user.get("access_token")
    if not user_token:
        print(f"No user token in response: {result}", file=sys.stderr)
        return 1

    ok, detail = verify_token_matches_email(user_token, args.email, tokens.get("app_token"))
    if not ok:
        print()
        print("!" * 70)
        print("VERIFICATION FAILED — token NOT saved.")
        print("!" * 70)
        print(detail)
        return 2

    tokens.setdefault("users", {})[args.email] = user_token
    save_tokens(tokens)
    audit_log(f":key: User token captured for `{args.email}` ({detail})")
    print()
    print(detail)
    print("Saved to tokens.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
