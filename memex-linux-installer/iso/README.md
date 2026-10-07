# MemXOS ISO build guide — 2026.09.2 RC1

This repository now includes an ISO remix pipeline and a Curtin installation
backend. **An ISO has not yet been built or boot-tested in the development
workspace.** The application package and automated checks can be produced without
privileged access. A successful build is an engineering candidate, not store
release approval.

## Build machine

Use a dedicated Ubuntu/Kubuntu amd64 machine or VM with administrator access,
4 CPU cores, at least 8 GB RAM, an 80 GB or larger build disk (60 GiB free at build
start), and internet access. A normal unprivileged container is insufficient:
mount, chroot and device-node creation capabilities are required. Use a Linux
filesystem for the working directory.

On the build host, install the tools:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-yaml python3-apt git xorriso squashfs-tools \
  gnupg dpkg-dev qemu-system-x86 qemu-utils ovmf libegl1 libopengl0
```

From `memex-linux-installer/`:

```bash
sudo python3 iso/doctor.py --workdir .
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_curtin.py
python3 packaging/build_deb.py
.venv/bin/python scripts/verify_package.py 'dist/memex-installer_2026.9.2~rc1_all.deb'
sudo bash iso/build.sh
```

The default command downloads **Kubuntu 26.04.1 amd64**, authenticates its signed
checksum list using Ubuntu's pinned CD-image key, verifies the ISO, extracts the
filesystem, installs the MemXOS package and dependencies in a private mount
namespace, enables the live-only kiosk, then repacks the image with `xorriso` boot
settings replayed from the original. The Ubuntu shim, GRUB, live kernel and initrd
are retained. Their preservation does not establish that Secure Boot works; the
boot tests below remain mandatory.

Output:

- `dist/ME-Linux-2026.09.2-RC1.iso`
- `dist/ME-Linux-2026.09.2-RC1.iso.sha256`
- `dist/ME-Linux-2026.09.2-RC1.build.json`

To use an existing copy of the exact pinned image:

```bash
sudo bash iso/build.sh --base-iso /path/to/kubuntu-26.04.1-desktop-amd64.iso \
  --workdir /path/to/linux-build-work \
  --output /path/to/output/ME-Linux-2026.09.2-RC1.iso
```

## Store settings and timezone

Each ISO carries one store's settings in `/etc/memex/store.json`. Build one ISO per
timezone with `--store-timezone` (IANA name, validated at build time; default
`America/Edmonton` with a printed notice) and optionally `--store-name`, which is
also appended to the default output filename:

```bash
sudo bash iso/build.sh --store-timezone America/Vancouver --store-name "Burnaby"
```

| Province | `--store-timezone` |
|---|---|
| Alberta | `America/Edmonton` |
| British Columbia | `America/Vancouver` |
| Saskatchewan | `America/Regina` |
| Manitoba | `America/Winnipeg` |
| Ontario | `America/Toronto` |

The installer writes this zone to the customer OS. Dual-boot note: Windows keeps the
hardware clock in local time; Linux stays on UTC and is deliberately left unchanged.

Existing output images are never overwritten. Build workspaces are retained for
diagnosis. The script attempts to unmount its own mounts on exit. If a run fails,
review the terminal log and the printed build workspace before deleting anything.
Do not manually delete a work directory while anything inside it is still mounted.

## VM installation checks

The VM helper creates only new virtual disks. When a Windows reference image is
provided, QEMU writes to a new overlay and leaves the reference image unchanged.
Use a properly licensed Windows test image. Do not attach host physical disks.

```bash
python3 scripts/boot_vm.py --iso dist/ME-Linux-2026.09.2-RC1.iso \
  --workdir /path/to/vms/linux-only --secure-boot
```

Walk through the wizard. The target disk must be `MEMEX-VM-LINUX`. After successful
OS installation, close QEMU and boot the same VM without the ISO:

```bash
python3 scripts/boot_vm.py --workdir /path/to/vms/linux-only --installed
```

Two-disk Windows preservation:

```bash
python3 scripts/boot_vm.py --iso dist/ME-Linux-2026.09.2-RC1.iso \
  --workdir /path/to/vms/two-disk --windows-image /path/to/windows.qcow2 --secure-boot
```

Same-disk resizing:

```bash
python3 scripts/boot_vm.py --iso dist/ME-Linux-2026.09.2-RC1.iso \
  --workdir /path/to/vms/same-disk --windows-image /path/to/windows.qcow2 \
  --same-disk --secure-boot
```

Verify the acceptance checklist in `docs/ACCEPTANCE.md`. Installation requires UEFI.
Same-disk installation requires an unmounted GPT disk, one verified Windows NTFS
volume, one adequate EFI system partition, and a successful read-only NTFS resize
probe. Unsupported, encrypted, dirty or hibernated target layouts must stop before
partition changes. Recovery and MSR partitions must keep their original offsets,
sizes and UUIDs. RAID, LVM and unusual layouts are not part of this candidate's
supported same-disk installation matrix.

## Physical bench

Use a spare SSD/PC, a 16 GB or larger USB, and wired networking. Test AMD, Intel and
NVIDIA systems with Secure Boot enabled. Verify GRUB entries, Windows boot and
files, hardware drivers and profile applications. Drivers or updates may require
one restart; the completer must verify again before displaying Setup complete.
NVIDIA signing/MOK issues are a failed validation, not a completed hand-off.

The standard profiles include proprietary applications and package licence
prompts are preseeded for unattended installation. Review the software manifests
and applicable deployment/licensing requirements before distributing store media.
No customer credentials are included in the base ISO or application package.

## Failure logs to return

- Build: the terminal output and `*.build.json` if produced.
- Live install: `/var/log/memex-install/`.
- First boot: `/var/log/memex-setup/commands.log`, `/var/lib/memex-setup/status.json`,
  and `journalctl -u memex-setup.service`.

Do not send account files from `/run/`; they are temporary installation secrets.
The wizard cleans up its answer file when the engine exits. Passwords are hashed
before any answer file is written, and target account creation passes the hash
through stdin.
