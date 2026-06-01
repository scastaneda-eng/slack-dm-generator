# Local Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the GitHub Actions driver for `daily/refresh.py` with a local launchd LaunchAgent on Mac, plus a Python installer/uninstaller, and rewrite docs around the new path.

**Architecture:** A single LaunchAgent fires `refresh.py --mode auto` hourly. `daily/install_local_scheduler.py` generates the .plist from `daily/config.json`, writes it to `~/Library/LaunchAgents/`, and calls `launchctl bootstrap`. `daily/refresh.py` stays scheduler-agnostic — only the driver changes.

**Tech Stack:** Python 3.12, pytest 8 + pytest-mock, slack_sdk (unchanged), Apple launchd (Mac only).

**Spec:** `docs/2026-06-01-local-scheduler-design.md`

---

## File Structure

**New:**
- `daily/install_local_scheduler.py` — installer/uninstaller CLI + pure plist-generation functions
- `daily/templates/launchagent.plist.template` — plist body with `{python}`, `{repo}`, `{label}`, `{stdout_log}`, `{stderr_log}` placeholders
- `daily/logs/.gitkeep` — placeholder so the log directory ships with the repo
- `daily/tests/test_install_local_scheduler.py` — unit tests for the installer

**Modified:**
- `daily/refresh.py` — `SLOT_WINDOW_MINUTES` 10 → 5
- `daily/tests/test_refresh.py` — adjust `test_pick_slot_within_window` parameters to the new 5-minute window
- `daily/README.md` — full rewrite around launchd
- `README.md` — replace the "uses GitHub Actions" sentence
- `CLAUDE.md` — add a section on the daily/ install flow
- `.gitignore` — add `daily/logs/*.log`

**Removed:**
- `.github/workflows/daily-refresh.yml.disabled`
- `.github/workflows/` (if empty)

---

### Task 1: Cleanup — rip out GitHub Actions, scaffold log dir + .gitignore

