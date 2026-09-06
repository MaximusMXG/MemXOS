# Memory Express Linux Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a custom Kubuntu LTS USB installer (five-screen wizard → unattended install → first-boot completer) so Memory Express techs can ship Home / Workstation / Gaming Linux PCs without knowing Linux.

**Architecture:** Python package `memex_installer` shared by three apps: live-USB wizard (PySide6), installer engine (autoinstall + partition helpers), and first-boot completer (systemd + PySide6 GUI). Frozen YAML profiles select packages. Logic (disk rules, preflight, errors) is pure Python and tested without hardware.

**Tech Stack:** Python 3.12+, PySide6, PyYAML, pytest, Ubuntu autoinstall (`autoinstall.yaml`), systemd, Ubuntu `ubuntu-drivers`, `lsblk`/`blkid` for disk discovery, Kubuntu LTS as ISO base.

## Global Constraints

- Base OS: Kubuntu LTS (26.04 or current Kubuntu LTS at build time); KDE Plasma only (no GNOME).
- Languages: English and French for wizard, completer, and errors.
- Never store the customer password on disk for later sudo; completer runs as root via systemd.
- BitLocker on a volume we would shrink → hard stop `ME-BITLOCKER`.
- Two-disk dual-boot: allowed with warning; selected Linux disk is wiped; Windows disk untouched.
- Frozen app lists only (Home / Workstation / Gaming); no tech checkboxes.
- Network assumed on bench; completer retries until network + steps succeed.
- Error screens: plain language + code; no terminal for floor techs.
- Product version string visible on wizard (example: `ME Linux 2026.09.1`).
- Spec of record: `docs/superpowers/specs/2026-08-27-memex-linux-installer-design.md`.

---

## File Structure

```
memex-linux-installer/
  pyproject.toml
  README.md
  profiles/
    all.yaml
    home.yaml
    workstation.yaml
    gaming.yaml
  src/memex_installer/
    __init__.py
    version.py
    errors.py              # ErrorCode + i18n messages
    models.py              # Answers, DiskInfo, ProfileId, InstallMode
    profiles.py            # load/merge YAML package lists
    disks.py               # discover disks, Windows/BitLocker probes (injectable runners)
    preflight.py           # dual-boot / wipe / USB-target rules
    answers_io.py          # read/write answers.yaml
    i18n.py                # EN/FR strings for wizard + completer
  src/memex_wizard/
    __init__.py
    app.py                 # QApplication entry
    main_window.py         # five-screen QStackedWidget
    pages/
      language.py
      pc_type.py
      disk.py
      account.py
      confirm.py
  src/memex_engine/
    __init__.py
    run.py                 # CLI: memex-engine /path/to/answers.yaml
    autoinstall.py         # generate autoinstall.yaml
    partition.py           # linux-only wipe / same-disk shrink / two-disk wipe
    seed.py                # copy completer + profiles into target
  src/memex_completer/
    __init__.py
    service.py             # root steps: gpu → apt → packages → layout
    state.py               # heartbeat, setup-complete flag
    gui.py                 # fullscreen progress / stuck / fail / success
  packaging/
    systemd/
      memex-setup.service
    desktop/
      memex-setup.desktop  # autostart GUI after login
    kde/
      layout/              # Plasma look-and-feel / panel config
  iso/
    README.md
    build.sh               # remix notes / hooks (later tasks)
  tests/
    test_errors.py
    test_profiles.py
    test_preflight.py
    test_disks.py
    test_answers_io.py
    test_autoinstall.py
    test_completer_state.py
    fixtures/
      disks_linux_only.json
      disks_dual_same.json
      disks_dual_two.json
      disks_bitlocker.json
```

---

### Task 1: Project skeleton + version + error catalog

**Files:**
- Create: `memex-linux-installer/pyproject.toml`
- Create: `memex-linux-installer/README.md`
- Create: `memex-linux-installer/src/memex_installer/__init__.py`
- Create: `memex-linux-installer/src/memex_installer/version.py`
- Create: `memex-linux-installer/src/memex_installer/errors.py`
- Create: `memex-linux-installer/src/memex_installer/i18n.py`
- Create: `memex-linux-installer/tests/test_errors.py`

**Interfaces:**
- Produces: `PRODUCT_VERSION: str`, `ErrorCode` enum, `error_message(code: ErrorCode, lang: str) -> dict` with keys `title`, `body`, `action`

- [ ] **Step 1: Create project layout and `pyproject.toml`**

