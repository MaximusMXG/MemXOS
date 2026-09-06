#!/usr/bin/env python3
"""Launch an isolated UEFI VM. Uses new virtual disks and optional Windows overlays."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def run(*args):
    subprocess.run([str(x) for x in args], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iso', type=Path)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--windows-image', type=Path, help='Read-only backing image; writes go to a new overlay')
    parser.add_argument('--same-disk', action='store_true', help='Install beside Windows in the overlay')
    parser.add_argument('--installed', action='store_true', help='Boot a previously created VM without the ISO')
    parser.add_argument('--secure-boot', action='store_true')
    args = parser.parse_args()
    work = args.workdir.resolve()
    if not args.installed:
        if work.exists() and any(work.iterdir()):
            parser.error('Choose a new or empty VM work directory.')
        if not args.iso or not args.iso.is_file():
            parser.error('Provide the MemXOS ISO.')
        if args.same_disk and not args.windows_image:
            parser.error('--same-disk requires --windows-image.')
        work.mkdir(parents=True, exist_ok=True)
        drives = []
        if args.windows_image:
            source = args.windows_image.resolve()
            info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(source)], text=True))
            overlay = work / 'windows.qcow2'
            run('qemu-img', 'create', '-f', 'qcow2', '-F', info['format'], '-b', source, overlay)
            drives.append({'path': str(overlay), 'serial': 'MEMEX-VM-WINDOWS'})
        if not args.same_disk:
            target = work / 'linux.qcow2'
            run('qemu-img', 'create', '-f', 'qcow2', target, '120G')
            drives.append({'path': str(target), 'serial': 'MEMEX-VM-LINUX'})
        firmware = Path('/usr/share/OVMF')
        code = firmware / ('OVMF_CODE_4M.secboot.fd' if args.secure_boot else 'OVMF_CODE_4M.fd')
        variables = firmware / ('OVMF_VARS_4M.ms.fd' if args.secure_boot else 'OVMF_VARS_4M.fd')
        if not code.is_file() or not variables.is_file():
            parser.error('Install the Ubuntu ovmf package; required firmware files were not found.')
        shutil.copy2(variables, work / 'vars.fd')
        state = {'drives': drives, 'code': str(code), 'secure_boot': args.secure_boot}
        (work / 'vm.json').write_text(json.dumps(state))
    else:
        state = json.loads((work / 'vm.json').read_text())
    command = ['qemu-system-x86_64', '-machine', 'q35,smm=on', '-m', '6144', '-smp', '4',
               '-accel', 'kvm' if os.access('/dev/kvm', os.R_OK | os.W_OK) else 'tcg',
               '-drive', f'if=pflash,format=raw,readonly=on,file={state["code"]}',
               '-drive', f'if=pflash,format=raw,file={work / "vars.fd"}',
               '-device', 'virtio-vga', '-device', 'qemu-xhci', '-device', 'usb-tablet',
               '-nic', 'user,model=virtio-net-pci', '-boot', 'menu=on']
    if state['secure_boot']:
        command += ['-global', 'driver=cfi.pflash01,property=secure,value=on']
    for i, drive in enumerate(state['drives']):
        command += ['-drive', f'file={drive["path"]},if=none,id=disk{i},format=qcow2',
                    '-device', f'nvme,drive=disk{i},serial={drive["serial"]}']
    if not args.installed:
        command += ['-cdrom', str(args.iso.resolve())]
    run(*command)


if __name__ == '__main__':
    main()
