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


def test_cli_print_writes_plist_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    rc = installer.main(["--print"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "<plist" in captured.out
    assert "<key>Label</key>" in captured.out
    assert installer.LABEL in captured.out


import json


def test_validate_config_accepts_example(tmp_path: Path) -> None:
    example = ROOT / "daily" / "config.example.json"
    cfg = json.loads(example.read_text())
    # Strip the leading "_comment" key that the example carries for SE guidance.
    cfg.pop("_comment", None)
    target = tmp_path / "config.json"
    target.write_text(json.dumps(cfg))
    # Should not raise.
    parsed = installer.validate_config(target)
    assert parsed["recipient_user_id"] == cfg["recipient_user_id"]


def test_validate_config_rejects_missing_required_field(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text(json.dumps({
        "recipient_user_id": "U1",
        "senders": {"primary": "p@x.com"},
        "timezone": "America/Los_Angeles",
        # missing slots and weekdays
    }))
    with pytest.raises(installer.ConfigError) as excinfo:
        installer.validate_config(target)
    assert "slots" in str(excinfo.value)


def test_validate_config_rejects_bad_json(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("{not valid json")
    with pytest.raises(installer.ConfigError) as excinfo:
        installer.validate_config(target)
    assert "JSON" in str(excinfo.value) or "json" in str(excinfo.value)


def test_validate_config_rejects_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "missing.json"
    with pytest.raises(installer.ConfigError) as excinfo:
        installer.validate_config(target)
    assert "not found" in str(excinfo.value)


def _scaffold_repo(tmp_path: Path) -> Path:
    """Create a minimal repo-like structure for preflight to pass."""
    repo = tmp_path / "repo"
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").touch()
    (repo / "daily").mkdir(parents=True)
    (repo / "tokens.json").write_text("{}")
    cfg_example = ROOT / "daily" / "config.example.json"
    cfg = json.loads(cfg_example.read_text())
    cfg.pop("_comment", None)
    (repo / "daily" / "config.json").write_text(json.dumps(cfg))
    return repo


def test_preflight_passes_with_complete_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _scaffold_repo(tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    # Should not raise.
    installer.preflight(repo)


def test_preflight_rejects_non_mac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _scaffold_repo(tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(installer.PreflightError) as excinfo:
        installer.preflight(repo)
    assert "macOS" in str(excinfo.value) or "Mac" in str(excinfo.value)


def test_preflight_rejects_missing_tokens_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _scaffold_repo(tmp_path)
    (repo / "tokens.json").unlink()
    monkeypatch.setattr(sys, "platform", "darwin")
    with pytest.raises(installer.PreflightError) as excinfo:
        installer.preflight(repo)
    assert "tokens.json" in str(excinfo.value)


def test_preflight_rejects_missing_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _scaffold_repo(tmp_path)
    (repo / ".venv" / "bin" / "python").unlink()
    monkeypatch.setattr(sys, "platform", "darwin")
    with pytest.raises(installer.PreflightError) as excinfo:
        installer.preflight(repo)
    assert ".venv" in str(excinfo.value)


def test_preflight_propagates_config_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _scaffold_repo(tmp_path)
    (repo / "daily" / "config.json").unlink()
    monkeypatch.setattr(sys, "platform", "darwin")
    with pytest.raises(installer.ConfigError):
        installer.preflight(repo)
