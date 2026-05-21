# daily/ — Optional automation add-on

This is an **optional, opt-in** add-on to the main toolkit. It uses GitHub
Actions to keep your demo Slack org naturally active between demos: a small
batch of generic DMs lands every weekday morning and noon, and gets wiped at
night. The next morning, fresh batch.

If you only need to seed DMs right before a specific demo,
**you don't need this** — the manual flow in `examples/send_dms_as_users.py`
covers that case and stays untouched.

> **You probably don't need this if** you only spin up your demo org for one
> or two demos a week. Set it up if you want your org to look "alive" any
> time you happen to open it — for screen recordings, ad-hoc walkthroughs, or
> standing demo links.

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
DMs. See Step 2 and Step 3 below.

---

## Before you start — three things you need

1. **A working `tokens.json`.** Finish Steps 1–6 of the main `SETUP.md` first.
   The daily add-on uses the same tokens.
2. **Admin on your demo Slack org.** Already true if you finished main setup.
3. **A free GitHub account.** This is the part that's likely new — read on.

### What's GitHub Actions, and why do I need a GitHub account?

The bot needs to run on a schedule even when your laptop is closed. We use
**GitHub Actions** for that — it's GitHub's built-in scheduler that fires jobs
on a timer, kind of like a tiny computer in the cloud you don't have to
maintain. The job needs a place to live, and that place is **a copy of this
repo under your own GitHub account**. Without a GitHub account, there's
nowhere for the scheduler to run.

GitHub Actions is **free** for public repos like this one — running this job
24 times a day uses a small fraction of GitHub's free tier.

### If you don't have a GitHub account yet

1. Go to <https://github.com/join> and sign up. The free tier is fine — you
   don't need Pro, Enterprise, or any paid plan.
2. Pick any username; it doesn't have to match your work email.
3. Verify your email when GitHub sends the confirmation link.
4. You're done. Continue to Step 1.

### Why your copy of this repo should be private

The bot commits a small **manifest file** (`daily/state/today.json`) back to
your copy of the repo every time it runs — that's how it remembers what to
delete at 9pm. The manifest contains:

- The **emails** of the personas you configured as senders
- The **Slack user ID** of the recipient
- An **80-character preview** of every message the bot sent today

It's not credential-grade data, but it *is* live information about your
demo org. If your copy of the repo is **public**, that information is
public too — and your config file (`daily/config.json`) and Action run
logs leak the same details.

**The fix is one click during setup: make your copy of the repo private.**

GitHub's "Fork" button creates a *public* copy of a public repo (you can't
change that). So instead of forking, this guide tells you to **clone and
push to a new, private repo of your own**. The end result is the same — a
copy you can edit and run Actions from — but it's private from the start,
your tokens stay encrypted as a GitHub secret, and nothing in the repo's
git history reveals demo-org internals.

GitHub Actions on a private repo gives you 2,000 free minutes/month. This
bot uses ~6 hours/month — well under the limit.

---

## Step 1 — `[GitHub web UI + Terminal]` Make a private copy of the repo

We'll make a private copy of this repo on your GitHub account in three
small moves: clone the public repo locally, create a new empty private
repo, and push your local copy up to it.

### 1a — `[GitHub web UI]` Create an empty private repo

1. Go to <https://github.com/new>.
2. **Repository name:** `slack-dm-generator` (or anything you like — it's
   yours).
3. **Visibility:** click **Private**. ⚠ This is the important one. If you
   leave it on Public, your config file and the manifest the bot commits
   daily will be visible to anyone with the link.
4. **Do not** check "Add a README", "Add .gitignore", or "Choose a
   license" — we want a totally empty repo to push into.
5. Click **Create repository**.
6. On the next page, GitHub shows you a clone URL like
   `https://github.com/<your-username>/slack-dm-generator.git`. **Copy it
   — you'll paste it in 1c.**

### 1b — `[Claude Code or Terminal]` Clone the public template locally

```bash
git clone https://github.com/scastaneda-eng/slack-dm-generator.git
cd slack-dm-generator
```

