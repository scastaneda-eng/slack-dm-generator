"""Validate daily/pool.json shape: 5 weekdays x {morning,noon} x {primary,secondary} messages."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

POOL_PATH = Path(__file__).resolve().parent.parent / "pool.json"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
SLOTS = ["morning", "noon"]
ROLES = {"primary", "secondary"}
MAX_TEXT_CHARS = 5000  # matches examples/send_dms_as_users.py:MAX_TEXT_CHARS


@pytest.fixture(scope="module")
def pool() -> dict:
    with POOL_PATH.open() as f:
        return json.load(f)


def test_pool_file_exists() -> None:
    assert POOL_PATH.is_file(), f"pool.json missing at {POOL_PATH}"


def test_all_weekdays_present(pool: dict) -> None:
    assert set(pool.keys()) == set(WEEKDAYS)


@pytest.mark.parametrize("day", WEEKDAYS)
def test_each_weekday_has_both_slots(pool: dict, day: str) -> None:
    assert set(pool[day].keys()) == set(SLOTS)


@pytest.mark.parametrize("day", WEEKDAYS)
@pytest.mark.parametrize("slot", SLOTS)
def test_each_slot_has_both_roles(pool: dict, day: str, slot: str) -> None:
    roles = {msg["sender_role"] for msg in pool[day][slot]}
    assert roles == ROLES, f"{day}.{slot} sender_roles = {roles}, expected {ROLES}"


@pytest.mark.parametrize("day", WEEKDAYS)
@pytest.mark.parametrize("slot", SLOTS)
def test_each_message_has_required_fields(pool: dict, day: str, slot: str) -> None:
    for msg in pool[day][slot]:
        assert "sender_role" in msg
        assert "text" in msg
        assert msg["sender_role"] in ROLES
        assert isinstance(msg["text"], str)
        assert msg["text"].strip(), f"{day}.{slot} has an empty message"
        assert len(msg["text"]) <= MAX_TEXT_CHARS
