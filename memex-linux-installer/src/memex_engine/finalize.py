"""Curtin late stage: customer identity, desktop defaults and first-boot service."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from memex_engine.seed import seed_target
from memex_installer.models import Language, ProfileId
from memex_installer.secure_io import HASH_RE, atomic_write


def configure_files(root: Path, account: dict) -> None:
    lang = Language(account['language'])
    locale = 'fr_CA.UTF-8' if lang == Language.FR else 'en_CA.UTF-8'
    keyboard = 'ca' if lang == Language.FR else 'us'
    seed_target(root, ProfileId(account['profile']), lang)
    atomic_write(root / 'etc/memex/plasma-profile', '[General]\nGaming=' + ('true' if account['profile'] == 'gaming' else 'false') + '\n', 0o644)
    atomic_write(root / 'etc/memex/username', account['username'] + '\n', 0o644)
    atomic_write(root / 'etc/hostname', account['hostname'] + '\n', 0o644)
    atomic_write(root / 'etc/hosts', f"127.0.0.1 localhost\n127.0.1.1 {account['hostname']}\n::1 localhost ip6-localhost ip6-loopback\n", 0o644)
    atomic_write(root / 'etc/default/locale', f'LANG={locale}\n', 0o644)
    atomic_write(root / 'etc/default/keyboard', f'XKBMODEL="pc105"\nXKBLAYOUT="{keyboard}"\nXKBVARIANT=""\nXKBOPTIONS=""\n', 0o644)
    atomic_write(root / 'etc/timezone', 'America/Edmonton\n', 0o644)
    zone = root / 'etc/localtime'
    zone.unlink(missing_ok=True)
    zone.symlink_to('/usr/share/zoneinfo/America/Edmonton')
    atomic_write(root / 'etc/default/grub.d/90-memex.cfg',
                 'GRUB_TIMEOUT_STYLE=menu\nGRUB_TIMEOUT=5\nGRUB_DISABLE_OS_PROBER=' + ('false' if account['dual_boot'] else 'true') + '\n', 0o644)
    (root / 'etc/memex/live-build.json').unlink(missing_ok=True)
    # No live-session autologin may survive onto the customer OS.
    for path in [root / 'etc/sddm.conf', *(root / 'etc/sddm.conf.d').glob('*.conf')]:
        if path.is_file():
            text = re.sub(r'(?ms)^\[Autologin\]\s*\n.*?(?=^\[|\Z)', '', path.read_text())
            atomic_write(path, text, 0o644)
    for path in (root / 'etc/ssh').glob('ssh_host_*'):
        path.unlink()
    atomic_write(root / 'etc/machine-id', '', 0o444)
    (root / 'var/lib/dbus/machine-id').unlink(missing_ok=True)
    machine_id = root / 'var/lib/dbus/machine-id'
    machine_id.parent.mkdir(parents=True, exist_ok=True)
    machine_id.symlink_to('/etc/machine-id')


def finalize(root: Path, account_path: Path) -> None:
    if root.resolve() != Path('/target') or not os.path.ismount(root) or os.geteuid() != 0:
        raise RuntimeError('Finalization requires the mounted Curtin target.')
    account = json.loads(account_path.read_text())
    if not HASH_RE.fullmatch(account['password_hash']):
        raise ValueError('A valid password hash is required.')
    configure_files(root, account)
    def target(*cmd, input=None):
        return subprocess.run(['curtin', 'in-target', '--target', str(root), '--', *cmd],
                              input=input, text=True, check=True, timeout=1800)
    target('useradd', '-m', '-s', '/bin/bash', '-c', account['display_name'], '-G', 'sudo,adm,video,audio,plugdev', account['username'])
    # Hash travels only over stdin; Curtin's argv log contains no password material.
    target('chpasswd', '-e', input=account['username'] + ':' + account['password_hash'] + '\n')
    target('passwd', '-l', 'root')
    desktop = root / 'home' / account['username'] / 'Desktop'
    desktop.mkdir(parents=True, exist_ok=True)
    for name, url, icon in [('Home', str(Path('/home') / account['username']), 'user-home'), ('Trash', 'trash:/', 'user-trash')]:
        atomic_write(desktop / (name + '.desktop'), f'[Desktop Entry]\nType=Link\nName={name}\nIcon={icon}\nURL={url}\n', 0o755)
    target('chown', '-R', account['username'] + ':' + account['username'], '/home/' + account['username'])
    target('locale-gen', 'en_CA.UTF-8', 'fr_CA.UTF-8')
    target('apt-get', '-y', 'purge', 'casper', 'calamares', 'calamares-settings-kubuntu')
    target('update-initramfs', '-u', '-k', 'all')
    target('update-grub')
    atomic_write(root / 'etc/memex/os-installed', 'ok\n', 0o644)


if __name__ == '__main__':
    finalize(Path(sys.argv[1]), Path(sys.argv[2]))
