# MemXOS — Memory Express Kubuntu installer

**2026.09.2 RC1 build package. The application package builds and automated tests pass. Bundled runtime dependencies,
a bootable ISO and actual installations still require validation on the build host.**

MemXOS is a company USB installer for technicians: language, Home / Workstation /
Gaming profile, disk, customer account, confirmation, followed by installation and
first-boot driver/application setup.

## Implemented

- English/French Qt wizard with fixture preview and guarded live installation.
- Read-only inventory with Windows hive detection, USB/mounted/read-only checks,
  stable disk IDs and fresh identity checks before installation.
- Curtin image-install backend using an exact upstream source pin. Linux-only and
  two-disk installs use explicit GPT/EFI/ext4 layouts. Same-disk plans preserve the
  existing table and resize only a verified NTFS Windows volume within tested
  allocation rules. Actual disk behavior remains untested.
- Password hashing before answer persistence; root-only temporary answer/config
  files; account setup and automatic enabling of the first-boot service.
- Checked driver, apt, Flatpak and special application installers; logs, periodic
  heartbeat, retry checkpoints, reboot-required state and post-reboot verification.
- Microsoft VS Code and Docker official repositories; Steam, Discord, Heroic and
  ProtonUp-Qt in the Gaming profile. Software choices are frozen in YAML; package
  versions are resolved from upstream repositories at installation time.
- Plasma initial layout, live X11 kiosk unit, policy limited to setup-service retry,
  Debian packaging, authenticated base download, ISO build pipeline and VM helper.

## Developer checks

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_curtin.py
python3 packaging/build_deb.py
.venv/bin/python scripts/verify_package.py 'dist/memex-installer_2026.9.2~rc1_all.deb'
.venv/bin/memex-wizard --demo
```

Qt needs native graphics libraries (`libegl1`, `libopengl0`) even for offscreen
checks. For a source checkout without editable installation, set `PYTHONPATH=src`.
`bash scripts/dry_run_matrix.sh` runs the suite and an isolated development seed.

## Commands

| Command | Behavior |
|---|---|
| `memex-wizard --demo` | Fixture preview; no disk writes or saved customer credentials |
| `memex-wizard` | Preview outside the live ISO; real install on the root live kiosk |
| `memex-engine answers.yaml --preview-out report.json` | Password-free preview JSON |
| `memex-engine answers.yaml --install --confirm-disk ID` | Guarded live ISO installation only |
| `memex-completer` | First-boot root service with required steps and final verification |
| `memex-completer-gui` | Progress, Retry, restart and completion screen after login |

Real installation requires the build marker, original media payload, UEFI, root,
a stable unmounted target and explicit disk confirmation. Fixtures and development
seed options cannot be combined with installation. The old `MEMEX_DRY_RUN=0`
partition shortcut and Subiquity autoinstall generator are disabled.

## Build and validation

Follow [iso/README.md](iso/README.md). Use [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) to
record the ISO, VM and hardware tests still required. The build host needs root
mount/chroot/device capabilities, 4 cores, 8 GB RAM and at least 60 GiB free disk.

Known release limitations: the assembled ISO, kiosk startup, real disk resizing,
UEFI/Secure Boot bootloader behavior, package installation and Plasma appearance
have not been exercised on a build host or bench. Network access is required for
the build and should be available during installation; first-boot provisioning
waits for networking. Unsupported same-disk layouts fail closed.

The initial spec and historical plan remain in `../docs/superpowers/`. This README
and the ISO guide describe the implemented Curtin architecture. The original
Subiquity assumptions are superseded. Upstream Curtin source and its AGPL licence
are bundled with the application package; see `packaging/curtin.lock.json`.