**Files:**
- Delete: `.github/workflows/daily-refresh.yml.disabled`
- Delete: `.github/workflows/` (directory, if it ends up empty)
- Create: `daily/logs/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Delete the GitHub Actions workflow and its containing directory if empty**

```bash
cd ~/claude-projects/slack-dm-generator
rm .github/workflows/daily-refresh.yml.disabled
rmdir .github/workflows 2>/dev/null || true
rmdir .github 2>/dev/null || true
```

- [ ] **Step 2: Create the log directory placeholder**

```bash
mkdir -p daily/logs
touch daily/logs/.gitkeep
```

- [ ] **Step 3: Append the log glob to .gitignore**

Edit `.gitignore`. Final contents should be:

```
tokens.json
.env
__pycache__/
*.pyc
.DS_Store
.venv/
.certs/
.pytest_cache/
daily/logs/*.log
```

- [ ] **Step 4: Verify**

```bash
ls .github 2>&1                    # expected: ls: .github: No such file or directory
ls daily/logs                      # expected: .gitkeep listed (use ls -a)
git status                         # expected: deletion + new files staged-ready
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Remove GitHub Actions driver and scaffold daily/logs/ for launchd"
```

---

### Task 2: Tighten SLOT_WINDOW_MINUTES from 10 → 5

launchd fires within seconds of the wall-clock minute, so the wide ±10-minute window from the Actions era is no longer needed. Existing tests parametrize the boundary at ±9 / ±10 minutes; we tighten both the constant and the tests in lockstep.

**Files:**
- Modify: `daily/refresh.py:41`
- Modify: `daily/tests/test_refresh.py:34-50`

- [ ] **Step 1: Update the parametrized window test to expect the new boundary**

In `daily/tests/test_refresh.py`, replace the parameter list of `test_pick_slot_within_window` (currently lines 34-50) with:

```python
@pytest.mark.parametrize(
    "h,m,expected",
    [
        (8, 0, "morning"),
        (7, 55, "morning"),
        (8, 4, "morning"),
        (8, 6, None),
        (7, 54, None),
        (12, 0, "noon"),
        (12, 4, "noon"),
        (11, 56, "noon"),
        (11, 55, "noon"),
        (11, 54, None),
        (21, 0, "wipe"),
        (15, 30, None),
    ],
)
def test_pick_slot_within_window(h: int, m: int, expected: str | None) -> None:
    assert refresh.pick_slot(_at(h, m), SLOTS) == expected
```

- [ ] **Step 2: Run the test and confirm it fails on the new boundary cases**

```bash
.venv/bin/python -m pytest daily/tests/test_refresh.py::test_pick_slot_within_window -v
```

Expected: failures on the cases that now expect `None` (e.g. `(8, 6, None)`) because the current window is still ±10.

- [ ] **Step 3: Tighten the constant**

In `daily/refresh.py`, change line 41 from:

```python
SLOT_WINDOW_MINUTES = 10
```

to:

```python
SLOT_WINDOW_MINUTES = 5
```

- [ ] **Step 4: Re-run the test and confirm it passes**

```bash
.venv/bin/python -m pytest daily/tests/test_refresh.py -v
```

Expected: all green, including the full file (no other tests should break).

- [ ] **Step 5: Commit**

```bash
git add daily/refresh.py daily/tests/test_refresh.py
git commit -m "Tighten slot window to 5 minutes for launchd's precise firing"
```

---

### Task 3: Plist template file

A static template with placeholders — kept on disk so it's reviewable and editable independently of the Python.

**Files:**
- Create: `daily/templates/launchagent.plist.template`
- Create: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `daily/tests/test_install_local_scheduler.py` with:

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: FAIL with template not found.

- [ ] **Step 3: Create the template**

```bash
mkdir -p daily/templates
```

Create `daily/templates/launchagent.plist.template` with this exact content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{repo}/daily/refresh.py</string>
        <string>--mode</string>
        <string>auto</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{repo}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add daily/templates/launchagent.plist.template daily/tests/test_install_local_scheduler.py
git commit -m "Add launchd plist template for daily refresh"
```

---

### Task 4: render_plist pure function

The pure-function core of the installer. Takes resolved paths, returns the plist string. Easy to unit-test without filesystem or subprocess concerns.

**Files:**
- Create: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: FAIL — `install_local_scheduler` module does not exist.

- [ ] **Step 3: Create the installer module with constants and `render_plist`**

Create `daily/install_local_scheduler.py` with:

```python
"""Install/uninstall a launchd LaunchAgent that runs daily/refresh.py hourly.

Usage:
    .venv/bin/python daily/install_local_scheduler.py            # install
    .venv/bin/python daily/install_local_scheduler.py --print    # dump plist to stdout
    .venv/bin/python daily/install_local_scheduler.py --uninstall
    .venv/bin/python daily/install_local_scheduler.py --reinstall

macOS only. Linux SEs use cron; Windows SEs use Task Scheduler. See daily/README.md.
"""
from __future__ import annotations

from pathlib import Path

LABEL = "com.slack-dm-generator.daily"

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "daily" / "templates" / "launchagent.plist.template"


def render_plist(
    *,
    python: Path,
    repo: Path,
    label: str,
    stdout_log: Path,
    stderr_log: Path,
) -> str:
    """Substitute placeholders in the plist template. Pure function."""
    template = TEMPLATE_PATH.read_text()
    return template.format(
        python=str(python),
        repo=str(repo),
        label=label,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
    )
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS — 9 tests on Mac, 8 passed + 1 skipped on Linux (plutil test is macOS-only).

- [ ] **Step 5: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Add render_plist pure function for launchd installer"
```

---

### Task 5: --print CLI mode

Adds the CLI entry point with one mode (`--print`) so we have a runnable script before introducing filesystem / subprocess effects.

**Files:**
- Modify: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
def test_cli_print_writes_plist_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    rc = installer.main(["--print"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "<plist" in captured.out
    assert "<key>Label</key>" in captured.out
    assert installer.LABEL in captured.out
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py::test_cli_print_writes_plist_to_stdout -v
```

Expected: FAIL — `installer.main` does not exist.

- [ ] **Step 3: Add path resolvers and the CLI**

Append to `daily/install_local_scheduler.py`:

```python
import argparse
import sys


def repo_python(repo: Path) -> Path:
    """Absolute path to the venv python this repo expects to run with."""
    return repo / ".venv" / "bin" / "python"


def stdout_log_path(repo: Path) -> Path:
    return repo / "daily" / "logs" / "stdout.log"


def stderr_log_path(repo: Path) -> Path:
    return repo / "daily" / "logs" / "stderr.log"


def _render_for_repo(repo: Path) -> str:
    return render_plist(
        python=repo_python(repo),
        repo=repo,
        label=LABEL,
        stdout_log=stdout_log_path(repo),
        stderr_log=stderr_log_path(repo),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--print", dest="print_only", action="store_true",
                       help="Render the plist and write it to stdout. No filesystem changes.")
    group.add_argument("--uninstall", action="store_true",
                       help="Stop and remove the LaunchAgent.")
    group.add_argument("--reinstall", action="store_true",
                       help="Uninstall then install fresh. Use after the repo moves on disk.")
    args = parser.parse_args(argv)

    if args.print_only:
        sys.stdout.write(_render_for_repo(ROOT))
        return 0

    # Install/uninstall/reinstall paths are added in later tasks.
    parser.error("install/uninstall not yet implemented")
    return 2  # unreachable; parser.error exits


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test and confirm it passes**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (10 on Mac, 9 + 1 skipped on Linux).

- [ ] **Step 5: Sanity-check the CLI by hand**

```bash
.venv/bin/python daily/install_local_scheduler.py --print | head -10
```

Expected: the first ~10 lines of a valid plist with absolute paths.

- [ ] **Step 6: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Add --print CLI mode to launchd installer"
```

---

### Task 6: Config validation

Validates `daily/config.json` before generating a plist or talking to launchctl, so the SE gets a friendly error instead of a runtime failure mid-cron.

**Files:**
- Modify: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: 4 failures — `installer.ConfigError` and `installer.validate_config` do not exist.

- [ ] **Step 3: Implement `ConfigError` and `validate_config`**

Add to `daily/install_local_scheduler.py` (above `def main`):

```python
import json

REQUIRED_CONFIG_KEYS = ("recipient_user_id", "senders", "timezone", "slots", "weekdays")


class ConfigError(Exception):
    """Raised when daily/config.json is missing or malformed."""


def validate_config(path: Path) -> dict:
    """Load and validate daily/config.json. Raises ConfigError on any problem."""
    if not path.exists():
        raise ConfigError(
            f"{path} not found. Copy daily/config.example.json to daily/config.json and fill it in."
        )
    try:
        cfg = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}") from e

    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in cfg]
    if missing:
        raise ConfigError(
            f"{path} is missing required field(s): {', '.join(missing)}. "
            f"See daily/config.example.json."
        )
    return cfg
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (14 on Mac, 13 + 1 skipped on Linux).

- [ ] **Step 5: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Validate daily/config.json before installing the LaunchAgent"
```

---

### Task 7: Pre-flight checks

Wraps platform / tokens.json / venv / config validation. One function the install path calls before doing any side effects.

**Files:**
- Modify: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: 5 failures — `installer.preflight` and `installer.PreflightError` do not exist.

- [ ] **Step 3: Implement preflight**

Add to `daily/install_local_scheduler.py` (above `def main`):

```python
class PreflightError(Exception):
    """Raised when the local environment isn't ready for install."""


def preflight(repo: Path) -> dict:
    """Verify the local environment is ready to install the LaunchAgent.

    Returns the parsed config on success. Raises PreflightError or ConfigError
    on failure with a message suitable for direct printing to the SE.
    """
    if sys.platform != "darwin":
        raise PreflightError(
            "This installer is macOS-only. "
            "Linux SEs: see the cron snippet in daily/README.md. "
            "Windows SEs: see the Task Scheduler appendix in daily/README.md."
        )
    if not (repo / "tokens.json").exists():
        raise PreflightError(
            f"{repo / 'tokens.json'} not found. Finish the main SETUP.md flow first."
        )
    venv_python = repo_python(repo)
    if not venv_python.exists():
        raise PreflightError(
            f"{venv_python} not found. Create the venv per SETUP.md Step 3."
        )
    return validate_config(repo / "daily" / "config.json")
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (19 on Mac, 18 + 1 skipped on Linux).

- [ ] **Step 5: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Add preflight checks for the launchd installer"
```

---

### Task 8: Install action (default CLI behavior)

Default path: render the plist, write it to `~/Library/LaunchAgents/`, then `launchctl bootstrap gui/$UID …`. Subprocess and the launch-agents directory are mocked in tests.

**Files:**
- Modify: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: 3 failures — `installer.install` and `installer.launch_agents_dir` do not exist.

- [ ] **Step 3: Implement install + helpers**

Add to `daily/install_local_scheduler.py` (above `def main`):

```python
import os
import subprocess


def launch_agents_dir() -> Path:
    """`~/Library/LaunchAgents`. Wrapped in a function so tests can monkeypatch."""
    return Path.home() / "Library" / "LaunchAgents"


def plist_path() -> Path:
    return launch_agents_dir() / f"{LABEL}.plist"


def install(repo: Path) -> int:
    """Render plist, write to ~/Library/LaunchAgents/, bootstrap with launchctl."""
    preflight(repo)
    target = plist_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render_for_repo(repo))

    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"launchctl bootstrap failed (exit {result.returncode}): "
            f"{result.stderr.strip()}\n"
            f"The plist was written to {target} — fix the underlying issue and rerun.\n"
        )
        return result.returncode

    print(f"Installed {LABEL}.")
    print(f"  plist:  {target}")
    print(f"  logs:   {stdout_log_path(repo)}")
    print(f"          {stderr_log_path(repo)}")
    print("Next run: at the top of the next hour. To smoke-test now:")
    print(f"  {repo_python(repo)} {repo}/daily/refresh.py --mode morning")
    return 0
```

Also update `main()` to dispatch to `install` when no flag is passed. Replace the `parser.error(...)` block with:

```python
    if args.uninstall:
        # Implemented in the next task.
        parser.error("--uninstall not yet implemented")
        return 2
    if args.reinstall:
        # Implemented in a later task.
        parser.error("--reinstall not yet implemented")
        return 2

    return install(ROOT)
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (22 on Mac, 21 + 1 skipped on Linux).

- [ ] **Step 5: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Implement install action for the launchd LaunchAgent"
```

---

### Task 9: Uninstall action (--uninstall)

`launchctl bootout gui/$UID/<label>` then delete the plist. Both steps idempotent (no-op if there's nothing to undo).

**Files:**
- Modify: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: 2 failures — `installer.uninstall` does not exist.

- [ ] **Step 3: Implement uninstall**

Add to `daily/install_local_scheduler.py` (above `def main`):

```python
def uninstall() -> int:
    """Bootout the LaunchAgent and delete the plist. Idempotent."""
    target = plist_path()
    # bootout is best-effort: it returns non-zero if the agent isn't loaded,
    # and we treat that as success.
    subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
    )
    if target.exists():
        target.unlink()
        print(f"Removed {target}.")
    else:
        print(f"No plist at {target} — nothing to remove.")
    return 0
```

In `main()`, replace the `--uninstall` placeholder block with:

```python
    if args.uninstall:
        return uninstall()
```

- [ ] **Step 4: Run the tests and confirm they pass**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (24 on Mac, 23 + 1 skipped on Linux).

- [ ] **Step 5: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Implement uninstall action for the launchd LaunchAgent"
```

---

### Task 10: Reinstall action (--reinstall)

Trivial composition: uninstall then install. Useful when the repo moves on disk or `.venv` is rebuilt.

**Files:**
- Modify: `daily/install_local_scheduler.py`
- Modify: `daily/tests/test_install_local_scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `daily/tests/test_install_local_scheduler.py`:

```python
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
```

- [ ] **Step 2: Run the test and confirm it fails**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: FAIL — `installer.reinstall` does not exist.

- [ ] **Step 3: Implement reinstall**

Add to `daily/install_local_scheduler.py`:

```python
def reinstall(repo: Path) -> int:
    """Bootout + delete + bootstrap fresh."""
    uninstall()
    return install(repo)
```

In `main()`, replace the `--reinstall` placeholder block with:

```python
    if args.reinstall:
        return reinstall(ROOT)
```

- [ ] **Step 4: Run the test and confirm it passes**

```bash
.venv/bin/python -m pytest daily/tests/test_install_local_scheduler.py -v
```

Expected: PASS (25 on Mac, 24 + 1 skipped on Linux).

- [ ] **Step 5: Commit**

```bash
git add daily/install_local_scheduler.py daily/tests/test_install_local_scheduler.py
git commit -m "Implement reinstall action for the launchd LaunchAgent"
```

---

### Task 11: Rewrite daily/README.md

Full rewrite around launchd, with a Linux cron snippet and a Windows Task Scheduler appendix. No mention of GitHub Actions, forks, secrets, or the `.disabled` rename.

**Files:**
- Modify: `daily/README.md` (full replacement)

- [ ] **Step 1: Replace daily/README.md with the new contents**

Open `daily/README.md` and replace its entire contents with:

````markdown
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
````

- [ ] **Step 2: Visually skim the rendered README**

```bash
.venv/bin/python -c "import pathlib; print(pathlib.Path('daily/README.md').read_text()[:1500])"
```

Confirm: no mention of GitHub Actions, forks, secrets, `.disabled`, or
`Run workflow`. Mention of launchd, `install_local_scheduler.py`, the
catch-up command, and the Linux/Windows appendices is present.

- [ ] **Step 3: Commit**

```bash
git add daily/README.md
git commit -m "Rewrite daily/ docs around the launchd installer"
```

---

### Task 12: Update root README and CLAUDE.md

**Files:**
- Modify: `README.md:43-53`
- Modify: `CLAUDE.md` (append a section)

- [ ] **Step 1: Update the "Optional" section in `README.md`**

In `README.md`, replace lines 43-53 (the section currently titled
"## Optional: keep your demo org alive automatically") with:

```markdown
## Optional: keep your demo org alive automatically

The [`daily/`](daily/README.md) folder is an opt-in add-on that runs on a
local schedule (launchd on Mac, cron on Linux, Task Scheduler on Windows)
to send a small batch of generic DMs every weekday morning and noon, then
wipe them at night — so your demo org stays naturally active between demos.
It ships **disabled by default**: nothing runs until you turn it on.

See [`daily/README.md`](daily/README.md) for setup (~5 minutes on Mac).
```

- [ ] **Step 2: Append a section to `CLAUDE.md`**

Append to the end of `CLAUDE.md`:

```markdown

## Daily add-on (`daily/`)

If the user wants to enable the optional `daily/` automation, walk them
through `daily/README.md`. Two notes specific to that add-on:

- **Don't write the launchd .plist by hand.** The repo ships
  `daily/install_local_scheduler.py`, which generates the .plist from
  `daily/config.json` and registers it with `launchctl`. Run that script
  via the Bash tool — don't synthesize plist XML inline.
- **Don't reinstall after JSON edits.** Routine edits to slot times or
  weekdays in `daily/config.json` take effect on the next hourly run —
  the script reads JSON every time. Only run `--reinstall` if the repo
  moves on disk or the venv is rebuilt.
```

- [ ] **Step 3: Verify**

```bash
grep -n "GitHub Actions" README.md daily/README.md CLAUDE.md
```

Expected: no matches.

- [ ] **Step 4: Run the full test suite as a final check**

```bash
.venv/bin/python -m pytest -v
```

Expected: all green (test_refresh + test_pool_schema + test_install_local_scheduler).

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "Update root README and CLAUDE.md for the local-scheduler path"
```

---

## Done

After Task 12, the repo is shippable on the local-scheduler path:
- `daily/refresh.py` unchanged in behavior beyond the tighter slot window
- `daily/install_local_scheduler.py` is the supported install path
- All documentation reflects the new flow
- No GitHub Actions artifacts remain