```toml
[project]
name = "memex-linux-installer"
version = "2026.9.1"
description = "Memory Express Kubuntu LTS shop installer"
requires-python = ">=3.12"
dependencies = [
  "PyYAML>=6.0",
  "PySide6>=6.6",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
memex-wizard = "memex_wizard.app:main"
memex-engine = "memex_engine.run:main"
memex-completer = "memex_completer.service:main"
memex-completer-gui = "memex_completer.gui:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Write failing tests for error catalog**

```python
# tests/test_errors.py
from memex_installer.errors import ErrorCode, error_message
from memex_installer.version import PRODUCT_VERSION


def test_product_version_format():
    assert PRODUCT_VERSION.startswith("ME Linux ")


def test_bitlocker_english():
    msg = error_message(ErrorCode.BITLOCKER, "en")
    assert msg["code"] == "ME-BITLOCKER"
    assert "BitLocker" in msg["title"] or "BitLocker" in msg["body"]
    assert msg["action"]


def test_bitlocker_french():
    msg = error_message(ErrorCode.BITLOCKER, "fr")
    assert msg["code"] == "ME-BITLOCKER"
    assert msg["title"]
    assert msg["body"]


def test_all_codes_have_en_and_fr():
    for code in ErrorCode:
        for lang in ("en", "fr"):
            msg = error_message(code, lang)
            assert msg["code"].startswith("ME-")
            assert msg["title"].strip()
            assert msg["body"].strip()
            assert msg["action"].strip()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd "memex-linux-installer" && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest tests/test_errors.py -v`

Expected: FAIL (modules missing) or import error.

- [ ] **Step 4: Implement version, ErrorCode, i18n messages**

```python
# src/memex_installer/version.py
PRODUCT_VERSION = "ME Linux 2026.09.1"

# src/memex_installer/errors.py
from enum import Enum
from memex_installer.i18n import ERRORS


class ErrorCode(Enum):
    BITLOCKER = "ME-BITLOCKER"
    NO_WINDOWS = "ME-NO-WINDOWS"
    SPACE = "ME-SPACE"
    USB_TARGET = "ME-USB-TARGET"
    DISK_GONE = "ME-DISK-GONE"
    INSTALL_FAIL = "ME-INSTALL-FAIL"
    NO_NET = "ME-NO-NET"
    STUCK = "ME-STUCK"
    STEP_FAIL = "ME-STEP-FAIL"
    TWO_DISK = "ME-TWO-DISK"  # warning, not a hard stop


def error_message(code: ErrorCode, lang: str) -> dict:
    lang = "fr" if lang.startswith("fr") else "en"
    entry = ERRORS[code.value][lang]
    return {
        "code": code.value,
        "title": entry["title"],
        "body": entry["body"],
        "action": entry["action"],
    }
```

Implement `i18n.py` with `ERRORS` dict covering every `ErrorCode` in `en` and `fr` using the wording from the design spec section 9.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_errors.py -v`  
Expected: PASS

```bash
git add memex-linux-installer
git commit -m "feat: scaffold installer package with error catalog"
```

---

### Task 2: Domain models + answers.yaml I/O

**Files:**
- Create: `memex-linux-installer/src/memex_installer/models.py`
- Create: `memex-linux-installer/src/memex_installer/answers_io.py`
- Create: `memex-linux-installer/tests/test_answers_io.py`

**Interfaces:**
- Produces: `ProfileId`, `InstallMode`, `Language`, `LinuxSizePreset`, `Answers`, `load_answers(path) -> Answers`, `save_answers(path, answers) -> None`
- Consumes: none beyond stdlib + PyYAML

- [ ] **Step 1: Write failing tests**

```python
# tests/test_answers_io.py
from pathlib import Path
from memex_installer.models import (
    Answers,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)
from memex_installer.answers_io import load_answers, save_answers


def test_round_trip(tmp_path: Path):
    answers = Answers(
        language=Language.EN,
        profile=ProfileId.GAMING,
        target_disk_id="wwn-0x1234",
        target_disk_model="Samsung SSD 990",
        target_disk_size_bytes=2000_000_000_000,
        mode=InstallMode.DUAL_BOOT,
        linux_size=LinuxSizePreset.GB_100,
        display_name="Alex Customer",
        username="alex",
        password="secret",
        hostname="alex-pc",
    )
    path = tmp_path / "answers.yaml"
    save_answers(path, answers)
    loaded = load_answers(path)
    assert loaded.profile == ProfileId.GAMING
    assert loaded.username == "alex"
    assert loaded.mode == InstallMode.DUAL_BOOT
    assert loaded.linux_size == LinuxSizePreset.GB_100


def test_hostname_from_username():
    assert Answers.hostname_for("Alex") == "alex-pc"
    assert Answers.hostname_for("bob_smith") == "bob_smith-pc"
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest tests/test_answers_io.py -v`

