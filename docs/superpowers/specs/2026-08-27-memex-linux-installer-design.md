# Memory Express Linux Installer — Design Spec

Date: 2026-08-27  
Status: draft for review  
Product: company USB installer for Memory Express technicians  
OS: Kubuntu LTS (26.04 as of this spec), KDE Plasma, Windows-like layout

## 1. Problem

Most Memory Express techs do not know Linux. Customers increasingly ask for Linux (Steam share ~4%; Statcounter web share is higher and noisier). The shop already images Windows normally. Techs need a USB that feels like the Windows imager: a few clicks, then a finished PC with drivers and a frozen app set.

## 2. Goals and non-goals

**v1 goals**

- Bootable custom ISO. Tech never sees a Linux desktop or the stock Kubuntu installer.
- Five screens, then unattended Kubuntu install.
- Linux-only, or dual-boot beside Windows that was installed with the normal shop process.
- Auto-detect GPU. Frozen apps per profile (Home / Workstation / Gaming).
- Network assumed on the bench. If there is no network, a first-boot completer retries until the network exists, then finishes drivers and apps.
- BitLocker-on Windows is a hard stop when we would have to shrink that disk.
- Named error screens a Windows-only tech can follow. Freeze and fail are visible. Success is explicit before the PC is handed to the customer.

**Non-goals (not v1)**

- Unattended Windows 11 install from this USB.
- Multiple Linux distros (no CachyOS/Mint/Ubuntu GNOME).
- Tech-selectable extra apps.
- Customer-facing distro shopping or in-store kiosk for shoppers.
- Full offline ISO with cached NVIDIA/Steam payloads.
- LUKS/disk encryption of Linux (adds dual-boot and support cost).

## 3. Users and constraints

- **Primary user:** floor tech who can run the Windows imager and follow on-screen steps.
- **Secondary:** customer at home if the bench had no network; they log in and wait for Setup complete.
- **Language:** English and French (wizard + completer + errors).
- **Trust:** do not rely on the tech to “finish later” from memory. The machine must keep trying until setup succeeds.
- **Passwords:** never write the customer password to disk for later sudo. Completer runs as root via systemd. Login is authentication. The GUI only shows progress, stuck, fail, or complete.

## 4. Architecture

Five components on one custom Kubuntu LTS live ISO:

1. **Live ISO** — UEFI, Secure Boot using Ubuntu’s signed shim. Boots a fullscreen kiosk (Plasma in kiosk mode or equivalent), not a usable desktop.
2. **Wizard** — Qt/KDE app, five screens.
3. **Installer engine** — reads one answers file; preflight; partition; unattended Kubuntu; copies completer + profile onto the new OS.
4. **First-boot completer** — systemd service + fullscreen GUI after login. Retries until network + all steps succeed, then sets `setup-complete`.
5. **Profile manifests** — YAML: `all`, `home`, `workstation`, `gaming`. Changing apps means editing YAML and shipping a new ISO.

```
USB boot → wizard (5 screens) → answers.yaml
    → preflight → partition → unattended Kubuntu
    → reboot (tech removes USB)
    → login as customer
    → completer (drivers → updates → apps)
    → Setup complete
```

## 5. Wizard (five screens)

Order is fixed.

### Screen 1 — Language

- English / Français
- Sets wizard, installer locale, completer, and error strings.
- Keyboard: English → `us`; French → `ca`.

### Screen 2 — PC type

Exactly one:

- **Home**
- **Workstation**
- **Gaming**

This selects the frozen package list. No extra checkboxes.

### Screen 3 — Disk

List every candidate disk with **size, model, and a Windows badge** if Windows is on that disk. Tech selects the **Linux target**.

Then:

- **Linux only** — wipe the selected disk entirely.
- **Dual-boot** — keep Windows; install Linux per the dual-boot rules below.
- If dual-boot **and** Windows is on the **same** disk as the target: Linux size presets (50/50, 100 GB Linux, or all leftover). Preflight rejects a size that would leave Windows with less than **64 GB**.

The USB installer device is listed as blocked or omitted so it cannot be the target.

