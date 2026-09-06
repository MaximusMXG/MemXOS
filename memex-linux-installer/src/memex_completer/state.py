"""Completer state: heartbeat, status.json, setup-complete flag."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from memex_installer.secure_io import atomic_write

DEFAULT_SETUP_DIR = Path(os.environ.get("MEMEX_SETUP_DIR", "/var/lib/memex-setup"))
STUCK_SECONDS = 180


@dataclass
class Status:
    phase: str  # waiting_network | running | stuck | failed | complete
    step: str
    error_code: str | None = None
    message: str = ""
    updated_at: float = 0.0


class SetupState:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_SETUP_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.heartbeat_path = self.root / "heartbeat"
        self.status_path = self.root / "status.json"
        self.complete_path = self.root / "setup-complete"
        self.retry_path = self.root / "retry"

    def is_complete(self) -> bool:
        return self.complete_path.exists()

    def mark_complete(self) -> None:
        atomic_write(self.complete_path, "ok\n", 0o644)
        self.write_status(
            Status(phase="complete", step="done", message="Setup complete", updated_at=time.time())
        )

    def beat(self) -> None:
        atomic_write(self.heartbeat_path, str(time.time()), 0o644)

    def heartbeat_age(self) -> float | None:
        if not self.heartbeat_path.exists():
            return None
        try:
            stamp = float(self.heartbeat_path.read_text(encoding="utf-8").strip())
        except ValueError:
            return None
        return time.time() - stamp

    def is_stuck(self, timeout: float = STUCK_SECONDS) -> bool:
        age = self.heartbeat_age()
        if age is None:
            return False
        status = self.read_status()
        if status and status.phase in {"complete", "waiting_network", "failed", "reboot_required"}:
            return False
        return age > timeout

    def write_status(self, status: Status) -> None:
        status.updated_at = time.time()
        atomic_write(self.status_path, json.dumps(asdict(status), indent=2), 0o644)

    def read_status(self) -> Status | None:
        if not self.status_path.exists():
            return None
        try:
            data = json.loads(self.status_path.read_text(encoding="utf-8"))
            return Status(**data)
        except (OSError, ValueError, TypeError):
            return None

    def request_retry(self) -> None:
        self.retry_path.write_text(str(time.time()), encoding="utf-8")

    def consume_retry(self) -> bool:
        if not self.retry_path.exists():
            return False
        self.retry_path.unlink()
        return True
