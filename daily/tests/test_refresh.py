"""Tests for daily/refresh.py — slot matching, manifest IO, send/wipe orchestration.

Slack API calls are exercised via a fake `Sender` object passed in by tests, so
these tests don't reach the network and don't need slack_sdk mocks.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import refresh  # noqa: E402  (path injected via conftest.py)


# --------------------------------------------------------------------------- #
# pick_slot — given a tz-aware datetime + slot config, return slot name or None
# --------------------------------------------------------------------------- #

SLOTS = {"morning": "08:00", "noon": "12:00", "wipe": "21:00"}


def _at(hour: int, minute: int, tz: str = "America/Los_Angeles", *, weekday: int = 0) -> datetime:
    """Build an aware datetime for a Monday (weekday=0) at HH:MM in tz."""
    # 2026-05-25 is a Monday
    base = datetime(2026, 5, 25, hour, minute, tzinfo=ZoneInfo(tz))
    # weekday 0..6 -> shift days
    return base.replace(day=25 + weekday)


@pytest.mark.parametrize(
    "h,m,expected",
    [
        (8, 0, "morning"),
        (7, 50, "morning"),
        (8, 9, "morning"),
        (8, 11, None),
        (7, 49, None),
        (12, 0, "noon"),
        (12, 9, "noon"),
        (11, 51, "noon"),
        (11, 50, "noon"),
        (11, 49, None),
        (21, 0, "wipe"),
        (15, 30, None),
    ],
)
def test_pick_slot_within_window(h: int, m: int, expected: str | None) -> None:
    assert refresh.pick_slot(_at(h, m), SLOTS) == expected


def test_pick_slot_handles_dst_spring_forward() -> None:
    # 2026-03-08 02:30 PT does not exist (clocks jump 02:00 -> 03:00).
    # 08:00 local on that day is unambiguous and should still match "morning".
    spring = datetime(2026, 3, 8, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert refresh.pick_slot(spring, SLOTS) == "morning"


def test_pick_slot_handles_dst_fall_back() -> None:
    # 2026-11-01 fall-back day; 08:00 is well clear of the 01:00-02:00 ambiguity.
    fall = datetime(2026, 11, 1, 8, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert refresh.pick_slot(fall, SLOTS) == "morning"


# --------------------------------------------------------------------------- #
# weekday_name — lowercase English weekday from a datetime
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "date_args,expected",
    [
        ((2026, 5, 25), "monday"),
        ((2026, 5, 26), "tuesday"),
        ((2026, 5, 27), "wednesday"),
        ((2026, 5, 28), "thursday"),
        ((2026, 5, 29), "friday"),
        ((2026, 5, 30), "saturday"),
        ((2026, 5, 31), "sunday"),
    ],
)
def test_weekday_name(date_args: tuple[int, int, int], expected: str) -> None:
    dt = datetime(*date_args, 12, 0, tzinfo=ZoneInfo("UTC"))
    assert refresh.weekday_name(dt) == expected


# --------------------------------------------------------------------------- #
# resolve_messages — pool entry + sender map -> [(email, text)]
# --------------------------------------------------------------------------- #


def test_resolve_messages_maps_roles_to_emails() -> None:
    pool_entry = [
        {"sender_role": "primary",   "text": "hello from primary"},
        {"sender_role": "secondary", "text": "hello from secondary"},
    ]
    senders = {"primary": "p@x.com", "secondary": "s@x.com"}
    out = refresh.resolve_messages(pool_entry, senders)
    assert out == [("p@x.com", "hello from primary"), ("s@x.com", "hello from secondary")]


def test_resolve_messages_skips_unmapped_roles() -> None:
    pool_entry = [
        {"sender_role": "primary",   "text": "p"},
        {"sender_role": "secondary", "text": "s"},
    ]
    # Only primary is configured.
    out = refresh.resolve_messages(pool_entry, {"primary": "p@x.com"})
    assert out == [("p@x.com", "p")]


# --------------------------------------------------------------------------- #
# Manifest IO — read/write/append/clear
# --------------------------------------------------------------------------- #


def test_load_manifest_returns_empty_when_missing(tmp_path: Path) -> None:
    m = refresh.load_manifest(tmp_path / "today.json")
    assert m == {"date": None, "timezone": None, "sent": []}


def test_save_then_load_manifest_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "today.json"
    data = {
        "date": "2026-05-25",
        "timezone": "America/Los_Angeles",
        "sent": [
            {"slot": "morning", "sender_email": "p@x.com", "recipient_user_id": "U1",
             "channel_id": "D1", "ts": "1.0", "text_preview": "hi"}
        ],
    }
    refresh.save_manifest(p, data)
    assert refresh.load_manifest(p) == data


def test_already_sent_true_when_slot_in_manifest() -> None:
    manifest = {
        "date": "2026-05-25",
        "timezone": "America/Los_Angeles",
        "sent": [{"slot": "morning", "sender_email": "x", "recipient_user_id": "U",
                  "channel_id": "D", "ts": "1", "text_preview": ""}],
    }
    assert refresh.already_sent(manifest, "morning", "2026-05-25") is True


def test_already_sent_false_when_different_date() -> None:
    manifest = {
        "date": "2026-05-24",
        "timezone": "America/Los_Angeles",
        "sent": [{"slot": "morning", "sender_email": "x", "recipient_user_id": "U",
                  "channel_id": "D", "ts": "1", "text_preview": ""}],
    }
    assert refresh.already_sent(manifest, "morning", "2026-05-25") is False


def test_already_sent_false_when_different_slot() -> None:
    manifest = {
        "date": "2026-05-25",
        "timezone": "America/Los_Angeles",
        "sent": [{"slot": "morning", "sender_email": "x", "recipient_user_id": "U",
                  "channel_id": "D", "ts": "1", "text_preview": ""}],
    }
    assert refresh.already_sent(manifest, "noon", "2026-05-25") is False


# --------------------------------------------------------------------------- #
# run_send — orchestrates a slot's sends, idempotent, appends to manifest
# --------------------------------------------------------------------------- #


class FakeSender:
    """Stand-in for the real Slack `chat.postMessage` call.

    Records calls, returns deterministic channel/ts. Tests pass it via
    dependency injection so refresh.py doesn't need a Slack mock here.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self._counter = 0

    def __call__(self, sender_email: str, recipient_user_id: str, text: str) -> dict:
        self._counter += 1
        self.calls.append({"sender_email": sender_email, "text": text})
        return {
            "sender_email": sender_email,
            "recipient_user_id": recipient_user_id,
            "channel_id": f"D{self._counter:03d}",
            "ts": f"170000000{self._counter}.000{self._counter:03d}",
        }