- [ ] **Step 3: Implement models + I/O**

```python
# src/memex_installer/models.py
from dataclasses import dataclass
from enum import Enum
import re


class Language(Enum):
    EN = "en"
    FR = "fr"


class ProfileId(Enum):
    HOME = "home"
    WORKSTATION = "workstation"
    GAMING = "gaming"


class InstallMode(Enum):
    LINUX_ONLY = "linux_only"
    DUAL_BOOT = "dual_boot"


class LinuxSizePreset(Enum):
    HALF = "half"
    GB_100 = "100gb"
    ALL_LEFTOVER = "all_leftover"
    FULL_DISK = "full_disk"  # linux_only or two-disk dual-boot wipe


@dataclass
class Answers:
    language: Language
    profile: ProfileId
    target_disk_id: str
    target_disk_model: str
    target_disk_size_bytes: int
    mode: InstallMode
    linux_size: LinuxSizePreset
    display_name: str
    username: str
    password: str
    hostname: str

    @staticmethod
    def hostname_for(username: str) -> str:
        clean = re.sub(r"[^a-z0-9_-]", "", username.lower())
        return f"{clean or 'user'}-pc"

    @staticmethod
    def username_from_display(display_name: str) -> str:
        first = display_name.strip().split()[0] if display_name.strip() else "user"
        return re.sub(r"[^a-z0-9]", "", first.lower()) or "user"
```

`answers_io.py`: serialize enums as values; password is written only to the live answers file used by the engine during install (not seeded into the installed OS). Document that clearly in a module docstring.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add Answers model and YAML round-trip"
```

---

### Task 3: Profile manifests (frozen package lists)

**Files:**
- Create: `memex-linux-installer/profiles/all.yaml`
- Create: `memex-linux-installer/profiles/home.yaml`
- Create: `memex-linux-installer/profiles/workstation.yaml`
- Create: `memex-linux-installer/profiles/gaming.yaml`
- Create: `memex-linux-installer/src/memex_installer/profiles.py`
- Create: `memex-linux-installer/tests/test_profiles.py`

**Interfaces:**
- Produces: `PackageLists` dataclass (`apt: list[str]`, `flatpak: list[str]`, `special: list[str]`), `load_profile(profile: ProfileId, profiles_dir: Path) -> PackageLists`
- Consumes: `ProfileId`

- [ ] **Step 1: Write YAML files per spec §10**

`all.yaml` apt: `firefox`, `vlc`, `cups`, `timeshift`, `fastfetch`, `ubuntu-restricted-extras`  
`home.yaml`: `libreoffice`, `thunderbird`  
`workstation.yaml`: `libreoffice`, `git`, `build-essential`, `python3`, `python3-pip`, `python3-venv` + special: `vscode`, `docker`  
`gaming.yaml`: `steam`, `gamemode`, `mangohud` + flatpak/special: `discord`, `heroic`, `proton-extras`

- [ ] **Step 2: Write failing tests**

```python
def test_gaming_includes_all_and_steam(profiles_dir):
    pkgs = load_profile(ProfileId.GAMING, profiles_dir)
    assert "firefox" in pkgs.apt
    assert "steam" in pkgs.apt
    assert "libreoffice" not in pkgs.apt


def test_workstation_has_docker_special(profiles_dir):
    pkgs = load_profile(ProfileId.WORKSTATION, profiles_dir)
    assert "docker" in pkgs.special
    assert "vscode" in pkgs.special
