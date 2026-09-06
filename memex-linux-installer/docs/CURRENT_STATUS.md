# Current delivery status — 2026.09.2 RC1

This is a development checkpoint and build kit. It is not a bootable ISO and is
not ready for customer installations.

Included: complete MemXOS source, Home/Workstation/Gaming profiles, installer and
first-boot services, the application .deb, pinned Curtin source, ISO download/build
tools, VM launch tools, and the build/acceptance guides.

Checks completed for this delivery:
- 72 automated tests passed, including offscreen wizard checks.
- Wipe and same-disk configuration schemas passed against pinned Curtin source.
- The application .deb rebuilt successfully.
- Source diff whitespace check passed.

Still pending:
- Full packaged-runtime verification on Ubuntu/Kubuntu. The last runtime check
  stopped at the missing aptsources module; python3-apt has now been added to the
  Debian dependencies and host instructions, but this has not been verified in an
  installed package environment.
- Actual ISO assembly, UEFI/Secure Boot boot tests, and all VM/physical installs.
- Real NTFS resizing, hardware drivers, first-boot application installation, and
  Plasma layout checks.

Build host: Ubuntu/Kubuntu amd64 with administrator access, 4 cores, 8 GB RAM,
80 GB or larger disk and at least 60 GiB free, plus internet access. The current
workspace lacks mount/chroot/device-node capabilities.

Start with memex-linux-installer/iso/README.md. Record remaining tests in
memex-linux-installer/docs/ACCEPTANCE.md. Do not install the .deb on a daily-use
machine just to preview it: it contains system services and desktop configuration.
Use the documented source demo or a disposable VM.