> **Cloning** copies the repo from GitHub onto your computer. By default,
> the local folder is connected back to the original public repo as
> `origin`. We'll change that in the next step.

### 1c — `[Claude Code or Terminal]` Point the local repo at your private one

Replace the URL below with the one you copied at the end of 1a, then run:

```bash
git remote set-url origin https://github.com/<your-username>/slack-dm-generator.git
git push -u origin main
```

That `git push` uploads everything to your private repo. Refresh the
GitHub page from 1a — you should see all the project files there now.

> **Verify it's private.** On the repo's GitHub page, look for a 🔒
> (lock) icon next to the repo name. If you see it, you're good. If not,
> open **Settings → General → scroll to "Danger Zone" → "Change
> repository visibility"** and switch to Private.

From here on, every "your repo" reference means **your private repo**, not
the original public template.

---

## Step 2 — `[Claude Code or Terminal]` Create `daily/config.json`

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
| `recipient_user_id` | Slack user ID (starts with `U`) of the person who receives the DMs. Usually Jennifer Hynes — the same recipient you'd target with the manual flow. Find it in Slack: click the person's profile → ⋯ → **Copy member ID**. |
| `senders.primary`   | Email of one persona you authorized in main setup Step 5. Required. |
| `senders.secondary` | Email of a second persona. Optional — delete this key if you only want one sender per slot. |
| `timezone`          | Any IANA timezone name: `America/Los_Angeles`, `America/New_York`, `Europe/London`, `Asia/Tokyo`, etc. The schedule is in this timezone, with daylight-saving handled automatically. |
| `slots`             | Times of day in 24-hour `HH:MM`. Edit if 8/12/9 doesn't fit your day. |
| `weekdays`          | Days the bot is active. Trim to taste. Lowercase English names only. |

> **Don't paste tokens here.** This file holds emails and timezone, no
> secrets. The actual tokens stay in `tokens.json`, which never gets
> committed.

---

## Step 3 — `[Claude Code or Terminal]` (Optional) Edit the message bank

The default messages in `daily/pool.json` are intentionally generic — they
read as a colleague asking for help, an FYI, or a time-sensitive request, and
they make sense in any demo. **You can use them as-is.**

If you want to tailor the voice or industry, the file is organized as
**weekday → slot → list of messages**. Each slot has two messages, one tagged
`primary` and one tagged `secondary`, mapped to the senders you set in
Step 2. Example before/after:

```json
"monday": {
  "morning": [
    {"sender_role": "primary",   "text": "Need 15 minutes today to align on the retro outcomes before our 1:1 tomorrow. Does 2pm or 4pm work better?"},
    {"sender_role": "secondary", "text": "Did the deck from Friday's review get finalized? I need to share it with my counterpart in the next hour."}
  ],
  ...
}
```

Swap in your own wording — keep `sender_role` (`primary` or `secondary`) and
`text` as the field names and you're fine. There's a schema test in
`daily/tests/test_pool_schema.py` that catches typos:

```bash
.venv/bin/python -m pytest daily/tests/test_pool_schema.py
```

---

## Step 4 — `[GitHub web UI]` Add the `TOKENS_JSON` secret

GitHub Actions runs in the cloud, so it needs a copy of your `tokens.json`
to authenticate as your personas. We give it that as an **encrypted
repository secret** — a value GitHub Actions can read but no one else can
see (not even you, after you save it).

1. On your private repo's page, click **Settings** (top nav).
2. In the left sidebar: **Secrets and variables → Actions**.
3. Click **New repository secret**.
4. **Name:** `TOKENS_JSON` (exactly that, all caps).
5. **Value:** paste the entire contents of your local `tokens.json`. Open it
   in any editor, select all, copy, paste.
6. Click **Add secret**.

> **Why the entire file?** It's simpler than per-key secrets — one secret in,
> one file out. The workflow writes `tokens.json` from the secret at the
> start of each run and deletes it at the end.

---

## Step 5 — `[Claude Code or Terminal]` Enable the workflow

