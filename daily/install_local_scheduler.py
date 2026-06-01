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

    if args.uninstall:
        return uninstall()
    if args.reinstall:
        # Implemented in a later task.
        parser.error("--reinstall not yet implemented")
        return 2

    return install(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
