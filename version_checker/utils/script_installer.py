"""Run install scripts for script-based installs."""

from __future__ import annotations

import subprocess

from .auto_installer import run_sudo_command


def run_install_script(
    script: str,
    *,
    sudo: bool = False,
    timeout_seconds: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Run an installation script.

    The script is executed using: sh -lc "<script>".

    Args:
        script: Shell script string to execute.
        sudo: If True, run the script through sudo (non-interactive prompt handled by run_sudo_command).
        timeout_seconds: Optional timeout for execution.

    Returns:
        subprocess.CompletedProcess.
    """
    if sudo:
        # run_sudo_command doesn't support timeouts currently; keep behavior consistent.
        return run_sudo_command(["sh", "-lc", script])

    return subprocess.run(
        ["sh", "-lc", script],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )

