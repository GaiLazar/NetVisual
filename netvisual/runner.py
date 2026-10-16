"""Safe subprocess runner.

Two entry points, chosen by trust level:
  - ``run(cmd)``     — shell string, only for the fixed allow-listed commands.
  - ``run_list(args)`` — arg list (no shell), for anything built from user input.

Both suppress the Windows console window and decode output best-effort.
"""
from __future__ import annotations

import subprocess

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(cmd: str, timeout: int = 12) -> tuple[int, str]:
    """Run a trusted command string; return ``(returncode, combined_output)``.

    Timeout → ``(124, "timeout after {N}s")``; other errors → ``(1, str(err))``.
    """
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout,
                           creationflags=_NO_WINDOW)
        out = p.stdout.decode("utf-8", "replace")
        err = p.stderr.decode("utf-8", "replace")
        return p.returncode, (out + "\n" + err).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except Exception as e:  # noqa
        return 1, str(e)


def run_list(args: list[str], timeout: int = 12) -> tuple[int, str]:
    """Run a command as an arg-list (NO shell) — immune to shell injection.

    Use for commands built from user input (ping / dns / tracert / pathping).
    """
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout,
                           creationflags=_NO_WINDOW)
        out = p.stdout.decode("utf-8", "replace")
        err = p.stderr.decode("utf-8", "replace")
        return p.returncode, (out + "\n" + err).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except Exception as e:  # noqa
        return 1, str(e)
