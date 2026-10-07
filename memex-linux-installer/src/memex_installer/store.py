"""Per-store settings baked into the ISO at build time (/etc/memex/store.json)."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEZONE = 'America/Edmonton'
STORE_FILE = Path('/etc/memex/store.json')
TZ_RE = re.compile(r'^[A-Za-z_]+(/[A-Za-z0-9_+-]+)+$')


@dataclass(frozen=True)
class Store:
    timezone: str = DEFAULT_TIMEZONE
    name: str = ''


def validate_timezone(tz, root: Path | None = None) -> str:
    """Return tz if safe; with root, it must also exist under root/usr/share/zoneinfo."""
    if not isinstance(tz, str) or not TZ_RE.fullmatch(tz) or '..' in tz.split('/'):
        raise ValueError(f'Invalid timezone: {tz!r}')
    if root is not None:
        base = (root / 'usr/share/zoneinfo').resolve()
        zone = (base / tz).resolve()
        if base not in zone.parents or not zone.is_file():
            raise ValueError(f'Unknown timezone for this image: {tz}')
    return tz


def load_store(path: Path = STORE_FILE) -> Store:
    if not path.exists():
        return Store()
    try:
        data = json.loads(path.read_text())
        name = data.get('name', '')
        if not isinstance(name, str) or len(name) > 80 or any(ord(c) < 32 for c in name):
            raise ValueError('Invalid store name.')
        return Store(validate_timezone(data.get('timezone', DEFAULT_TIMEZONE), None), name)
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f'Unreadable store config {path}: {exc}') from exc
