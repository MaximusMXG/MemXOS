# Memory Express Linux Installer

Shop-floor USB installer for Kubuntu LTS (KDE). Five clicks: language, PC type, disk, customer account, confirm. Then unattended install and a first-boot completer for drivers and frozen apps.

## Quick start (developer)

```bash
cd memex-linux-installer
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
memex-wizard --demo
```

`--demo` uses fixture disks and never touches real hardware.

## Components

| Command | Role |
|---|---|
| `memex-wizard` | Live-USB five-screen kiosk |
| `memex-engine` | Preflight, partition, autoinstall, seed |
| `memex-completer` | Root first-boot service |
| `memex-completer-gui` | Fullscreen setup progress after login |

See `docs/superpowers/specs/2026-08-27-memex-linux-installer-design.md` for the product spec and `iso/README.md` for remixing the ISO.
