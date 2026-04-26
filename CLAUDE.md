# Claude Code orientation

This toolkit lets a Slack admin send and delete DMs as real users in their
demo Slack org via per-user OAuth tokens. The user may or may not be an
experienced coder — assume they are using Terminal commands and Claude Code
for the first time, and will need clear explanations and more context on
how to install and implement this project.

## What you should do

- **Setup help** — walk the user through `SETUP.md` one step at a time. Don't
  paste long blocks of commands; pause after each step and confirm before
  moving on.
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
- **Ask Mac or Windows first.** Before Step 4, ask which OS they're on. The
  doc is Mac-first; for Windows users, substitute from the
  `## Windows commands` table at the bottom of `SETUP.md` whenever a command
  starts with `source`, `cp`, or `python3.12`. Everything else is identical.
- **After token capture** — always run `python verify_setup.py` and read the
  output before declaring setup done.
- **Sending DMs** — copy `examples/send_messages.example.json` to a new file,
  edit it for the user's demo, then run
  `python examples/send_dms_as_users.py --config <file> --manifest sent.json`.
  Keep the manifest — it's how `delete_dms.py` knows what to remove later.

## What you must NOT do

- **Never ask the user to paste a token into the chat.** Always route them
  through `auth_user.py` (browser OAuth) for `xoxp-` user tokens or
  `save_bot_token.py` (getpass) for the optional `xoxb-` audit-logging token.
  Re-pasting tokens in chat re-leaks them into transcripts/logs.
- **Don't fabricate features.** This toolkit deliberately omits channel
  management, admin operations, and AI agents. If asked, say so.

## Critical OAuth gotcha

When `auth_user.py` opens the OAuth URL, it goes to the user's **default**
browser. If they're logged in to Slack there as a different user (e.g., their
admin account), Slack silently grants THAT user's token. The script's
post-capture check (`auth.test` + `users.lookupByEmail`) catches this and
refuses to save — but to avoid the round trip, **tell the user upfront** to
copy the printed URL into an **incognito** window logged in as the target
persona. Incognito shortcut: `Cmd+Shift+N` (Chrome/Edge on Mac),
`Ctrl+Shift+N` (Chrome/Edge on Windows), or `Ctrl+Shift+P` /
`Cmd+Shift+P` (Firefox).

If the user has `app_token` configured in `tokens.json`, verification is
strict (lookupByEmail). If not, verification falls back to a heuristic
name-match. Recommend they set up `app_token` for strict verification when
working with multiple personas.

## Token rotation

If the user needs to rotate tokens:
1. Rotate via Slack app UI (Basic Information page for client secret;
   reinstall app for new bot/user tokens).
2. For the bot token: `python save_bot_token.py` (getpass).
3. For user tokens: re-run `auth_user.py --email <email>` per persona.
4. Reinstalling the app does NOT invalidate already-captured `xoxp-` tokens,
   so you usually only need to re-capture the bot token.
