"""Tests for daily/install_local_scheduler.py — plist generation, validation, install/uninstall.

These tests do not call launchctl. Subprocess interactions are mocked.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = ROOT / "daily" / "templates" / "launchagent.plist.template"


def test_template_exists() -> None:
    assert TEMPLATE.exists(), f"plist template not found at {TEMPLATE}"


@pytest.mark.parametrize("placeholder", ["{python}", "{repo}", "{label}", "{stdout_log}", "{stderr_log}"])
def test_template_has_placeholder(placeholder: str) -> None:
    text = TEMPLATE.read_text()
    assert placeholder in text, f"template is missing placeholder {placeholder}"


import sys

sys.path.insert(0, str(ROOT / "daily"))
import install_local_scheduler as installer  # noqa: E402


def test_render_plist_substitutes_all_placeholders() -> None:
    rendered = installer.render_plist(
        python=Path("/tmp/repo/.venv/bin/python"),
        repo=Path("/tmp/repo"),
        label="com.slack-dm-generator.daily",
        stdout_log=Path("/tmp/repo/daily/logs/stdout.log"),
        stderr_log=Path("/tmp/repo/daily/logs/stderr.log"),
    )
    assert "/tmp/repo/.venv/bin/python" in rendered
    assert "/tmp/repo/daily/refresh.py" in rendered
    assert "<string>com.slack-dm-generator.daily</string>" in rendered
    assert "/tmp/repo/daily/logs/stdout.log" in rendered
    assert "/tmp/repo/daily/logs/stderr.log" in rendered
    # No placeholders remain.
    for placeholder in ["{python}", "{repo}", "{label}", "{stdout_log}", "{stderr_log}"]:
        assert placeholder not in rendered, f"unsubstituted placeholder {placeholder}"


def test_render_plist_is_deterministic() -> None:
    args = dict(
        python=Path("/tmp/repo/.venv/bin/python"),
        repo=Path("/tmp/repo"),
        label="com.slack-dm-generator.daily",
        stdout_log=Path("/tmp/repo/daily/logs/stdout.log"),
        stderr_log=Path("/tmp/repo/daily/logs/stderr.log"),
    )
    assert installer.render_plist(**args) == installer.render_plist(**args)


@pytest.mark.skipif(sys.platform != "darwin", reason="plutil is macOS-only")
def test_render_plist_passes_plutil_lint() -> None:
    import subprocess
    rendered = installer.render_plist(
        python=Path("/tmp/repo/.venv/bin/python"),
        repo=Path("/tmp/repo"),
        label="com.slack-dm-generator.daily",
        stdout_log=Path("/tmp/repo/daily/logs/stdout.log"),
        stderr_log=Path("/tmp/repo/daily/logs/stderr.log"),
    )
    result = subprocess.run(
        ["plutil", "-lint", "-"],
        input=rendered,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"plutil rejected the plist: {result.stdout}{result.stderr}"
