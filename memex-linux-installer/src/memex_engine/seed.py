"""Seed the installed OS; no answer files or credentials are copied."""
import shutil
from pathlib import Path
from memex_installer.models import Language, ProfileId
from memex_installer.secure_io import atomic_write

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def seed_target(rootfs: Path, profile: ProfileId, language: Language, *, source_root: Path | None = None) -> None:
    source = source_root or PACKAGE_ROOT
    config = rootfs / 'etc/memex'
    config.mkdir(parents=True, exist_ok=True)
    atomic_write(config / 'profile', profile.value + '\n', 0o644)
    atomic_write(config / 'language', language.value + '\n', 0o644)
    shutil.copytree(source / 'profiles', config / 'profiles', dirs_exist_ok=True)
    opt = rootfs / 'opt/memex-linux-installer'
    for package in ('memex_installer', 'memex_completer'):
        shutil.copytree(source / 'src' / package, opt / 'src' / package,
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(source / 'profiles', opt / 'profiles', dirs_exist_ok=True)
    for relative, destination in [
        ('systemd/memex-setup.service', 'etc/systemd/system/memex-setup.service'),
        ('desktop/memex-setup.desktop', 'etc/xdg/autostart/memex-setup.desktop'),
        ('polkit/49-memex-setup.rules', 'etc/polkit-1/rules.d/49-memex-setup.rules'),
    ]:
        dest = rootfs / destination
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / 'packaging' / relative, dest)
    wants = rootfs / 'etc/systemd/system/multi-user.target.wants'
    wants.mkdir(parents=True, exist_ok=True)
    link = wants / 'memex-setup.service'
    if not link.is_symlink():
        link.symlink_to('../memex-setup.service')
    state = rootfs / 'var/lib/memex-setup'
    state.mkdir(parents=True, exist_ok=True, mode=0o755)
    shutil.copytree(source / 'packaging/kde/layout', config / 'kde-layout', dirs_exist_ok=True)
