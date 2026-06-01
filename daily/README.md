# daily/ — Optional automation add-on

This is an **optional, opt-in** add-on to the main toolkit. It keeps your
demo Slack org naturally active between demos: a small batch of generic DMs
lands every weekday morning and noon, and gets wiped at night. The next
morning, fresh batch.

If you only need to seed DMs right before a specific demo,
**you don't need this** — the manual flow in `examples/send_dms_as_users.py`
covers that case and stays untouched.

> **You probably don't need this if** you only spin up your demo org for one
> or two demos a week. Set it up if you want your org to look "alive" any
> time you happen to open it — for screen recordings, ad-hoc walkthroughs,
> or standing demo links.

---

## What it does — at a glance

Once enabled, the bot runs on a schedule in **your** timezone (configured in
`daily/config.json`). The default schedule:

| Time (your local) | What happens |
|---|---|
| 8:00am Mon–Fri  | 2 DMs land in the recipient's inbox (one from each configured sender). |
| 12:00pm Mon–Fri | 2 more DMs land. |
| 9:00pm Mon–Fri  | All DMs the bot sent today are deleted. |
| Sat / Sun       | Nothing — by default, only weekdays are configured. |

You can edit times, weekdays, message content, and which personas send the
DMs. See Step 2 below.

The schedule runs from **your laptop** via launchd (Mac), cron (Linux), or
Task Scheduler (Windows). When your laptop is closed, the schedule pauses;
the next slot to fire after the laptop wakes will run normally. To catch up
a missed slot manually, run `.venv/bin/python daily/refresh.py --mode morning`
(or `noon` / `wipe`).

---

## Before you start

1. **A working `tokens.json`.** Finish Steps 1–6 of the main `SETUP.md` first.
   The daily add-on uses the same tokens.
2. **Admin on your demo Slack org.** Already true if you finished main setup.
3. **Mac, Linux, or Windows** — the Mac path is the supported one and what
   the rest of this guide covers. Linux/Windows users: see the appendices
   at the bottom.

---

## Step 1 — `[Claude Code or Terminal]` Create `daily/config.json`

Copy the example:

```bash
cp daily/config.example.json daily/config.json
```

Open `daily/config.json` and edit the four fields:

```json
{
  "recipient_user_id": "U01ABCDEFGH",
  "senders": {
    "primary":   "manager@yourorg.com",
    "secondary": "teammate@yourorg.com"
  },
  "timezone": "America/Los_Angeles",
  "slots": {
    "morning": "08:00",
    "noon":    "12:00",
    "wipe":    "21:00"
  },
  "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"]
}
```

| Field | What goes here |
|---|---|
| `recipient_user_id` | Slack user ID (starts with `U`) of the person who receives the DMs. Usually your primary demo persona. Find it in Slack: click the person's profile → ⋯ → **Copy member ID**. |
| `senders.primary`   | Email of one persona you authorized in main setup Step 5. Required. |
| `senders.secondary` | Email of a second persona. Optional — delete this key if you only want one sender per slot. |
| `timezone`          | Any IANA timezone name: `America/Los_Angeles`, `America/New_York`, `Europe/London`, `Asia/Tokyo`, etc. The schedule is in this timezone, with daylight-saving handled automatically. |
| `slots`             | Times of day in 24-hour `HH:MM`. Edit if 8/12/9 doesn't fit your day. |
| `weekdays`          | Days the bot is active. Trim to taste. Lowercase English names only. |

> **Don't paste tokens here.** This file holds emails and timezone, no
> secrets. The actual tokens stay in `tokens.json`, which never gets
> committed.

---

## Step 2 — `[Claude Code or Terminal]` (Optional) Edit the message bank

The default messages in `daily/pool.json` are intentionally generic — they
read as a colleague asking for help, an FYI, or a time-sensitive request,
and they make sense in any demo. **You can use them as-is.**

If you want to tailor the voice or industry, the file is organized as
**weekday → slot → list of messages**. Each slot has two messages, one
tagged `primary` and one tagged `secondary`, mapped to the senders you set
in Step 1. Example:

```json
"monday": {
  "morning": [
    {"sender_role": "primary",   "text": "Need 15 minutes today to align on the retro outcomes before our 1:1 tomorrow. Does 2pm or 4pm work better?"},
    {"sender_role": "secondary", "text": "Did the deck from Friday's review get finalized? I need to share it with my counterpart in the next hour."}
  ],
  ...
}
```

Swap in your own wording — keep `sender_role` (`primary` or `secondary`)
and `text` as the field names and you're fine. There's a schema test that
catches typos:

```bash
.venv/bin/python -m pytest daily/tests/test_pool_schema.py
```

---

## Step 3 — `[Claude Code or Terminal]` Install the LaunchAgent

This step writes a launchd LaunchAgent to `~/Library/LaunchAgents/` and
registers it with `launchctl`. Run:

```bash
.venv/bin/python daily/install_local_scheduler.py
```

You should see output like:

