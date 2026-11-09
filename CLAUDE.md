# Claude Code orientation

This toolkit lets a Slack admin send and delete DMs as real users in their
demo Slack org via per-user OAuth tokens. The user may or may not be an
experienced coder — assume they are using Terminal commands and Claude Code
for the first time, and will need clear explanations and more context on
how to install and implement this project.

## What you should do

- **Setup help** — ask which OS the user uses and whether they want
  one step at a time or a short checklist. For guided setup, give one
  action at a time and explain what success looks like. In either mode,
  the user signs into Slack and approves access in the browser.
- **Showing the manifest** — when the user hits Step 1 (the "paste the
  manifest into Slack" step), open `manifest.json` with the Read tool and
  show the full JSON in chat so the user can copy it. Don't improvise or
  modify the manifest mid-walkthrough while helping someone through setup —
  deliberate scope/config changes to `manifest.json` are the project owner's
  call and go through the **Token rotation** process below, not an ad hoc
  edit during a setup session.
- **Respect the [Claude Code] vs [Terminal] tags in SETUP.md.** For
  `[Claude Code]` steps, just run the command yourself via the Bash tool
  and show the user the result. For `[Terminal]` steps, **don't run them
  yourself** — instead, tell the user: "please open a Terminal window, make
  sure you're in the project folder, and run this:" followed by the
  command. These steps block on interactive input (`getpass`, an OAuth
  callback, `y/N` confirms) that the Bash tool can't drive.
- **Venv in Claude Code sessions.** Each Bash tool call runs in a fresh
  shell, so `source .venv/bin/activate` doesn't persist. Always invoke the
  project's Python as `.venv/bin/python <script>` (macOS/Linux) or
  `.venv\Scripts\python.exe <script>` (Windows) instead of activating.
- **Windows commands** — use the PowerShell equivalents in SETUP.md.
- **After token capture** — always run `.venv/bin/python verify_setup.py`
  and read the output before declaring setup done.
- **Sending DMs** — start with the one-message example. Show the sender,
  recipient, and text for review before sending. Use a new cleanup filename
  for each batch and keep it for `delete_dms.py`.

## Credentials and feature scope

- **Keep credentials local.** The user enters the Client Secret directly in
  `tokens.json`. Use `auth_user.py` for sender tokens and `save_bot_token.py`
  for the bot token used for exact sender verification or optional audit
  logging. Keep all three out of chat.
- **Don't fabricate features.** This toolkit deliberately omits channel
  management, admin operations, and AI agents. If asked, say so.

## Critical OAuth gotcha

Give the user the Step 5 command with `--no-open` to run in Terminal.
Have them paste the link into a private window signed into Slack as the
sender, check the Slack account before clicking Allow, and return to
Terminal for the verification result. Recommend saving the bot token in
Step 4 for exact email verification.

## Token rotation

If the user needs to rotate tokens:
1. Rotate via Slack app UI (Basic Information page for client secret;
   reinstall app for new bot/user tokens). Scopes themselves are pinned by
   `manifest.json` — if the user ever needs to change scopes, tell them to
   go to **Features → App Manifest** in the Slack app UI and paste an
   updated `manifest.json`, then reinstall.
2. For the bot token: `.venv/bin/python save_bot_token.py` (getpass).
3. For user tokens: re-run `.venv/bin/python -u auth_user.py --email <email> --no-open` per persona.
4. Reinstalling the app does NOT invalidate already-captured `xoxp-` tokens,
   so you usually only need to re-capture the bot token.

## Daily add-on (`daily/`)

If the user wants to enable the optional `daily/` automation, walk them
through `daily/README.md`. Two notes specific to that add-on:

- **Don't write the launchd .plist by hand.** The repo ships
  `daily/install_local_scheduler.py`, which generates the .plist from
  `daily/config.json` and registers it with `launchctl`. Run that script
  via the Bash tool — don't synthesize plist XML inline.
- **Don't reinstall after JSON edits.** Routine edits to slot times or
  weekdays in `daily/config.json` take effect on the next hourly run —
  the script reads JSON every time. Only run `--reinstall` if the repo
  moves on disk or the venv is rebuilt.
