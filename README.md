# Slack DM Generator

Fill your Slack demo inbox with realistic direct messages (DMs) from demo
accounts, then remove them after the demo. Start with one sender, one recipient,
and one test DM. Check that it appears in Slack, then use the cleanup file to
remove it. Once that works, you can prepare a batch for your demo.

## Before you start

- A Slack demo workspace where you can install an app.
- Sign-in access for the demo sender. Jennifer Hynes is the usual recipient.
  Use your primary demo account if your workspace is customized.
- Python 3.12. The [setup guide](SETUP.md#prerequisites) shows how to install it.

On GitHub, choose **Code → Download ZIP** and unzip it, or clone the repo with
Git. Open the resulting project folder in your coding assistant or Terminal.

## Pick your setup path

- **New to coding assistants or Terminal?** Paste the prompt below into your
  coding assistant and ask for one step at a time.
- **Comfortable with a coding assistant?** Use the same prompt and ask for a
  short checklist. You'll sign into Slack and approve access in your browser.
  Claude Code also uses [CLAUDE.md](CLAUDE.md) for project guidance.
- **Prefer Terminal?** Follow the [setup guide](SETUP.md). Already set up?
  [Verify setup](SETUP.md#step-6--verify) or
  [send and clean up a test DM](SETUP.md#step-7--send-a-test-dm).

> Read SETUP.md and help me send and clean up one test DM in my Slack demo
> workspace. Ask which operating system I use and whether I want step-by-step
> help or a short checklist. Tell me what to click in Slack, what to run in
> Terminal, and what success looks like. Show me the sender, recipient, and
> message before sending.

## Optional daily refresh

The [daily add-on](daily/README.md) can send demo DMs on weekday mornings
and at noon, then remove them at night. It runs on your computer and is
disabled until you turn it on.
