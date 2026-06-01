"""Daily DM refresh — opt-in scheduler add-on.

This script is the workhorse behind the optional GitHub Actions automation
described in daily/README.md. It supports four modes:

  morning  — send the configured weekday's morning DMs and append to manifest.
  noon     — send the configured weekday's noon DMs and append to manifest.
  wipe     — delete every DM listed in the manifest, then clear it.
  auto     — pick the right mode based on the current time-in-recipient-tz.
             Used by the GitHub Actions hourly cron.

Manual scripts under examples/ are unchanged. This module deliberately
duplicates the ~30 lines of probe-and-delete logic from examples/delete_dms.py
so daily/ stays a clean delete if an SE doesn't want it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

# Make `from config import ...` etc. work whether run from repo root or daily/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import audit_log, user_client  # noqa: E402
from errors import friendly_slack_error  # noqa: E402
from retry import retry_on_rate_limit  # noqa: E402

from slack_sdk.errors import SlackApiError  # noqa: E402

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "config.json"
DEFAULT_POOL_PATH = ROOT / "pool.json"
DEFAULT_MANIFEST_PATH = ROOT / "state" / "today.json"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]
SLOT_WINDOW_MINUTES = 5
TEXT_PREVIEW_CHARS = 80


# --------------------------------------------------------------------------- #
# Pure logic (no Slack, no IO outside the manifest path)
# --------------------------------------------------------------------------- #


def weekday_name(dt: datetime) -> str:
    return WEEKDAYS[dt.weekday()]


def pick_slot(now: datetime, slots: dict[str, str]) -> str | None:
    """Return the slot name whose HH:MM window contains `now`, else None.

    Window is +/- SLOT_WINDOW_MINUTES around the configured time.
    """
    now_minutes = now.hour * 60 + now.minute
    for name, hhmm in slots.items():
        h, m = (int(x) for x in hhmm.split(":"))
        target = h * 60 + m
        if abs(now_minutes - target) <= SLOT_WINDOW_MINUTES:
            return name
    return None


def resolve_messages(
    pool_entry: list[dict[str, str]],
    senders: dict[str, str],
) -> list[tuple[str, str]]:
    """Map [{sender_role, text}, ...] + senders dict -> [(email, text), ...].

    Messages whose sender_role is not in `senders` are silently dropped, so
    SEs can configure only `primary` and skip secondary messages.
    """
    out: list[tuple[str, str]] = []
    for msg in pool_entry:
        email = senders.get(msg["sender_role"])
        if not email:
            continue
        out.append((email, msg["text"]))
    return out


# --------------------------------------------------------------------------- #
# Manifest IO
# --------------------------------------------------------------------------- #


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"date": None, "timezone": None, "sent": []}
    with path.open() as f:
        return json.load(f)


def save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def already_sent(manifest: dict, slot: str, date: str) -> bool:
    if manifest.get("date") != date:
        return False
    return any(entry["slot"] == slot for entry in manifest.get("sent", []))


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


SendFn = Callable[[str, str, str], dict[str, Any]]
DeleteFn = Callable[[str, str, str], tuple[bool, str]]


def run_send(
    slot: str,
    now: datetime,
    config: dict,
    pool: dict,
    manifest_path: Path,
    send_fn: SendFn,
) -> None:
    """Send all messages for a given slot, append to manifest. Idempotent."""
    weekday = weekday_name(now)
    if weekday not in config.get("weekdays", []):
        print(f"[skip] {weekday} not in configured weekdays")
        return

    today_iso = now.date().isoformat()
    manifest = load_manifest(manifest_path)

    if manifest.get("date") != today_iso:
        # New day — start fresh. Yesterday's manifest, if any, is overwritten.
        manifest = {"date": today_iso, "timezone": str(now.tzinfo), "sent": []}

    if already_sent(manifest, slot, today_iso):
        print(f"[skip] {slot} already sent today ({today_iso})")
        return

    pool_entry = pool.get(weekday, {}).get(slot, [])
    pairs = resolve_messages(pool_entry, config["senders"])
    if not pairs:
        print(f"[skip] no messages resolved for {weekday}.{slot}")
        return

    recipient = config["recipient_user_id"]
    for email, text in pairs:
        try:
            result = send_fn(email, recipient, text)
        except SlackApiError as e:
            err = friendly_slack_error(e)
            print(f"[fail] {email}: {err}", file=sys.stderr)
            audit_log(f":warning: daily-dm send failed — {email} -> <@{recipient}> error=`{err}`")
            continue
        entry = {
            "slot": slot,
            "sender_email": email,
            "recipient_user_id": recipient,
            "channel_id": result["channel_id"],
            "ts": result["ts"],
            "text_preview": text[:TEXT_PREVIEW_CHARS],
        }
        manifest["sent"].append(entry)
        print(f"[sent] {email} -> <@{recipient}> ts={entry['ts']}")
        audit_log(f":inbox_tray: daily-dm sent — {email} -> <@{recipient}> (`ts={entry['ts']}`)")

    save_manifest(manifest_path, manifest)


def run_wipe(manifest_path: Path, delete_fn: DeleteFn) -> None:
    """Delete every entry in the manifest, then clear it."""
    manifest = load_manifest(manifest_path)
    sent = manifest.get("sent", [])
    if not sent:
        print("[skip] manifest empty, nothing to wipe")
        return

    for entry in sent:
        ok, info = delete_fn(entry["sender_email"], entry["recipient_user_id"], entry["ts"])
        if ok:
            print(f"[deleted] {entry['sender_email']} ts={entry['ts']}")
            audit_log(
                f":wastebasket: daily-dm wiped — {entry['sender_email']} -> "
                f"<@{entry['recipient_user_id']}> (`ts={entry['ts']}`)"
            )
        else:
            print(f"[fail] {entry['sender_email']} ts={entry['ts']} — {info}", file=sys.stderr)
            audit_log(
                f":warning: daily-dm wipe failed — {entry['sender_email']} -> "
                f"<@{entry['recipient_user_id']}> (`ts={entry['ts']}`) — {info}"
            )

    save_manifest(manifest_path, {"date": None, "timezone": None, "sent": []})


def dispatch(
    mode: str,
    now: datetime,
    config: dict,
    pool: dict,
    manifest_path: Path,
    send_fn: SendFn,
    delete_fn: DeleteFn,
) -> None:
    """Top-level mode dispatcher used by both CLI and tests."""
    if mode == "auto":
        slot = pick_slot(now, config["slots"])
        if slot is None:
            print(f"[skip] off-slot at {now.strftime('%H:%M')} {now.tzinfo}")
            return
        if slot == "wipe":
            run_wipe(manifest_path, delete_fn)
        else:
            run_send(slot, now, config, pool, manifest_path, send_fn)
        return

    if mode in ("morning", "noon"):
        run_send(mode, now, config, pool, manifest_path, send_fn)
        return

    if mode == "wipe":
        run_wipe(manifest_path, delete_fn)
        return

    raise ValueError(f"Unknown mode: {mode!r}")


# --------------------------------------------------------------------------- #
# Real Slack call sites (used at CLI/Action runtime, not in unit tests)
# --------------------------------------------------------------------------- #


@retry_on_rate_limit()
def _slack_send(sender_email: str, recipient_user_id: str, text: str) -> dict:
    client = user_client(sender_email)
    resp = client.chat_postMessage(channel=recipient_user_id, text=text)
    return {
        "sender_email": sender_email,
        "recipient_user_id": recipient_user_id,
        "channel_id": resp["channel"],
        "ts": resp["ts"],
    }


@retry_on_rate_limit()
def _slack_probe(client, recipient_user_id: str):
    return client.chat_postMessage(channel=recipient_user_id, text=".")


@retry_on_rate_limit()
def _slack_delete(client, channel: str, ts: str):
    return client.chat_delete(channel=channel, ts=ts)


def _slack_delete_one(sender_email: str, recipient_user_id: str, target_ts: str) -> tuple[bool, str]:
    """Probe-and-delete trick — see examples/delete_dms.py for full background."""
    client = user_client(sender_email)
    try:
        probe = _slack_probe(client, recipient_user_id)
    except SlackApiError as e:
        return False, f"probe post failed: {friendly_slack_error(e)}"
    channel = probe["channel"]
    probe_ts = probe["ts"]

    target_err = None
    try:
        _slack_delete(client, channel, target_ts)
    except SlackApiError as e:
        target_err = friendly_slack_error(e)

    probe_err = None
    try:
        _slack_delete(client, channel, probe_ts)
    except SlackApiError as e:
        probe_err = friendly_slack_error(e)

    if target_err and probe_err:
        return False, (
            f"chat.delete failed: {target_err}; probe cleanup also failed "
            f"({probe_err}) — orphan probe in channel {channel}"
        )
    if target_err:
        return False, f"chat.delete failed: {target_err}"
    if probe_err:
        return False, f"target deleted but probe cleanup failed: {probe_err}"
    return True, channel


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _dry_run_send(sender_email: str, recipient_user_id: str, text: str) -> dict:
    print(f"[dry-run] would send: {sender_email} -> <@{recipient_user_id}>: {text}")
    return {
        "sender_email": sender_email,
        "recipient_user_id": recipient_user_id,
        "channel_id": "D-DRYRUN",
        "ts": "0.000000",
    }


def _dry_run_delete(sender_email: str, recipient_user_id: str, ts: str) -> tuple[bool, str]:
    print(f"[dry-run] would delete: {sender_email} -> <@{recipient_user_id}> ts={ts}")
    return True, "D-DRYRUN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True,
                        choices=["auto", "morning", "noon", "wipe"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--pool", default=str(DEFAULT_POOL_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be sent/deleted without calling Slack")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        print(
            f"error: {config_path} not found. Copy {DEFAULT_CONFIG_PATH.name.replace('config', 'config.example')} to config.json and fill it in.",
            file=sys.stderr,
        )
        return 2
    with config_path.open() as f:
        config = json.load(f)
    with Path(args.pool).open() as f:
        pool = json.load(f)

    now = datetime.now(ZoneInfo(config["timezone"]))
    send_fn = _dry_run_send if args.dry_run else _slack_send
    delete_fn = _dry_run_delete if args.dry_run else _slack_delete_one

    dispatch(
        mode=args.mode, now=now,
        config=config, pool=pool,
        manifest_path=Path(args.manifest),
        send_fn=send_fn, delete_fn=delete_fn,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
