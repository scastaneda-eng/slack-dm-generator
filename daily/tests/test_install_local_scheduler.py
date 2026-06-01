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


import os
import subprocess


def test_install_writes_plist_and_calls_launchctl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    repo = _scaffold_repo(tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_launch_agents = tmp_path / "LaunchAgents"
    fake_launch_agents.mkdir()
    monkeypatch.setattr(installer, "launch_agents_dir", lambda: fake_launch_agents)
    monkeypatch.setattr(os, "getuid", lambda: 501)
    run_mock = mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0))

    rc = installer.install(repo)
    assert rc == 0

    written = fake_launch_agents / "com.slack-dm-generator.daily.plist"
    assert written.exists()
    body = written.read_text()
    assert str(repo / ".venv" / "bin" / "python") in body
    assert installer.LABEL in body

    run_mock.assert_called_once()
    cmd = run_mock.call_args.args[0]
    assert cmd[:2] == ["launchctl", "bootstrap"]
    assert cmd[2] == "gui/501"
    assert cmd[3] == str(written)


def test_install_fails_when_preflight_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    repo = _scaffold_repo(tmp_path)
    (repo / "tokens.json").unlink()
    monkeypatch.setattr(sys, "platform", "darwin")
    run_mock = mocker.patch("subprocess.run")

    with pytest.raises(installer.PreflightError):
        installer.install(repo)
    run_mock.assert_not_called()


def test_install_surfaces_launchctl_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    repo = _scaffold_repo(tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_launch_agents = tmp_path / "LaunchAgents"
    fake_launch_agents.mkdir()
    monkeypatch.setattr(installer, "launch_agents_dir", lambda: fake_launch_agents)
    monkeypatch.setattr(os, "getuid", lambda: 501)
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 5, stderr="boom"))

    rc = installer.install(repo)
    assert rc != 0


def test_uninstall_calls_bootout_and_deletes_plist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    fake_launch_agents = tmp_path / "LaunchAgents"
    fake_launch_agents.mkdir()
    plist = fake_launch_agents / f"{installer.LABEL}.plist"
    plist.write_text("dummy")
    monkeypatch.setattr(installer, "launch_agents_dir", lambda: fake_launch_agents)
    monkeypatch.setattr(os, "getuid", lambda: 501)
    run_mock = mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0))

    rc = installer.uninstall()
    assert rc == 0

    cmd = run_mock.call_args.args[0]
    assert cmd[:2] == ["launchctl", "bootout"]
    assert cmd[2] == f"gui/501/{installer.LABEL}"
    assert not plist.exists()


def test_uninstall_is_idempotent_when_nothing_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    fake_launch_agents = tmp_path / "LaunchAgents"
    fake_launch_agents.mkdir()
    monkeypatch.setattr(installer, "launch_agents_dir", lambda: fake_launch_agents)
    monkeypatch.setattr(os, "getuid", lambda: 501)
    # bootout returns non-zero when nothing is loaded — that's fine.
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 113, stderr="not loaded"))

    rc = installer.uninstall()
    assert rc == 0  # idempotent: no plist + bootout said "not loaded" is success


def test_reinstall_calls_uninstall_then_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker,
) -> None:
    repo = _scaffold_repo(tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_launch_agents = tmp_path / "LaunchAgents"
    fake_launch_agents.mkdir()
    monkeypatch.setattr(installer, "launch_agents_dir", lambda: fake_launch_agents)
    monkeypatch.setattr(os, "getuid", lambda: 501)
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0))

    uninstall_spy = mocker.spy(installer, "uninstall")
    install_spy = mocker.spy(installer, "install")

    rc = installer.reinstall(repo)
    assert rc == 0
    uninstall_spy.assert_called_once()
    install_spy.assert_called_once()
