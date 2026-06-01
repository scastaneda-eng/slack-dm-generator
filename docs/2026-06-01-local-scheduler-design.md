# Local scheduler — design

**Status:** approved (pending spec review)
**Date:** 2026-06-01
**Owner:** Sergio Castañeda

## Problem

The `daily/` add-on currently runs on GitHub Actions: an hourly scheduled
workflow on a private fork of the repo invokes `daily/refresh.py --mode auto`,
which sends or wipes DMs based on slot times in `daily/config.json`.

That path has too many failure modes for SEs to rely on it:

- GitHub auto-disables scheduled workflows after 60 days of repo inactivity.
- Cron firing on Actions is delayed by minutes-to-hours under load, so the
  bot used a fuzzy `±10 min` window and still missed slots.
- Setup requires a private GitHub fork, a repository secret holding the full
  `tokens.json`, and a one-click "enable workflows" banner — heavy lift for
  an SE just trying to seed a demo org.

We're replacing it with a local scheduler running on the SE's Mac. The
Python core (`daily/refresh.py`) stays scheduler-agnostic; only the driver
changes.

## Goals

1. SE can install a hands-off daily refresh in one command after finishing
   `SETUP.md`, walked through by Claude Code.
2. Mac is the supported primary path (matches the SE audience). Linux and
   Windows get short fallback appendices, no installer.
3. No new always-on infrastructure: the schedule is a launchd LaunchAgent
   in the SE's user session.
4. The repo stays clonable as a public template — no secrets, no hard-coded
   paths, no reference to a personal demo org.

## Non-goals

- Cross-platform parity. Windows users get a Task Scheduler appendix; we
  don't ship a Windows installer.
- Catching up missed slots when the laptop was asleep. SEs run a manual
  `--mode morning` (or `noon`/`wipe`) to recover.
- Changing the existing manual flow (`examples/send_dms_as_users.py`,
  `examples/delete_dms.py`). Those stay as-is.
- A long-running supervisor process. launchd's calendar interval is plenty.

## Approach

### Architecture

```
SE edits daily/config.json
         │
         ▼
install_local_scheduler.py ──reads──► config.json
         │                  ──fills──► launchagent.plist.template
         │                  ──writes──► ~/Library/LaunchAgents/com.slack-dm-generator.daily.plist
         │                  ──runs──► launchctl bootstrap gui/$UID …
         ▼
   launchd (every hour, on the hour)
         │
         ▼
   .venv/bin/python daily/refresh.py --mode auto
         │
         ├── pick_slot() picks morning|noon|wipe|None from config.slots
         ├── send_fn / delete_fn (existing Slack call sites)
         └── manifest at daily/state/today.json
```

### Schedule shape

A single LaunchAgent fires hourly at `Minute: 0`. `refresh.py --mode auto`
reads `daily/config.json` and decides via `pick_slot()` whether the current
time-in-recipient-tz matches a configured slot. This keeps `daily/config.json`
as the single source of truth for slot times and weekdays — the SE edits
JSON, not the .plist.

`SLOT_WINDOW_MINUTES` shrinks from 10 → 5. launchd fires within seconds of
the wall-clock minute, so the wide window from the GitHub Actions era is no
longer needed; 5 minutes covers any clock skew or laggy Slack call.

### Components

**New files**

- `daily/install_local_scheduler.py` — installer/uninstaller. CLI flags:
  - default: validate config, generate .plist, write to
    `~/Library/LaunchAgents/`, `launchctl bootstrap`, print next-fire time
    and log paths.
  - `--uninstall`: `launchctl bootout` and delete the .plist.
  - `--print`: dump the generated .plist to stdout, no filesystem changes.
  - `--reinstall`: bootout + delete + bootstrap fresh. Use when the repo
    moves on disk or the `.venv` is rebuilt (so the .plist needs new
    absolute paths). Routine edits to `daily/config.json` do **not**
    require a reinstall — `refresh.py` re-reads JSON on every hourly run.
  - Pre-flight checks: macOS only (refuse on other platforms with a pointer
    to the Linux/Windows appendices); `tokens.json` exists; `daily/config.json`
    exists and parses as JSON with the required fields
    (`recipient_user_id`, `senders`, `timezone`, `slots`, `weekdays`);
    `.venv/bin/python` exists.
