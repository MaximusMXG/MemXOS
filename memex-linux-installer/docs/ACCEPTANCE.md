# MemXOS RC1 acceptance record

## Completed in the development workspace

- [x] Python logic, CLI and offscreen wizard regression tests.
- [x] Wipe and same-disk configurations validated against the pinned Curtin schema.
- [x] Application Debian package built and extracted for inspection.
- [x] Install entry point refuses non-live environments and fixture-based writes.
- [x] Same-disk plans preserve all enumerated GPT partitions, including recovery/MSR.
- [x] Required package failures prevent Setup complete; retry resumes unfinished steps.
- [x] Password hashing, private answer files and password-free preview reports.

## Required on the build host

- [ ] ISO assembly completes; output checksum and build manifest are recorded.
- [ ] ISO boots in a UEFI VM into the MemXOS kiosk.
- [ ] English and French full wizard paths render correctly.
- [ ] Linux-only installs, reboots from the SSD and signs in as the customer.
- [ ] Two-disk install leaves the Windows reference disk unchanged.
- [ ] Same-disk install preserves recovery/MSR/EFI and Windows files; both OSes boot.
- [ ] NTFS dirty/hibernated and BitLocker same-disk cases stop without disk writes.
- [ ] Removal, identity change, USB selection and read-only target cases stop.
- [ ] Home, Workstation and Gaming finish successfully; applications launch.
- [ ] Interrupted downloads and later networking recover through Retry and reboot.
- [ ] Reboot-required state does not display Setup complete prematurely.
- [ ] The installed system has no live autologin or passwordless live-user sudo rule.
- [ ] Normal customer boots start Plasma, not the installer kiosk.

## Required on the bench before store media

- [ ] AMD GPU / Secure Boot on.
- [ ] Intel-only / Secure Boot on.
- [ ] NVIDIA GPU / Secure Boot on; nvidia-smi and application acceleration work.
- [ ] Windows and Linux GRUB entries work for each supported dual-boot case.
- [ ] Network, audio, printer discovery, suspend, shutdown and restart checked.
- [ ] KDE panel, pinned apps, Home and Trash icons checked.
- [ ] Frozen application and licence choices approved for store distribution.
- [ ] Version, final ISO SHA256, test dates and tester recorded in a release ticket.

No store-ready claim should be made until these host and bench results exist.
