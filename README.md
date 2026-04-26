# slack-dm-generator

A demo preparation tool for Slack Solutions Engineers. Use it to seed a
realistic, "lived-in" Slack inbox before a customer demo — sending DMs on
behalf of persona accounts (a CRO, a customer, a deal-desk partner, etc.) so
the environment looks naturally active rather than empty. When the demo is
over, clean up all the seeded messages in one step.

This app walks you through authorizing one or more demo personas so you can
send messages on their behalf — all via API calls through your AI coding agent.

> **New to Vibe Coding or Terminal commands?** No problem. You can ask your
> agent for clarification or step-by-step instructions at any point. This
> project was built with beginner coders in mind.

## Get started

Read [SETUP.md](SETUP.md). Setup is ~15 minutes. You'll need:
- Admin access to your demo Slack org
- Python 3.12
- A willingness to click through one self-signed cert warning

## Using Claude Code?

Open this folder in Claude Code and ask: *"help me set this up."*
[CLAUDE.md](CLAUDE.md) tells Claude how to handle the gotchas (incognito for
OAuth, never paste tokens in chat, what to do if verification fails, etc.).