- `daily/templates/launchagent.plist.template` — plist template with
  placeholders for `{python}`, `{repo}`, `{label}`, `{stdout_log}`,
  `{stderr_log}`. The installer fills these in at install time using
  absolute paths derived from the repo's location on disk.
- `daily/logs/.gitkeep` — log directory. launchd writes
  `daily/logs/stdout.log` and `daily/logs/stderr.log`.

**Changed files**

- `daily/refresh.py` — drop `SLOT_WINDOW_MINUTES` from 10 → 5. No other
  changes.
- `daily/README.md` — full rewrite around the launchd path. Keep the
  existing "what it does — at a glance" intro and the daily/config.json
  reference table. Replace every section about GitHub forks, secrets,
  workflow renames, and Actions UI with a short section on running the
  installer. Add Linux + Windows appendices.
- `daily/config.example.json` — unchanged.
- `README.md` — replace "uses GitHub Actions" with "runs from a local
  launchd job on Mac (cron on Linux, Task Scheduler on Windows)."
- `CLAUDE.md` — add a short section telling Claude Code that the daily
  add-on is installed by running `daily/install_local_scheduler.py`, and
  that the script does the launchctl work — Claude Code does not write
  .plist files by hand.
- `.gitignore` — add `daily/logs/*.log`.

**Removed files**

- `.github/workflows/daily-refresh.yml.disabled`
- `.github/workflows/` directory if empty
- All sections in `daily/README.md` about GitHub forks, `TOKENS_JSON`
  secrets, the `.disabled` rename, the Actions UI smoke test, and the
  60-day auto-disable warning.

### Cross-platform

- **Mac (primary):** `install_local_scheduler.py` + launchd, as above.
- **Linux:** appendix in `daily/README.md`. One crontab entry:
  `0 * * * * cd /abs/path/to/repo && .venv/bin/python daily/refresh.py --mode auto >> daily/logs/cron.log 2>&1`.
  No installer.
- **Windows:** appendix in `daily/README.md`. Task Scheduler GUI walkthrough
  + a `schtasks /create` one-liner alternative. No installer.

### Testing

- `daily/tests/test_refresh.py` — unchanged (still covers slot dispatch,
  manifest IO, dry-run paths).
- `daily/tests/test_install_local_scheduler.py` — new. Covers:
  - .plist generation is deterministic given fixed inputs.
  - Generated .plist passes `plutil -lint` (skipped on non-Mac CI).
  - `--print` writes to stdout, no filesystem effects.
  - `--uninstall` is idempotent (no-op when nothing is installed).
  - Pre-flight failures exit with non-zero and a friendly message
    (missing `tokens.json`, missing `daily/config.json`, non-Mac OS).
- No live Slack integration tests.

### Tradeoffs and known limitations

- **Laptop-asleep behavior:** if the laptop is closed when a slot fires,
  the send/wipe is skipped. Recovery is `python daily/refresh.py --mode
  morning` (or `noon` / `wipe`) by hand. Documented prominently in
  `daily/README.md`.
- **Hourly idle wakeups:** launchd wakes the Python process 24 times a
  day; ~20 of those are no-ops because no slot matches. Cost is
  negligible (Python startup + JSON parse + clock check), and the
  payoff is keeping `daily/config.json` as the source of truth for slot
  times without a regenerate step.
- **DST:** launchd handles local-tz transitions natively. No per-fork
  schedule edits needed across DST boundaries.
- **`audit_log()`:** stays optional. The existing config-driven
  channel resolution (`SLACK_AUDIT_CHANNEL_ID` env var or
  `audit_channel_id` in `tokens.json`) already works for any SE.

## Open questions

None at design time. If the installer turns out to be flaky on first
contact (`launchctl bootstrap` failure modes, permission prompts), revisit
the .plist template and pre-flight checks before treating it as a refresh.