```

- [ ] **Step 3: Implement `load_profile` merge (all ∪ profile)**

- [ ] **Step 4: pytest PASS, commit**

```bash
git commit -m "feat: add frozen Home/Workstation/Gaming package profiles"
```

---

### Task 4: Disk discovery models + fixture-based classifier

**Files:**
- Create: `memex-linux-installer/src/memex_installer/disks.py`
- Create: `memex-linux-installer/tests/test_disks.py`
- Create: `memex-linux-installer/tests/fixtures/disks_linux_only.json`
- Create: `memex-linux-installer/tests/fixtures/disks_dual_same.json`
- Create: `memex-linux-installer/tests/fixtures/disks_dual_two.json`
- Create: `memex-linux-installer/tests/fixtures/disks_bitlocker.json`

**Interfaces:**
- Produces: `DiskInfo(id, model, size_bytes, is_usb, has_windows, bitlocker_on, device_path)`, `discover_disks(runner) -> list[DiskInfo]`, `disks_from_snapshot(data: dict) -> list[DiskInfo]`
- Consumes: injectable `runner(cmd: list[str]) -> str` for `lsblk`/`blkid` (tests never call real disks)

- [ ] **Step 1: Write fixtures** representing: one empty NVMe; one disk with Windows no BitLocker; two disks (Windows on sda, empty nvme); Windows + BitLocker flag on target.

- [ ] **Step 2: Failing tests** for `disks_from_snapshot` and USB filtering.

```python
def test_usb_installer_flagged():
    disks = disks_from_snapshot(load_fixture("disks_linux_only.json"))
    assert any(d.is_usb for d in disks)
    assert any(not d.is_usb for d in disks)


def test_windows_badge():
    disks = disks_from_snapshot(load_fixture("disks_dual_same.json"))
    win = [d for d in disks if d.has_windows]
    assert len(win) == 1
    assert win[0].bitlocker_on is False
```

- [ ] **Step 3: Implement snapshot parser + real `discover_disks` using `lsblk -J -o NAME,SIZE,MODEL,TRAN,TYPE,PKNAME,FSTYPE,MOUNTPOINT` and BitLocker heuristic: presence of BitLocker metadata / `FVE-FS` / `BitLocker` signature via `blkid` or NTFS volume flags (document heuristic; tests use explicit fixture field `bitlocker_on`).

- [ ] **Step 4: pytest PASS, commit**

```bash
git commit -m "feat: disk discovery models with injectable fixtures"
```

---

### Task 5: Preflight rules (dual-boot / BitLocker / USB / space)

**Files:**
- Create: `memex-linux-installer/src/memex_installer/preflight.py`
- Create: `memex-linux-installer/tests/test_preflight.py`

**Interfaces:**
- Produces: `PreflightResult(ok: bool, error: ErrorCode | None, warning: ErrorCode | None, plan: PartitionPlan | None)`, `PartitionPlan` with mode details, `run_preflight(answers: Answers, disks: list[DiskInfo]) -> PreflightResult`
- Consumes: `Answers`, `DiskInfo`, `ErrorCode`, `InstallMode`, `LinuxSizePreset`
- Constants: `MIN_WINDOWS_BYTES = 64 * 1024**3`

- [ ] **Step 1: Write failing tests covering every table row in spec §6**

```python
def test_usb_target_rejected():
    ...
    assert result.error == ErrorCode.USB_TARGET

def test_bitlocker_same_disk_rejected():
    ...
    assert result.error == ErrorCode.BITLOCKER

def test_two_disk_dual_boot_warns_and_ok():
    ...
    assert result.ok
    assert result.warning == ErrorCode.TWO_DISK
    assert result.plan.wipes_target is True

def test_dual_boot_no_windows_rejected():
    ...
    assert result.error == ErrorCode.NO_WINDOWS

def test_same_disk_shrink_space_fail():
    ...
    assert result.error == ErrorCode.SPACE

def test_linux_only_ok():
    ...
    assert result.ok and result.plan.wipes_target
