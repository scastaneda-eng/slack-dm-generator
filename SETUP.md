# slack-dm-generator — Setup

This toolkit lets you **send and delete DMs as real users** in your Slack
demo org. Useful for generating an active Today View and message inbox before a demo.

Setup is one-time, ~15 minutes.

---

## Before you start — if this is your first time with a terminal

This guide assumes you may never have used Terminal, Python, or Claude Code
before. That's fine — read this short primer and you'll be oriented.

**Claude Code** is an AI assistant that runs inside a folder on your
computer. You type a request in plain English and it can read your files
and run commands for you. If you're reading this because Claude Code told
you to, you already have it installed — you just type into the prompt.

**Terminal** is the Mac/Linux app that lets you type commands directly to
your computer (on Windows, the equivalent is **PowerShell**). You can open
it from Spotlight: press `Cmd+Space`, type `Terminal`, hit Enter.

**Every command below is tagged with where to run it:**

- **[Claude Code]** — paste the command into your Claude Code prompt (or
  just ask Claude to run it). Claude handles the typing for you.
- **[Terminal]** — open a dedicated Terminal / PowerShell window and type
  the command there. Use these for anything that takes over your screen
  with prompts or hidden input.

**About the working directory.** All the commands below assume you're
"inside" the toolkit folder. In Claude Code that's automatic if you opened
this folder. In a fresh Terminal window, you get there once with:

```bash
cd path/to/slack-dm-generator
```

Replace `path/to/` with wherever you cloned/downloaded it (e.g.
`cd ~/claude-projects/slack-dm-generator`).

**About `.venv` (Python virtual environment).** Step 4 creates a folder
called `.venv` inside the project. It's a private, sandboxed copy of Python
just for this toolkit — that way installing packages here won't affect the
rest of your system. You'll see the `.venv/` folder appear; that's
expected. `source .venv/bin/activate` (Step 4) tells *your current Terminal
window* to use that sandbox. It only lasts for that window — open a new
Terminal and you'd re-activate it. When running from Claude Code, each
command runs in a fresh shell, so Claude will call `.venv/bin/python`
directly instead of activating.

---

## Prerequisites

- **Slack admin** in your demo org (you need to install an app there).
- **Python 3.12** — the macOS system Python (3.9) is too old.
  **[Terminal]** (one-time system install):
  ```bash
  brew install python@3.12
  ```
  > **Don't have Homebrew?** Homebrew is the standard Mac package manager.
  > Install it once from https://brew.sh (a single command to paste into
  > Terminal), then run `brew install python@3.12` above.
  >
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

**[Claude Code]** Ask Claude to run these, or paste them into the prompt.
If you're using Terminal instead, run them there — just make sure you've
`cd`'d into the toolkit folder first (see "Before you start" above).

```bash
python3.12 -m venv .venv
pip install -r requirements.txt
```

You'll see a new `.venv/` folder appear in the project — that's the
sandboxed Python install. It's gitignored, so it won't be committed.

**If you're working in a dedicated Terminal window (not Claude Code),**
also run this once per new Terminal window, so your shell uses the sandbox:

```bash
source .venv/bin/activate
```

You'll know it worked when your prompt gains a `(.venv)` prefix. You do
**not** need to run `source ...` inside Claude Code — Claude calls
`.venv/bin/python` directly.

---

## Step 5 — Create `tokens.json`

**[Claude Code]** Ask Claude to run this, or do it yourself in Terminal:

```bash
cp tokens.example.json tokens.json
```

Open `tokens.json` and fill in `oauth.client_id` and `oauth.client_secret`
from Step 3. Leave everything else as-is for now. (If you're in Claude
Code, you can ask Claude to open the file and help you edit it — just
paste the client ID/secret from the Slack web UI; don't paste other
tokens.)

> ⚠ **Never paste tokens into a chat with Claude Code.** Always use the
> local scripts (`auth_user.py` for user tokens, `save_bot_token.py` for the
> optional bot token). Pasting tokens into chat re-leaks them.

---

## Step 6 — Capture per-persona tokens

**[Terminal]** — run this in a dedicated Terminal window, not Claude Code.
(The script prints a URL, then waits for your browser to complete OAuth.
You need to watch it live and have the window stay open.)

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

**[Claude Code]** (or Terminal, either works):

```bash
python verify_setup.py
```

Should print every persona email + matching user ID and end with
`READY — all checks passed.` If anything is flagged, fix it before moving on.
In Claude Code, Claude can run this and read the output back to you.

---

## Step 8 — Send a test DM

**[Claude Code]** (or Terminal — both commands here are non-interactive):

1. Copy the example config:
   ```bash
   cp examples/send_messages.example.json my_demo.json
   ```
2. Edit `my_demo.json` — replace the `sender_email` (must be one of your
   captured personas) and `recipient_user_id` (the Slack user ID of who
   should receive the DM). In Claude Code, you can ask Claude to open and
   edit the file for you.
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
   Token Scopes**: `chat:write`, `chat:write.public`, `users:read.email`.
   > ℹ `users:read.email` is what `auth_user.py` and `verify_setup.py` use
   > for strict persona verification (they look up the email you passed
   > with `--email` and confirm it matches the captured token). Without
   > this scope, you'll see a `missing_scope` error during verification.
3. Reinstall the app. Copy the new **Bot User OAuth Token** (`xoxb-...`)
   from the **Install App** page.
   > ℹ Reinstalling the app does **not** invalidate already-captured
   > `xoxp-` user tokens.
4. **[Terminal]** — run this in a dedicated Terminal window (the script
   uses a hidden paste prompt and a `y/N` confirm, which Claude Code's
   runner can't drive):
   ```bash
   python save_bot_token.py
   ```
   Paste the `xoxb-` when prompted. **Your keystrokes won't appear on
   screen — that's intentional (`getpass` hides them so tokens don't show
   up in scrollback). Just paste and press Enter.**
5. Open `tokens.json` and set `audit_channel_id` to the channel ID from
   step 1.
6. **[Claude Code]** Re-run `python verify_setup.py` — you should now see
   audit logging green.

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
