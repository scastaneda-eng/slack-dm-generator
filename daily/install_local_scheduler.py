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