The workflow file ships with a `.disabled` suffix so GitHub Actions ignores
it until you turn it on. Enabling is a single rename + commit.

If you're in **Claude Code**, paste this prompt:

```
Please rename .github/workflows/daily-refresh.yml.disabled to
.github/workflows/daily-refresh.yml, then commit and push to my private repo.
```

If you'd rather do it in Terminal:

```bash
git mv .github/workflows/daily-refresh.yml.disabled \
       .github/workflows/daily-refresh.yml
git commit -m "Enable daily DM refresh"
git push
```

> **Why a rename instead of a checkbox?** GitHub Actions only picks up
> workflow files that end in `.yml` or `.yaml`. Renaming is a clean,
> reversible toggle that doesn't require any UI clicks.

---

## Step 6 — `[GitHub web UI]` Smoke test

Confirm the bot works before you leave it running unattended.

1. On your private repo's page, click **Actions** (top nav).
   - **First-time visit:** GitHub shows a banner asking you to enable
     workflows on this repo. Click **I understand my workflows, go ahead and
     enable them**.
2. In the left sidebar, click **Daily DM Refresh**.
3. Click **Run workflow** (top right of the run list).
4. **Mode:** pick `morning`.
5. Click the green **Run workflow** button.
6. Wait ~30 seconds for it to finish (refresh the page).
7. Check Slack — you should see two new DMs in the recipient's inbox.
8. Run it again with **mode:** `wipe`. The DMs should disappear.

Once the smoke test works, the hourly schedule takes over and you're done.

---

## Coexistence with manual sends

You can keep using `examples/send_dms_as_users.py` to seed custom DMs for a
specific demo. The two flows don't interfere:

- The auto-job's manifest lives at `daily/state/today.json`. The 9pm wipe
  **only** deletes messages listed there.
- Your manual `--manifest sent.json` (or whatever you name it) is untouched
  by the auto-job.

When you finish a manual demo, clean up your hand-curated DMs the usual
way (`examples/delete_dms.py --manifest sent.json`).

---

## Turning it off

Three options, depending on how off you want it:

| What you want | What to do |
|---|---|
| Pause for a few days | On your fork's **Actions** tab → **Daily DM Refresh** → ⋯ menu → **Disable workflow**. Re-enable the same way. |
| Keep the code, stop running | Rename `.github/workflows/daily-refresh.yml` back to `.disabled` and commit. |
| Remove entirely | Delete the `daily/` folder and the workflow file. Nothing else changes. |

If you also want to stop committing state, delete `daily/state/today.json`
after you turn the workflow off.

---

## Troubleshooting

**The schedule isn't firing.**
Check the workflow file ends in `.yml`, not `.yml.disabled`. GitHub Actions
silently ignores any other extension.

**The run failed with "TOKENS_JSON secret is missing."**
Add the secret in Step 4. Names are case-sensitive.

**The run succeeded but no DMs landed.**
- Confirm `recipient_user_id` is correct (starts with `U`).
- Confirm both `senders.primary` and `senders.secondary` are emails listed
  under `users` in your local `tokens.json`. If only one is present, the
  other's messages get skipped silently.
- Check the run log under **Actions → Daily DM Refresh** for `[fail]` lines.

**The DMs land at the wrong time.**
Check `timezone` in `daily/config.json`. Use an IANA name
(`America/New_York`), not an abbreviation like `EST`.

**GitHub disabled my workflow after a long break.**
GitHub auto-disables scheduled workflows after **60 days of repo inactivity**
(no commits, issues, etc.). Once enabled, the daily commits the workflow
makes back to your repo are themselves activity, so this only affects repos
that pause for 60+ days. To wake it up, push any commit — even a
whitespace-only change to a README — then re-enable the workflow if needed.

**I want to send only one DM per slot, not two.**
Delete the `secondary` line from `senders` in `daily/config.json`.

**I want to send on weekends too.**
Add `"saturday"` and/or `"sunday"` to the `weekdays` list. You'll also need
to add `saturday`/`sunday` keys with `morning` and `noon` slots to
`pool.json`.
