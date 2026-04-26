# slack-dm-generator — Setup

This toolkit lets you **send and delete DMs as real users** in your Slack
demo org. Useful for seeding a "lived-in" inbox before a demo.

Setup is one-time, ~15 minutes.

---

## Prerequisites

- **Slack admin** in your demo org (you need to install an app there).
- **Python 3.12** — the macOS system Python (3.9) is too old.
  ```bash
  brew install python@3.12
  ```
  > **On Windows?** Download the Python 3.12 installer from
  > https://www.python.org/downloads/ and **check "Add python.exe to PATH"**
  > on the first installer screen. When you hit a step below whose command
  > starts with `source`, `cp`, or `python3.12`, swap it for the Windows
  > equivalent in the [Windows commands](#windows-commands) table at the
  > bottom of this file. Every other command is identical.
- **macOS, Linux, or Windows** — the toolkit generates its own OAuth cert
  using a pure-Python library, so you don't need `openssl` installed.

---

## Step 1 — Create the Slack app

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**.
2. Name it anything (e.g., `Demo DM Helper`). Pick your demo workspace.

---

## Step 2 — Configure OAuth

1. In the app settings, go to **OAuth & Permissions**.
2. Under **Redirect URLs**, add:
   ```
   https://localhost:3000/oauth/callback
   ```
   > ⚠ **Must be `https://`** — Slack rejects `http://localhost`. The toolkit
   > generates a self-signed cert for this on first run.
3. Under **User Token Scopes**, add `chat:write`.
   > ℹ `chat:write` is sufficient for both DM **send** and DM **delete**.
   > You don't need `im:read` or `im:write` (counterintuitive but true).
4. Save changes.

---

## Step 3 — Get the OAuth credentials

1. In the app settings, go to **Basic Information**.
2. Under **App Credentials**, copy:
   - **Client ID**
   - **Client Secret** (click "Show")

You'll paste these into `tokens.json` in Step 5.

---

## Step 4 — Set up Python

From the toolkit directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.venv/` is gitignored. Activate it (`source .venv/bin/activate`) every new
terminal session.

---

## Step 5 — Create `tokens.json`

```bash
cp tokens.example.json tokens.json
```

Open `tokens.json` and fill in `oauth.client_id` and `oauth.client_secret`
from Step 3. Leave everything else as-is for now.

> ⚠ **Never paste tokens into a chat with Claude Code.** Always use the
> local scripts (`auth_user.py` for user tokens, `save_bot_token.py` for the
> optional bot token). Pasting tokens into chat re-leaks them.

---

## Step 6 — Capture per-persona tokens

For each user you want to impersonate (e.g., a CRO persona, a customer
persona, a deal-desk persona):

```bash
python -u auth_user.py --email persona@yourorg.com
```

> ⚠ Use `python -u` (unbuffered) so the OAuth URL prints **before** the
> script blocks waiting for the callback.

The script will print an OAuth URL. **STOP** — read this carefully:

> ⚠ **Critical: open the URL in an INCOGNITO window** logged in as the
> target persona. Do NOT use your default browser if you're logged in there
> as a different user (e.g., your admin account). If you do, Slack will
> silently grant the wrong user's token.

> ℹ The script also tries to open your default browser as a convenience —
> ignore that tab if it goes to the wrong account.

> ℹ Your browser will warn about the self-signed cert. Click
> **advanced → proceed** to continue.

After you authorize, the script:
1. Captures the `xoxp-` token from the OAuth callback.
2. Calls `auth.test` on the new token to find out which user it actually
   belongs to.
3. (If `app_token` is configured) calls `users.lookupByEmail(email)` to get
   the user ID for the email you passed.
4. **Refuses to save** if those don't match — and tells you to retry in
   incognito.

Repeat for every persona.

---

## Step 7 — Verify

```bash
python verify_setup.py
```

Should print every persona email + matching user ID and end with
`READY — all checks passed.` If anything is flagged, fix it before moving on.

---

## Step 8 — Send a test DM

1. Copy the example config:
   ```bash
   cp examples/send_messages.example.json my_demo.json
   ```
2. Edit `my_demo.json` — replace the `sender_email` (must be one of your
   captured personas) and `recipient_user_id` (the Slack user ID of who
   should receive the DM).
3. Send:
   ```bash
   python examples/send_dms_as_users.py --config my_demo.json --manifest sent.json
   ```
4. Confirm the DM appears in the recipient's Slack.

To clean up:
```bash
python examples/delete_dms.py --manifest sent.json
```

---

## Step 9 (optional) — Audit logging

If you want every send/delete logged automatically to a Slack channel:

1. Create a dedicated channel in your demo org (e.g., `#demo-audit-log`).
   Right-click → **View channel details** → copy the channel ID at the
   bottom (starts with `C`).
2. In your existing Slack app, go to **OAuth & Permissions** → add **Bot
   Token Scopes**: `chat:write`, `chat:write.public`.
3. Reinstall the app. Copy the new **Bot User OAuth Token** (`xoxb-...`)
   from the **Install App** page.
   > ℹ Reinstalling the app does **not** invalidate already-captured
   > `xoxp-` user tokens.
4. Run:
   ```bash
   python save_bot_token.py
   ```
   Paste the `xoxb-` when prompted (it's hidden via `getpass`).
5. Open `tokens.json` and set `audit_channel_id` to the channel ID from
   step 1.
6. Re-run `python verify_setup.py` — you should now see audit logging
   green.

If you don't do this, audit logging silently no-ops. The toolkit still works.

---

## Token rotation

If you need to rotate (e.g., a token leaked):

| Token | How to rotate |
|---|---|
| `client_secret` | Slack app → Basic Information → Regenerate. Update `tokens.json`. |
| Bot `xoxb-` (audit) | Reinstall app → copy new token → `python save_bot_token.py`. |
| Persona `xoxp-` | Re-run `python -u auth_user.py --email persona@yourorg.com`. |

Reinstalling the app does **not** invalidate existing user (`xoxp-`) tokens.

> ⚠ Never paste rotated tokens into a chat with Claude Code. Always use
> the local scripts.

---

## File reference

| File | Purpose |
|---|---|
| `auth_user.py` | OAuth flow — captures one persona's `xoxp-` per run |
| `save_bot_token.py` | Paste path for the optional audit-logging `xoxb-` token |
| `verify_setup.py` | Diagnostic — confirms tokens.json is wired up correctly |
| `config.py` | Shared helpers (token loading, audit_log) |
| `examples/send_dms_as_users.py` | Send a list of DMs from different personas |
| `examples/delete_dms.py` | Delete previously-sent DMs (uses probe-and-delete trick) |
| `tokens.example.json` | Template — copy to `tokens.json` and fill in |
| `tokens.json` | Your real tokens (gitignored, never committed) |

---

## Troubleshooting

**`auth_user.py` exits with "Missing or unset oauth.client_id"** — You
haven't filled in `tokens.json`. See Step 5.

**Browser shows "Your connection is not private"** — Expected. The toolkit
uses a self-signed cert for the OAuth callback. Click **advanced → proceed**.

**`auth_user.py` says "VERIFICATION FAILED — token NOT saved"** — You
authorized in a browser logged in as the wrong user. Re-run in incognito as
the target persona.

**`auth_user.py` blocks before printing the URL** — You forgot the `-u`
flag. Hit `Ctrl+C` and re-run as `python -u auth_user.py ...`.

**`chat.delete` returns `cant_delete_message`** — User tokens can only
delete their own messages. Make sure the `sender_email` in the manifest
matches the user that originally sent the DM.

**`chat.postMessage` returns `not_in_channel`** — Only happens for channels,
not DMs. If you see this for a DM, double-check the `recipient_user_id` is
a user ID (starts with `U`), not a channel ID.

**`'source' is not recognized as an internal or external command`** — You're
on Windows. Use `.venv\Scripts\Activate.ps1` instead of
`source .venv/bin/activate`. See [Windows commands](#windows-commands) below.

**`.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is
disabled on this system`** — PowerShell's default execution policy blocks
the activation script. Run this once, then retry:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**`'python' is not recognized`** (Windows) — Python wasn't added to PATH
during install. Easiest fix: reinstall from python.org and check **"Add
python.exe to PATH"** on the first screen. Or use the Python launcher:
replace `python` with `py` and `python3.12` with `py -3.12`.

---

## Windows commands

Windows users: Steps 1–3 are in the Slack web UI and work as written.
Everything from Step 4 onward runs in **PowerShell** (search "PowerShell" in
the Start menu). Only the commands in this table differ from the main flow
above — anything that starts with `python` (e.g.,
`python -u auth_user.py ...`, `python verify_setup.py`,
`python examples/send_dms_as_users.py ...`) runs identically.

| Step | Mac/Linux (main flow) | Windows (PowerShell) |
|---|---|---|
| 4 — create venv | `python3.12 -m venv .venv` | `py -3.12 -m venv .venv` |
| 4 — activate venv | `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |
| 5 — copy tokens file | `cp tokens.example.json tokens.json` | `Copy-Item tokens.example.json tokens.json` |
| 8 — copy example config | `cp examples/send_messages.example.json my_demo.json` | `Copy-Item examples\send_messages.example.json my_demo.json` |

**First-time PowerShell note:** If activating the venv fails with
"running scripts is disabled on this system," run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and retry. This
is a one-time per-user setting.

**Incognito windows on Windows:** For the OAuth step, open a private
browsing window — **Ctrl+Shift+N** in Chrome/Edge, **Ctrl+Shift+P** in
Firefox. (On Mac, it's `Cmd` instead of `Ctrl`.)