def _config(tmp_path: Path, with_secondary: bool = True) -> dict:
    senders = {"primary": "p@x.com"}
    if with_secondary:
        senders["secondary"] = "s@x.com"
    return {
        "recipient_user_id": "U01ABCDEFGH",
        "senders": senders,
        "timezone": "America/Los_Angeles",
        "slots": SLOTS,
        "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    }


def _pool() -> dict:
    return {
        "monday": {
            "morning": [
                {"sender_role": "primary",   "text": "M morning P"},
                {"sender_role": "secondary", "text": "M morning S"},
            ],
            "noon": [
                {"sender_role": "primary",   "text": "M noon P"},
                {"sender_role": "secondary", "text": "M noon S"},
            ],
        },
        "tuesday": {"morning": [], "noon": []},
        "wednesday": {"morning": [], "noon": []},
        "thursday": {"morning": [], "noon": []},
        "friday": {"morning": [], "noon": []},
    }


def test_run_send_writes_manifest_and_calls_sender(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()

    refresh.run_send(
        slot="morning",
        now=_at(8, 0),
        config=_config(tmp_path),
        pool=_pool(),
        manifest_path=manifest_path,
        send_fn=sender,
    )

    assert len(sender.calls) == 2
    assert {c["sender_email"] for c in sender.calls} == {"p@x.com", "s@x.com"}
    manifest = refresh.load_manifest(manifest_path)
    assert manifest["date"] == "2026-05-25"
    assert len(manifest["sent"]) == 2
    assert all(entry["slot"] == "morning" for entry in manifest["sent"])


def test_run_send_idempotent_within_same_day(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()

    refresh.run_send("morning", _at(8, 0), _config(tmp_path), _pool(), manifest_path, sender)
    refresh.run_send("morning", _at(8, 5), _config(tmp_path), _pool(), manifest_path, sender)

    assert len(sender.calls) == 2  # second call no-ops
    assert len(refresh.load_manifest(manifest_path)["sent"]) == 2


def test_run_send_skips_when_weekday_not_in_config(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()
    cfg = _config(tmp_path)
    cfg["weekdays"] = ["tuesday"]  # Monday is excluded

    refresh.run_send("morning", _at(8, 0), cfg, _pool(), manifest_path, sender)

    assert sender.calls == []
    assert refresh.load_manifest(manifest_path)["sent"] == []


def test_run_send_skips_secondary_when_unmapped(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()

    refresh.run_send(
        "morning", _at(8, 0),
        _config(tmp_path, with_secondary=False),
        _pool(), manifest_path, sender,
    )

    assert len(sender.calls) == 1
    assert sender.calls[0]["sender_email"] == "p@x.com"


def test_run_send_replaces_manifest_on_new_day(tmp_path: Path) -> None:
    """A run on a new date overwrites yesterday's manifest rather than appending."""
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()

    refresh.run_send("morning", _at(8, 0, weekday=0), _config(tmp_path), _pool(),
                     manifest_path, sender)
    refresh.run_send("morning", _at(8, 0, weekday=1), _config(tmp_path),
                     {**_pool(), "tuesday": {"morning": [{"sender_role": "primary", "text": "T"}], "noon": []}},
                     manifest_path, sender)

    manifest = refresh.load_manifest(manifest_path)
    assert manifest["date"] == "2026-05-26"
    assert len(manifest["sent"]) == 1


# --------------------------------------------------------------------------- #
# run_wipe — reads manifest, calls deleter for each entry, clears manifest
# --------------------------------------------------------------------------- #


class FakeDeleter:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, sender_email: str, recipient_user_id: str, ts: str) -> tuple[bool, str]:
        self.calls.append({"sender_email": sender_email, "ts": ts})
        return True, "D-fake"


def test_run_wipe_deletes_each_entry_and_clears_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    refresh.save_manifest(manifest_path, {
        "date": "2026-05-25",
        "timezone": "America/Los_Angeles",
        "sent": [
            {"slot": "morning", "sender_email": "p@x.com", "recipient_user_id": "U1",
             "channel_id": "D1", "ts": "1.0", "text_preview": "x"},
            {"slot": "noon", "sender_email": "s@x.com", "recipient_user_id": "U1",
             "channel_id": "D1", "ts": "2.0", "text_preview": "y"},
        ],
    })
    deleter = FakeDeleter()

    refresh.run_wipe(manifest_path=manifest_path, delete_fn=deleter)

    assert len(deleter.calls) == 2
    assert {c["ts"] for c in deleter.calls} == {"1.0", "2.0"}
    assert refresh.load_manifest(manifest_path)["sent"] == []


def test_run_wipe_noop_on_empty_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    deleter = FakeDeleter()

    refresh.run_wipe(manifest_path=manifest_path, delete_fn=deleter)

    assert deleter.calls == []


# --------------------------------------------------------------------------- #
# auto-mode dispatch
# --------------------------------------------------------------------------- #


def test_dispatch_auto_calls_send_at_morning_slot(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()
    deleter = FakeDeleter()

    refresh.dispatch(
        mode="auto", now=_at(8, 0),
        config=_config(tmp_path), pool=_pool(),
        manifest_path=manifest_path,
        send_fn=sender, delete_fn=deleter,
    )

    assert len(sender.calls) == 2
    assert deleter.calls == []


def test_dispatch_auto_calls_wipe_at_wipe_slot(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    refresh.save_manifest(manifest_path, {
        "date": "2026-05-25", "timezone": "America/Los_Angeles",
        "sent": [{"slot": "morning", "sender_email": "p@x.com", "recipient_user_id": "U1",
                  "channel_id": "D1", "ts": "1.0", "text_preview": "x"}],
    })
    sender = FakeSender()
    deleter = FakeDeleter()

    refresh.dispatch(
        mode="auto", now=_at(21, 0),
        config=_config(tmp_path), pool=_pool(),
        manifest_path=manifest_path,
        send_fn=sender, delete_fn=deleter,
    )

    assert sender.calls == []
    assert len(deleter.calls) == 1


def test_dispatch_auto_off_slot_does_nothing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()
    deleter = FakeDeleter()

    refresh.dispatch(
        mode="auto", now=_at(15, 30),
        config=_config(tmp_path), pool=_pool(),
        manifest_path=manifest_path,
        send_fn=sender, delete_fn=deleter,
    )

    assert sender.calls == []
    assert deleter.calls == []


def test_dispatch_explicit_morning_runs_regardless_of_time(tmp_path: Path) -> None:
    """Explicit modes are for manual smoke-tests; they bypass the slot window."""
    manifest_path = tmp_path / "today.json"
    sender = FakeSender()

    refresh.dispatch(
        mode="morning", now=_at(15, 30),
        config=_config(tmp_path), pool=_pool(),
        manifest_path=manifest_path,
        send_fn=sender, delete_fn=FakeDeleter(),
    )

    assert len(sender.calls) == 2
