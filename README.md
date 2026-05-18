# slack-dm-generator

A demo preparation tool for Slack Solutions Engineers. Use it to seed a
realistic, active view of the Today View in Slack before a customer demo — sending DMs on
behalf of persona accounts (a CRO, a customer, a deal-desk partner, etc.) so
the environment looks naturally active, with pending messages from other users. When the demo is
over, clean up all the seeded messages in one step.

This app walks you through (1) installing an OAuth integration once as
Jennifer Hynes (or your primary demo persona, if you've swapped her out),
and then (2) authorizing it as each persona you want to impersonate, capturing
per-user tokens so you can send messages on their behalf — all via API calls
through your AI coding agent.

> **New to Vibe Coding or Terminal commands?** No problem. You can ask your
> agent for clarification or step-by-step instructions at any point. This
> project was built with beginner coders in mind.

## Get started

Read [SETUP.md](SETUP.md). Setup is ~15 minutes. You'll need:
- Admin access to your demo Slack org
- Python 3.12
- A willingness to click through one self-signed cert warning

> ℹ **A note on Python commands.** Every command in SETUP.md calls
> `.venv/bin/python ...` (or `.venv\Scripts\python.exe ...` on Windows)
> directly — that's the local sandboxed Python created in Step 3. You do
> **not** need to `source .venv/bin/activate` first. If you instead try
> bare `python -u auth_user.py ...` in a fresh Mac terminal, you'll see
> `zsh: command not found: python` (macOS only ships `python3`). Use the
> `.venv/bin/python` form and you're fine.

## Using Claude Code?

Open this folder in Claude Code and ask: *"help me set this up."*
[CLAUDE.md](CLAUDE.md) tells Claude how to handle the gotchas (incognito for
OAuth, never paste tokens in chat, what to do if verification fails, etc.).
