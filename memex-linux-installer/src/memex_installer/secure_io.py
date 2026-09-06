"""Atomic files and password hashing. Never pass passwords through argv or logs."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

HASH_RE = re.compile(r'^\$6\$(?:rounds=\d+\$)?[./a-zA-Z0-9]{1,16}\$[./a-zA-Z0-9]{86}$')


def password_hash(value: str) -> str:
    if HASH_RE.fullmatch(value):
        return value
    if not value or any(c in value for c in '\n\r\x00'):
        raise ValueError('Password must be nonempty and contain no line breaks.')
    result = subprocess.run(['openssl', 'passwd', '-6', '-stdin'], input=value + '\n',
                            capture_output=True, text=True, check=True, timeout=15)
    hashed = result.stdout.strip()
    if not HASH_RE.fullmatch(hashed):
        raise ValueError('Password hashing failed.')
    return hashed


def atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