### Screen 4 — Customer account

- Display name, username (derived, editable), password, password confirm.
- Username: lowercase ASCII, no spaces. Hostname: sanitized username + `-pc` (example: `alex-pc`).
- Timezone: `timedatectl` with network/geo if available; otherwise `America/Edmonton` (chain default). Not a wizard field.

### Screen 5 — Confirm

Shows: language, profile, target disk **model + size in large type**, Linux only vs dual-boot (two-disk dual-boot warns that the **selected disk will be wiped**), Linux size if shrinking, username.

- Linux-only and two-disk dual-boot are destructive to the **selected** disk; the large disk identity is the last chance to abort. Windows on another disk is left alone.
- Install starts only from this screen.

**After the OS copy succeeds**, before reboot, a blocking screen:

> Remove the USB, reboot, log in as **[username]**, leave the PC on until you see **Setup complete**. Do not power off.

## 6. Dual-boot and disks

| Case | Behavior |
|---|---|
| Linux only | Wipe **only** the selected disk. Other disks untouched. |
| Dual-boot, Windows on **selected** disk | BitLocker must be off. Shrink Windows NTFS, create Linux partitions on leftover space. |
| Dual-boot, Windows on a **different** disk | **Allowed.** Warning: two-drive dual-boot; **the selected disk is wiped** and used entirely for Linux; Windows disk is not partitioned. Preferred layout. |
| Dual-boot, Windows on **no** disk | **Stop.** Install Windows first, or choose Linux only. |
| Dual-boot, Windows on selected disk, BitLocker on | **Stop.** Turn BitLocker off in Windows, reboot this USB, retry. Code `ME-BITLOCKER`. |
| Dual-boot, Windows on **other** disk BitLocker-on | Allowed. We are not shrinking that disk. Bootloader still chainloads Windows. |
| Target is the USB | **Stop.** Code `ME-USB-TARGET`. |
| Target disk missing mid-wizard | **Stop.** Reseat drive, restart USB. |

Bootloader: GRUB on the Linux disk’s EFI (or the existing EFI partition when installing beside Windows on the same disk). `os-prober` so the menu shows **Windows** and **Kubuntu**. Secure Boot stays on.

Linux filesystem: ext4. Swap: swap file. No LUKS in v1.

## 7. Installer engine

On Confirm, wizard writes `answers.yaml` (language, profile, target disk by stable id: WWN/serial + model, mode, Linux size if any, username, hashed password handled by autoinstall). Engine reads only that file.

**Preflight** must pass or show a named error (section 9). Then:

1. Partition according to section 6.
2. Run unattended Kubuntu LTS desktop (KDE) with locale, keyboard, user, hostname from answers.
3. Seed the new OS with: profile id, completer unit + GUI, package YAML, this spec’s branding strings.
4. Reboot prompt (USB removal).

Half-finished installs are not auto-repaired. Tech reboots the USB and runs the wizard again. Screen text: do not unplug the Windows drive.

## 8. First-boot completer

Runs until `setup-complete` exists, then never again (unless a later ISO/tool explicitly resets that flag — not a floor action).

**systemd service (root)**

- Wants network-online. If no network, waits and retries; GUI says plug in ethernet.
- Heartbeat file updated at least every 30 seconds while a step runs.
- Log directory: `/var/log/memex-setup/`.
- Order: GPU driver → `apt` full upgrade → profile packages (apt and/or Flatpak system-wide) → KDE layout apply if not already from the ISO.
- GPU: `ubuntu-drivers` autoinstall (NVIDIA proprietary when NVIDIA is present; otherwise AMD/Intel open stack).
- On success: write `setup-complete`, stop retrying.

**GUI (after login, fullscreen)**

- Title: Memory Express Setup (FR equivalent).
- Progress by step name.
- **Stuck:** no heartbeat for 3 minutes → “This looks stuck”, last step, short error, **Retry**.
- **Fail:** driver/apt/download error → “Setup failed”, code, **Retry**. Flag stays unset; next boot retries even if they ignore Retry.
- **Success:** “Setup complete. You can give this PC to the customer.”
- If the root service already finished before login, the GUI opens on **success** immediately (still required for hand-off).