```

- [ ] **Step 2: Implement `run_preflight`** exactly per spec §6 (no improvisation).

- [ ] **Step 3: pytest PASS, commit**

```bash
git commit -m "feat: preflight dual-boot and wipe safety rules"
```

---

### Task 6: Wizard shell (five screens, EN/FR, no real install yet)

**Files:**
- Create: `memex-linux-installer/src/memex_wizard/__init__.py`
- Create: `memex-linux-installer/src/memex_wizard/app.py`
- Create: `memex-linux-installer/src/memex_wizard/main_window.py`
- Create: `memex-linux-installer/src/memex_wizard/pages/language.py`
- Create: `memex-linux-installer/src/memex_wizard/pages/pc_type.py`
- Create: `memex-linux-installer/src/memex_wizard/pages/disk.py`
- Create: `memex-linux-installer/src/memex_wizard/pages/account.py`
- Create: `memex-linux-installer/src/memex_wizard/pages/confirm.py`
- Create: `memex-linux-installer/src/memex_installer/i18n_ui.py` (wizard string tables)

**Interfaces:**
- Consumes: `discover_disks` / fixtures in `--demo` mode, `run_preflight`, `Answers`, `PRODUCT_VERSION`, `error_message`
- Produces: writes `answers.yaml` to `/tmp/memex-answers.yaml` (or path from env `MEMEX_ANSWERS_PATH`) on Confirm; calls optional `on_install` callback (engine wired in Task 8)

- [ ] **Step 1: Implement `app.py` with `--demo` flag** that loads fixture disks so the wizard can be exercised on a developer machine without wiping disks.

- [ ] **Step 2: Implement `QStackedWidget` pages** matching spec §5 order. Disk page shows model, size, Windows badge; size presets only when same-disk dual-boot; two-disk shows `ME-TWO-DISK` warning text but allows Next.

- [ ] **Step 3: Confirm page** shows large model+size; Install validates preflight and either shows error dialog or saves answers + emits install signal.

- [ ] **Step 4: Manual smoke:** `memex-wizard --demo` — walk all five screens in EN and FR.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add five-screen Memory Express installer wizard"
```

---

### Task 7: Autoinstall YAML generator

**Files:**
- Create: `memex-linux-installer/src/memex_engine/autoinstall.py`
- Create: `memex-linux-installer/tests/test_autoinstall.py`

**Interfaces:**
- Produces: `build_autoinstall(answers: Answers, plan: PartitionPlan) -> dict` and `write_autoinstall(path, ...)`
- Consumes: `Answers`, `PartitionPlan`

- [ ] **Step 1: Failing test** — generated YAML includes identity username/hostname, locale `en_CA`/`fr_CA`, keyboard `us`/`ca`, storage matching plan mode, and `late-commands` placeholder list for seeding.

- [ ] **Step 2: Implement generator** targeting Ubuntu autoinstall schema used by the live server / `ubuntu-desktop-bootstrap` path documented in `iso/README.md` (link official autoinstall reference in comments).

- [ ] **Step 3: pytest PASS, commit**

```bash
git commit -m "feat: generate Kubuntu autoinstall.yaml from Answers"
```

---

### Task 8: Installer engine CLI + partition helpers + seed

**Files:**
- Create: `memex-linux-installer/src/memex_engine/run.py`
- Create: `memex-linux-installer/src/memex_engine/partition.py`
- Create: `memex-linux-installer/src/memex_engine/seed.py`
- Create: `memex-linux-installer/tests/test_seed.py`

**Interfaces:**
- Produces: `memex-engine answers.yaml` exit 0/1; `seed_target(rootfs: Path, profile: ProfileId, language: Language)` copies profiles, systemd unit, completer scripts, branding
- Consumes: preflight, autoinstall builder

- [ ] **Step 1: Implement `partition.py` with dry-run mode** (`MEMEX_DRY_RUN=1`) that logs planned `sgdisk`/`ntfsresize` operations without executing.

- [ ] **Step 2: Implement `seed.py`** writing `/etc/memex/profile`, completer files, package YAML under target rootfs.

- [ ] **Step 3: `run.py`**: load answers → discover disks → preflight → on failure print error code JSON and exit 2 → dry-run or real partition → write autoinstall → invoke installer (real path behind feature flag; dry-run skips).

- [ ] **Step 4: Wire wizard Confirm to spawn `memex-engine` when not `--demo`.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: installer engine with dry-run partition and OS seed"
```

---

### Task 9: First-boot completer service + state machine

**Files:**
- Create: `memex-linux-installer/src/memex_completer/state.py`
- Create: `memex-linux-installer/src/memex_completer/service.py`
- Create: `memex-linux-installer/packaging/systemd/memex-setup.service`
- Create: `memex-linux-installer/tests/test_completer_state.py`

**Interfaces:**
- Produces: `SetupState` paths under `/var/lib/memex-setup/` (`heartbeat`, `status.json`, `setup-complete`), `run_completer(steps, wait_network=True)` 
- Steps order: `gpu` → `apt_upgrade` → `packages` → `kde_layout`
- Stuck timeout: 180 seconds without heartbeat
- Consumes: `load_profile`, `ErrorCode`

- [ ] **Step 1: Tests for state transitions** — no complete flag → runs; after success → skips; heartbeat updates; stuck detection.

- [ ] **Step 2: Implement service with injectable step runners** so tests do not call apt.

- [ ] **Step 3: Real step runners** (used on Kubuntu): `ubuntu-drivers autoinstall`, `apt-get update && apt-get -y full-upgrade`, install profile apt/flatpak/special, apply KDE layout files.

- [ ] **Step 4: systemd unit** `After=network-online.target`, `WantedBy=multi-user.target`.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: first-boot completer service with heartbeat and retry"
```