```
Installed com.slack-dm-generator.daily.
  plist:  /Users/<you>/Library/LaunchAgents/com.slack-dm-generator.daily.plist
  logs:   /path/to/repo/daily/logs/stdout.log
          /path/to/repo/daily/logs/stderr.log
Next run: at the top of the next hour. To smoke-test now:
  /path/to/repo/.venv/bin/python /path/to/repo/daily/refresh.py --mode morning
```

If the install fails, the output tells you what to fix (missing
`tokens.json`, missing `daily/config.json`, etc.). Address it and rerun.

> **What just happened?** The script generated a launchd .plist that points
> at this repo's `.venv/bin/python` and `daily/refresh.py`, dropped it in
> your user-level LaunchAgents folder, and asked launchd to start watching
> it. Every hour at `:00`, launchd runs `refresh.py --mode auto`, which
> reads `daily/config.json` and decides whether the current time matches
> a configured slot.

---

## Step 4 — `[Claude Code or Terminal]` Smoke test

Confirm the bot works before you leave it running unattended:

```bash
.venv/bin/python daily/refresh.py --mode morning
```

That sends the morning DMs immediately, regardless of the current time.
Check Slack — you should see two new DMs in the recipient's inbox. Then
wipe them:

```bash
.venv/bin/python daily/refresh.py --mode wipe
```

Once both work, the hourly schedule takes over and you're done.

---

## Coexistence with manual sends

You can keep using `examples/send_dms_as_users.py` to seed custom DMs for
a specific demo. The two flows don't interfere:

- The auto-job's manifest lives at `daily/state/today.json`. The 9pm wipe
  **only** deletes messages listed there.
- Your manual `--manifest sent.json` (or whatever you name it) is
  untouched by the auto-job.

When you finish a manual demo, clean up your hand-curated DMs the usual
way (`examples/delete_dms.py --manifest sent.json`).

---

## Pausing or removing

| What you want | What to do |
|---|---|
| Pause for a few days | `launchctl bootout gui/$(id -u)/com.slack-dm-generator.daily` — re-enable with `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.slack-dm-generator.daily.plist` |
| Remove entirely | `.venv/bin/python daily/install_local_scheduler.py --uninstall` |
| Move the repo to a new folder | After moving, run `.venv/bin/python daily/install_local_scheduler.py --reinstall` so the .plist picks up the new absolute paths |

---

## Troubleshooting

**The schedule isn't firing.**
Check that the LaunchAgent is registered:

```bash
launchctl print gui/$(id -u)/com.slack-dm-generator.daily | head -20
```

If you get "Could not find specified service", run the installer again.

**The run succeeded but no DMs landed.**
- Confirm `recipient_user_id` is correct (starts with `U`).
- Confirm both `senders.primary` and `senders.secondary` are emails listed
  under `users` in your local `tokens.json`. If only one is present, the
  other's messages get skipped silently.
- Check `daily/logs/stderr.log` for `[fail]` lines.

**The DMs land at the wrong time.**
Check `timezone` in `daily/config.json`. Use an IANA name
(`America/New_York`), not an abbreviation like `EST`.

**My laptop was asleep at slot time.**
launchd doesn't queue missed runs while the system sleeps. Catch up by
hand: `.venv/bin/python daily/refresh.py --mode morning` (or `noon` /
`wipe`).

**I want to send only one DM per slot, not two.**
Delete the `secondary` line from `senders` in `daily/config.json`. The
hourly job re-reads the file on every fire — no reinstall needed.

**I want to send on weekends too.**
Add `"saturday"` and/or `"sunday"` to the `weekdays` list. You'll also need
to add `saturday`/`sunday` keys with `morning` and `noon` slots to
`pool.json`.

---

## Appendix A — Linux

Use cron. Add one line to your crontab:

```
0 * * * * cd /abs/path/to/repo && .venv/bin/python daily/refresh.py --mode auto >> daily/logs/cron.log 2>&1
```

Edit with `crontab -e`. Replace `/abs/path/to/repo` with the absolute path
to this repo on your machine. Everything else in this README applies as-is
(config, smoke test, troubleshooting).

## Appendix B — Windows

Use Task Scheduler. Create a task with:

- **Trigger:** daily, repeat every 1 hour, indefinitely.
- **Action:** Start a program.
  - **Program/script:** `<repo>\.venv\Scripts\python.exe`
  - **Add arguments:** `<repo>\daily\refresh.py --mode auto`
  - **Start in:** `<repo>`

Or as a one-liner from an Administrator PowerShell prompt (replace `<repo>`
with the absolute path):

```powershell
schtasks /create /tn "slack-dm-generator daily" /sc hourly /mo 1 ^
  /tr "<repo>\.venv\Scripts\python.exe <repo>\daily\refresh.py --mode auto" ^
  /st 00:00
```

Logs go to `<repo>\daily\logs\stdout.log` only if you also redirect them in
the task — cron's `>>` redirect doesn't apply here. Easiest: wrap the
`refresh.py` call in a small `.cmd` file that does the redirect, and point
the task at that.
