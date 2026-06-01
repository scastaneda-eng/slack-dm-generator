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