---

### Task 10: Completer fullscreen GUI

**Files:**
- Create: `memex-linux-installer/src/memex_completer/gui.py`
- Create: `memex-linux-installer/packaging/desktop/memex-setup.desktop`
- Modify: `memex-linux-installer/src/memex_installer/i18n_ui.py` (completer strings EN/FR)

**Interfaces:**
- Consumes: `status.json` + heartbeat; polls every 2s
- Produces: UI states Progress / NoNet / Stuck / Fail / Success per spec §8

- [ ] **Step 1: Implement fullscreen window** titled "Memory Express Setup" / French equivalent; Retry button triggers `systemctl restart memex-setup.service` or touches a retry flag the service watches.

- [ ] **Step 2: Autostart desktop file** in `/etc/xdg/autostart/` via seed.

- [ ] **Step 3: Manual smoke with fake status files** (`MEMEX_SETUP_DIR` override).

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: completer GUI with stuck/fail/success screens"
```

---

### Task 11: KDE layout package + special package installers

**Files:**
- Create: `memex-linux-installer/packaging/kde/layout/` (panel config / look-and-feel notes)
- Modify: `memex-linux-installer/src/memex_completer/service.py` (vscode, docker, discord, heroic helpers)

**Interfaces:**
- Special handlers: download Microsoft VS Code `.deb` or repo; Docker official apt repo; Flatpak flathub for Discord/Heroic when apt packages unavailable

- [ ] **Step 1: Document exact commands in `service.py` helpers with tests that mock downloads.**

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: KDE layout seed and special app install helpers"
```

---

### Task 12: ISO remix scaffold + tech handoff screen

**Files:**
- Create: `memex-linux-installer/iso/README.md`
- Create: `memex-linux-installer/iso/build.sh`
- Create: `memex-linux-installer/iso/hooks/live-kiosk.sh`
- Modify: wizard post-install screen (USB remove / login / wait)

**Interfaces:**
- Build script documents: download Kubuntu LTS ISO → inject `memex_*` packages → autostart wizard in kiosk → disable stock desktop session
- `build.sh` may be a stub that prints steps until a Linux build host with `cubic`/`live-build` is available; must list exact commands to run

- [ ] **Step 1: Write `iso/README.md`** with Secure Boot note (Ubuntu shim), flash instructions matching Windows USB process, version string location.

- [ ] **Step 2: Post-install blocking screen** in wizard after engine success (spec §5 reboot text).

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: ISO remix scaffold and tech reboot handoff screen"
```

---

### Task 13: End-to-end dry-run checklist script

**Files:**
- Create: `memex-linux-installer/scripts/dry_run_matrix.sh`
- Create: `memex-linux-installer/tests/test_preflight_matrix.py` (parametrize all fixture × mode combinations)

**Interfaces:**
- One command: `./scripts/dry_run_matrix.sh` runs pytest + wizard-less engine dry-runs for each fixture

- [ ] **Step 1: Parametrize preflight matrix** for all cases in spec §12 logic list.

- [ ] **Step 2: Run full suite green.**

- [ ] **Step 3: Commit**

```bash
git commit -m "test: cover full preflight matrix and dry-run script"
```

---

## Spec coverage (self-review)

| Spec section | Task(s) |
|---|---|
| §2 goals / non-goals | Global constraints; Tasks 1–12 |
| §4 architecture | File structure; Tasks 6–10, 12 |
| §5 wizard screens | Task 6 |
| §6 dual-boot rules | Tasks 4–5 |
| §7 installer engine | Tasks 7–8 |
| §8 completer | Tasks 9–10 |
| §9 error catalog | Task 1 |
| §10 package lists | Tasks 3, 11 |
| §11 KDE layout | Task 11 |
| §12 testing | Tasks 1–5, 9, 13 |
| §13 ISO | Task 12 |

## Placeholder / consistency notes

- Password exists in live `answers.yaml` only for autoinstall; never copied into installed rootfs by `seed.py`.
- `ErrorCode.TWO_DISK` is a warning (`result.warning`), never `result.error`.
- `MIN_WINDOWS_BYTES = 64 GiB` matches spec §5/§6.
- Product version format: `ME Linux YYYY.MM.N`.
