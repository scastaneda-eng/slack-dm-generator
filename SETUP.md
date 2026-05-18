# slack-dm-generator — Setup

This toolkit lets you **send and delete DMs as real users** in your Slack
demo org. Useful for generating an active Today View and message inbox before a demo.

Setup is one-time, ~15 minutes.

---

## Two ways to follow this guide — pick whichever fits

- **Open this folder in Claude Code and ask *"help me set this up."*** Claude reads this guide and
  [CLAUDE.md](CLAUDE.md) and walks you through it one step at a time,
  pausing for your confirmation between steps and running the commands
  for you when it's safe to do so. Best if you're new to Terminal — at
  any point you can ask Claude to explain what a step does or why.
- **Read it yourself.** The steps below assume you're comfortable opening a
  Terminal window, copy-pasting commands, and running them yourself.

Either path uses the same instructions below. Each command is tagged with
**[Claude Code]** (Claude can run it for you) or **[Terminal]** (you run
it yourself in a Terminal window — these are commands that block on
interactive input that Claude can't drive). The tags are explained in the
primer below.

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

**About `.venv` (Python virtual environment).** Step 3 creates a folder
called `.venv` inside the project. It's a private, sandboxed copy of Python
just for this toolkit — that way installing packages here won't affect the
rest of your system. You'll see the `.venv/` folder appear; that's
expected. `source .venv/bin/activate` (Step 3) tells *your current Terminal
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

## Step 1 — `[Slack web UI]` Create the Slack app from the manifest

1. Open https://api.slack.com/apps in your browser.
2. Click **Create New App** → **From an app manifest**.
3. Pick your demo workspace.
4. Open `manifest.json` (in this folder) and paste the whole file into Slack's
   manifest box.
   > **In Claude Code**, ask Claude to open `manifest.json` and show it to you
   > — you can copy it from there.
5. Click **Next**, review the summary, then **Create**.

> **What is a manifest?** A JSON file that pre-fills every setting for your
> Slack app — name, redirect URL, scopes (permissions), bot user — so you
> don't have to click through a dozen forms. The file ships with this toolkit;
> you don't need to edit it.

---

## Identities at a glance — read this before Step 2

You'll work with two Slack identities through the rest of this setup. Knowing
which one you're "being" at each step is the single biggest source of confusion
for first-time users — pin this down up front and the rest of the setup is
straightforward.

> 👤 **Jennifer Hynes** (or your primary demo persona, if your demo org has
> been customized — uncommon). In every Slack Demo Org, Jennifer is both the
> admin *and* the primary demo user whose Today View / inbox is the focus of
> the demo. **In your normal browser, sign into Slack as Jennifer before you
> do Step 2.** Her account has the install rights this app needs, and her
> inbox is the one the persona DMs will eventually land in.
>
> 🎭 **Personas** — fake users (CRO, manager, deal-desk, etc.) whose tokens
> the script captures in Step 5 so they can DM Jennifer. **Each persona is
> authorized in its own fresh incognito window**, one at a time.
>
> Quick rule of thumb: *normal browser = Jennifer, incognito window = persona.*

---

## Step 2 — `[Slack web UI]` Install the app and copy OAuth credentials

> 👤 Before you click **Install to Workspace**: in this same (normal,
> non-incognito) browser, sign into Slack as **Jennifer Hynes** (or your
> primary demo persona). She has the install rights this app needs, and her
> inbox is the one the persona DMs will land in.

1. On your app's page at api.slack.com, click **Install to Workspace** and
   review the permissions, then click **Allow**.
2. Click **Basic Information** in the sidebar. Under **App Credentials**, copy:
   - **Client ID**
   - **Client Secret** (click "Show")

   You'll paste these into `tokens.json` in Step 4.
3. (Only if you plan to turn on audit logging in Step 8.) In the sidebar, click
   **OAuth & Permissions** and copy the **Bot User OAuth Token** (starts with
   `xoxb-`). Keep it handy — you'll use it in Step 8.

> ℹ The manifest already configured `https://localhost:3000/oauth/callback`
> as the redirect URL and pre-loaded the scopes the toolkit needs:
>
> - **User scope** (used for the persona's `xoxp-` token):
>   `chat:write` — covers DM **send** and **delete**.
> - **Bot scopes** (used for the optional audit-logging `xoxb-` token in
>   Step 8): `chat:write`, `chat:write.public`, `users:read`,
>   `users:read.email`.
>
> Nothing to click there.

---

## Step 3 — Set up Python

**[Claude Code]** Ask Claude to run these, or paste them into the prompt.
If you're using Terminal instead, run them there — just make sure you've
`cd`'d into the toolkit folder first (see "Before you start" above).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

You'll see a new `.venv/` folder appear in the project — that's the
sandboxed Python install. It's gitignored, so it won't be committed.

> ℹ **No activation needed.** Every command in the rest of this guide calls
> `.venv/bin/python ...` directly, which uses the sandbox without any
> activation step. This works the same in Claude Code and in a fresh
> Terminal window. (If you prefer a shorter `python` command for your own
> exploration, you can optionally run `source .venv/bin/activate` — it
> lasts for the current Terminal window only.)

---

## Step 4 — Create `tokens.json`

**[Claude Code]** Ask Claude to run this, or do it yourself in Terminal:

```bash
cp tokens.example.json tokens.json
```

Open `tokens.json` and fill in `oauth.client_id` and `oauth.client_secret`
from Step 2. Leave everything else as-is for now. (If you're in Claude
Code, you can ask Claude to open the file and help you edit it — just
paste the client ID/secret from the Slack web UI; don't paste other
tokens.)

> ⚠ **Never paste tokens into a chat with Claude Code.** Always use the
> local scripts (`auth_user.py` for user tokens, `save_bot_token.py` for the
> optional bot token). Pasting tokens into chat re-leaks them.

---

## Step 5 — Capture per-persona tokens

**[Terminal]** — run this in a dedicated Terminal window, not Claude Code.
(The script prints a URL, then waits for your browser to complete OAuth.
You need to watch it live and have the window stay open.)

This is the step where you switch identities: in Step 2 you were Jennifer
in your normal browser; now, **for each persona you want to impersonate**
(CRO, manager, deal-desk, etc.), you'll log in as that persona in a fresh
incognito window and let the script capture an `xoxp-` token through Slack's
OAuth flow. Quick rule of thumb: *normal browser = Jennifer, incognito
window = persona.*

Repeat the checklist below once per persona.

### The flow, step by step

1. **Open a fresh incognito window and sign into Slack as the persona.**
   Use that persona's Demo Zone Magic Link. Keep the window open — you'll
   paste a URL into it shortly.
   - Incognito shortcut: `Cmd+Shift+N` (Chrome/Edge on Mac), `Ctrl+Shift+N`
     (Chrome/Edge on Windows), `Cmd+Shift+P` / `Ctrl+Shift+P` (Firefox).

2. **Run the script** (in your Terminal, not in Claude Code):
   ```bash
   .venv/bin/python -u auth_user.py --email persona@yourorg.com
   ```
   - The `-u` (unbuffered) flag makes the OAuth URL print **before** the
     script blocks waiting for the callback.
   - Add `--no-open` if you're running this through Claude Code, or any
     time your default browser is signed into Slack as someone other than
     the persona you're capturing:
     ```bash
     .venv/bin/python -u auth_user.py --email persona@yourorg.com --no-open
     ```
     Without it, the script auto-opens your default browser on top of the
     URL it prints — easy to accidentally click "Allow" in the wrong
     window. `--no-open` skips that round trip entirely.

3. **Copy the OAuth URL the script prints, and paste it into the incognito
   window from step 1** — *not* your default browser.
   - **Why incognito matters:** Slack's OAuth URL is identity-blind. It
     grants a token for whichever Slack user is signed into the browser
     that loads it. Your normal browser is signed in as Jennifer, so a
     URL loaded there would issue a Jennifer token. The incognito window
     gives you a clean slate signed into Slack only as the persona, so
     the token belongs to the persona.
   - If the script auto-opened a tab in your default browser (i.e., you
     didn't pass `--no-open`), **ignore that tab** — close it or just
     don't click "Allow" in it.
   - Your browser will warn about a self-signed cert on `localhost`. Click
     **advanced → proceed**.

4. **Click Allow on Slack's authorization page** (in the incognito window).
   The script captures the token, verifies it belongs to the persona, and
   either saves it to `tokens.json` or rejects it.

5. **If verification rejects:** the script will print a checklist of the
   most likely causes. Fix the cause in the incognito window (or the
   `--email` value) and re-run from step 1.

### Reference

> ⚠ **Strict vs. heuristic verification.** Without `app_token` in
> `tokens.json`, the script can only *heuristically* check that the
> captured token belongs to the right person — by comparing the email's
> local part to the Slack username. That works for usernames that follow
> your email scheme (e.g. `john.doe@co.com` ↔ `john.doe`) but can pass for
> the wrong user when usernames diverge from emails (e.g. an admin account
> that happens to substring-match). **Strongly recommended: configure
> `app_token`** (a Slack bot token with the `users:read` and
> `users:read.email` scopes) so the script can call `users.lookupByEmail`
> and verify exactly. Heuristic-mode runs print a visible warning before
> saving.

> ℹ **What just happened.** In Step 2 you installed the app once as
> Jennifer (your normal browser, signed into Slack as her). In Step 5 you
> switched to each persona in incognito and captured a per-user `xoxp-`
> token. Those tokens now live in `tokens.json` under `users` and are what
> let the toolkit DM Jennifer on each persona's behalf in Step 7.

---

## Step 6 — Verify

**[Claude Code]** (or Terminal, either works):

```bash
.venv/bin/python verify_setup.py
```

Should print every persona email + matching user ID and end with
`READY — all checks passed.` If anything is flagged, fix it before moving on.
In Claude Code, Claude can run this and read the output back to you.

---

## Step 7 — Send a test DM

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
   .venv/bin/python examples/send_dms_as_users.py --config my_demo.json --manifest sent.json
   ```
4. Confirm the DM appears in the recipient's Slack.

To clean up:
```bash
.venv/bin/python examples/delete_dms.py --manifest sent.json
```

---

## Step 8 (optional) — Audit logging

If you want every send/delete logged automatically to a Slack channel:

1. Create a dedicated channel in your demo org (e.g., `#demo-audit-log`).
   Right-click → **View channel details** → copy the channel ID at the
   bottom (starts with `C`).
2. **[Terminal]** — run this in a dedicated Terminal window (the script
   uses a hidden paste prompt and a `y/N` confirm, which Claude Code's
   runner can't drive):
   ```bash
   .venv/bin/python save_bot_token.py
   ```
   Paste the `xoxb-` token you copied in Step 2. **Your keystrokes won't
   appear on screen — that's intentional (`getpass` hides them so tokens
   don't show up in scrollback). Just paste and press Enter.**
   > ℹ Didn't copy the bot token in Step 2? Go back to your app at
   > api.slack.com → **OAuth & Permissions** → copy the **Bot User OAuth
   > Token** (`xoxb-...`) and return here.
3. Open `tokens.json` and set `audit_channel_id` to the channel ID from
   step 1.
4. **[Claude Code]** Re-run `.venv/bin/python verify_setup.py` — you should
   now see audit logging green.

If you don't do this, audit logging silently no-ops. The toolkit still works.

> ℹ The manifest already ships the bot scopes this feature needs
> (`chat:write`, `chat:write.public`, `users:read`, `users:read.email`), so there's no
> reinstall step — just run `save_bot_token.py` with the token that was
> generated when you installed the app in Step 2.

---

## Token rotation

If you need to rotate (e.g., a token leaked):

| Token | How to rotate |
|---|---|
| `client_secret` | Slack app → Basic Information → Regenerate. Update `tokens.json`. |
| Bot `xoxb-` (audit) | Reinstall app → copy new token → `.venv/bin/python save_bot_token.py`. |
| Persona `xoxp-` | Re-run `.venv/bin/python -u auth_user.py --email persona@yourorg.com`. |

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
haven't filled in `tokens.json`. See Step 4.

**Browser shows "Your connection is not private"** — Expected. The toolkit
uses a self-signed cert for the OAuth callback. Click **advanced → proceed**.

**`auth_user.py` says "VERIFICATION FAILED — token NOT saved"** — You
authorized in a browser logged in as the wrong user. Re-run in incognito as
the target persona.

**`auth_user.py` blocks before printing the URL** — You forgot the `-u`
flag. Hit `Ctrl+C` and re-run as `.venv/bin/python -u auth_user.py ...`.

**`zsh: command not found: python`** (or `python: command not found`) —
You're in a Terminal window where the venv isn't active, and macOS's
default Python is named `python3` (not `python`). The fix is already baked
into every command in this guide: use the explicit
`.venv/bin/python ...` form (or `.venv\Scripts\python.exe ...` on
Windows). That works whether or not you've activated the venv.

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

Windows users: Steps 1–2 are in the Slack web UI and work as written.
Everything from Step 3 onward runs in **PowerShell** (search "PowerShell" in
the Start menu). The commands are nearly identical, with two substitutions:

- Anywhere this guide writes `.venv/bin/python ...`, swap in
  `.venv\Scripts\python.exe ...` (forward → back slashes, plus `.exe`).
- Anywhere this guide writes `.venv/bin/pip ...`, swap in
  `.venv\Scripts\pip.exe ...`.

The remaining differences are in this table:

| Step | Mac/Linux (main flow) | Windows (PowerShell) |
|---|---|---|
| 3 — create venv | `python3.12 -m venv .venv` | `py -3.12 -m venv .venv` |
| 3 — install requirements | `.venv/bin/pip install -r requirements.txt` | `.venv\Scripts\pip.exe install -r requirements.txt` |
| 4 — copy tokens file | `cp tokens.example.json tokens.json` | `Copy-Item tokens.example.json tokens.json` |
| 7 — copy example config | `cp examples/send_messages.example.json my_demo.json` | `Copy-Item examples\send_messages.example.json my_demo.json` |

**First-time PowerShell note:** If activating the venv fails with
"running scripts is disabled on this system," run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and retry. This
is a one-time per-user setting.

**Incognito windows on Windows:** For the OAuth step, open a private
browsing window — **Ctrl+Shift+N** in Chrome/Edge, **Ctrl+Shift+P** in
Firefox. (On Mac, it's `Cmd` instead of `Ctrl`.)
