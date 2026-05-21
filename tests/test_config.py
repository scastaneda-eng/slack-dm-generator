"""Tests for config.py — focused on the audit_log() silent no-op contract."""
from __future__ import annotations

from pathlib import Path

import pytest

import config


def test_audit_log_silent_when_tokens_json_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """audit_log() should no-op silently if tokens.json doesn't exist.

    This matches the docstring contract: "No-ops silently if `app_token` or
    `audit_channel_id` is unavailable." A missing tokens.json is one way they
    can be unavailable — e.g., during a --dry-run before tokens are set up.
    """
    monkeypatch.setattr(config, "TOKENS_PATH", tmp_path / "does-not-exist.json")
    monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_AUDIT_CHANNEL_ID", raising=False)

    config.audit_log("test message")