The root service may install drivers/apps before anyone logs in. The GUI is how the floor **knows** it finished. Do not give the PC to the customer until the success screen.

## 9. Error catalog

All errors: chosen language, what happened, what to do, code. No terminal.

| Code | When | Tech action |
|---|---|---|
| `ME-BITLOCKER` | Dual-boot would shrink a BitLocker volume | Decrypt in Windows, reboot USB |
| `ME-NO-WINDOWS` | Dual-boot and no Windows on any disk | Image Windows first, or Linux only |
| `ME-SPACE` | Shrink size does not fit | Smaller Linux size or other disk |
| `ME-USB-TARGET` | Target is installer USB | Pick the PC SSD |
| `ME-DISK-GONE` | Selected disk disappeared | Reseat, restart USB |
| `ME-INSTALL-FAIL` | Unattended Kubuntu died | Reboot USB, run wizard again; do not unplug Windows disk |
| `ME-NO-NET` | Completer waiting | Plug ethernet; leaves retrying |
| `ME-STUCK` | Heartbeat timeout | Retry; leave powered on |
| `ME-STEP-FAIL` | Named completer step failed | Retry; next boot also retries |
| `ME-TWO-DISK` | Not an error — warning | Two-drive dual-boot; selected disk will be **wiped** for Linux |

## 10. Frozen software lists

Techs cannot change these. Edit YAML and rebuild ISO to change company defaults.

**All profiles**

- GPU drivers as in section 8
- Firefox
- VLC
- `ubuntu-restricted-extras` and usual codecs via the completer (network), not bundled on the ISO
- CUPS / printer stack
- Timeshift
- Fastfetch
- Memory Express KDE layout (taskbar, application menu, desktop icons pattern comparable to Windows)

**Home** (plus all)

- LibreOffice
- Thunderbird

**Workstation** (plus all)

- LibreOffice
- Git
- Visual Studio Code (Microsoft repo or official `.deb` via completer)
- Docker Engine + user in `docker` group
- build-essential
- Python 3 + pip/venv

**Gaming** (plus all)

- Steam
- Discord
- GameMode
- MangoHud
- Heroic Games Launcher
- Proton extras (Steam runtime / Proton-GE helper as supported on Kubuntu)

No extra-apps screen.

## 11. KDE layout

Ship one locked Plasma layout so customers get one way to use the PC, not a customization playground:

- Bottom taskbar, Start-style application launcher, system tray, clock.
- Firefox (and Steam on Gaming) pinned.
- Desktop: Home, Trash; no extra widgets.
- Discover (or equivalent) available; we do not hide the OS, we hide our installer.

## 12. Testing

**Logic (no hardware)** — disk classification, BitLocker stop, USB-not-target, two-disk warning (not a stop), no-Windows stop, profile → package list, `setup-complete` skip.

**VM matrix**

- Linux only
- Dual-boot same disk (BitLocker off)
- Dual-boot two disks (warning, no shrink)
- BitLocker on + same-disk dual-boot → `ME-BITLOCKER`
- Dual-boot + no Windows → `ME-NO-WINDOWS`
- French wizard + French completer strings
- Completer with network delayed until a later boot

**Bench before store ISO**

- One AMD, one NVIDIA, one Intel-only; Secure Boot on
- Login, wait, Setup complete
- Smoke: Firefox; LibreOffice on Home/Workstation; Steam on Gaming

**Stuck UI** — stall a fake completer step; expect `ME-STUCK` and Retry.

## 13. ISO build and shop rollout

- Base: official Kubuntu 26.04 LTS (or current Kubuntu LTS at build time).
- Remix: live kiosk + wizard + engine; no default live desktop session.
- Distribution: one ISO image per release; stores flash USB the same way they flash Windows media.
- Version string visible on wizard screen 1 and Confirm (example: `ME Linux 2026.08.1`) for tickets.

## 14. Out of scope notes

CachyOS remains a possible later **optional gaming SKU**, not this product. Windows unattended on the same stick is v2 at earliest.
