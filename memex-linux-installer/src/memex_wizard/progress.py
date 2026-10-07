"""Install progress from the engine log (curtin stage events). Pure; no Qt."""

from __future__ import annotations

import re
import time
from pathlib import Path

ENGINE_LOG = Path("/var/log/memex-install/engine.log")
STUCK_SECONDS = 600
TAIL_BYTES = 65536

# curtin event (DEBUG, needs -vv): "start: cmd-install/stage-partitioning: ..." (curtin/reporter/events.py)
_START = re.compile(r"\bstart: cmd-install/stage-([a-z_]+)")
_STEPS = {
    "partitioning": "progress_disk",
    "extract": "progress_copy",
    "curthooks": "progress_config",
    "hook": "progress_finish",
    "late": "progress_finish",
}


def log_size(path: Path) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def read_tail(path: Path, size: int = TAIL_BYTES, offset: int = 0) -> str:
    """Last `size` bytes, never before `offset` (engine.log is appended across attempts)."""
    try:
        with Path(path).open("rb") as f:
            f.seek(0, 2)
            f.seek(max(offset, f.tell() - size))
            return f.read().decode(errors="replace")
    except OSError:
        return ""


def stage_key(text: str) -> str:
    """Friendly step key of the latest started stage; preparing disk by default."""
    key = "progress_disk"
    for m in _START.finditer(text):
        key = _STEPS.get(m.group(1), key)
    return key


def engine_progress(path: Path = ENGINE_LOG, started: float = 0.0, now: float | None = None,
                    offset: int = 0) -> tuple[str, float]:
    """(step key, seconds since the log last changed; never before `started`)."""
    now = time.time() if now is None else now
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        mtime = 0.0
    return stage_key(read_tail(path, offset=offset)), max(0.0, now - max(mtime, started))


def is_stuck(idle_seconds: float) -> bool:
    return idle_seconds >= STUCK_SECONDS
