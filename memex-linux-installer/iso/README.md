# Building the Memory Express Kubuntu ISO

This remix boots straight into `memex-wizard` (kiosk), not a stock Plasma desktop.

## Requirements

- Official Kubuntu LTS ISO (26.04 or current LTS)
- Host tools: `cubic`, or `live-build` / `xorriso` (document which you use in-store)
- Secure Boot: keep Ubuntu’s signed shim; do not replace the bootloader

## Outline (`build.sh`)

1. Download Kubuntu LTS ISO into `iso/cache/`.
2. Extract / open in Cubic (or equivalent).
3. Install this package into the live system:
   - copy `src/` → `/opt/memex-linux-installer`
   - `pip install` or ship a `.deb`
4. Autostart wizard on live boot (kiosk session):
   - disable default desktop session
   - run `memex-wizard` fullscreen as the live user
5. Include `profiles/`, systemd unit, completer, KDE layout under `/etc/memex` templates.
6. Rebuild ISO; name it `ME-Linux-YYYY.MM.N.iso`.
7. Flash USB the same way stores flash Windows media (`dd`, Rufus, Ventoy as approved).

Version string shown in the wizard: `ME Linux YYYY.MM.N` from `memex_installer.version`.

## Bench checklist before store rollout

- AMD, NVIDIA, Intel systems with Secure Boot on
- Linux-only, same-disk dual-boot (BitLocker off), two-disk dual-boot
- BitLocker on → must show `ME-BITLOCKER`
- French wizard + completer
- Completer success screen before customer hand-off
