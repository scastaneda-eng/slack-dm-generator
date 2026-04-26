# slack-dm-generator

Send and delete DMs as real users in your Slack demo org via per-user OAuth.
Useful for seeding a "lived-in" inbox before a demo (DMs from a CRO, a
customer, a deal-desk partner, etc.) and cleaning up afterward.

> **New to Terminal or Claude Code?** You're the target reader.
> [SETUP.md](SETUP.md) explains each command in plain language and tells you
> exactly where to run it (inside Claude Code, or in a dedicated Terminal
> window).

## Get started

Read [SETUP.md](SETUP.md). Setup is ~15 minutes. You'll need:
- Admin access to your demo Slack org
- Python 3.12
- A willingness to click through one self-signed cert warning

## Using Claude Code?

Open this folder in Claude Code and ask: *"help me set this up."*
[CLAUDE.md](CLAUDE.md) tells Claude how to handle the gotchas (incognito for
OAuth, never paste tokens in chat, what to do if verification fails, etc.).

## What this toolkit does NOT do

- No channel create/archive/delete
- No admin user management
- No AI agent simulation
- No Salesforce / external integrations

It's deliberately scoped to user impersonation + DM send/delete.
