"""Seed installed OS with completer, profiles, and branding.

Never copies the customer password into the target rootfs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from memex_installer.models import Language, ProfileId

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]


def seed_target(
    rootfs: Path,
    profile: ProfileId,
    language: Language,
    *,
    source_root: Path | None = None,
) -> None:
    root = source_root or PACKAGE_ROOT
    etc_memex = rootfs / "etc" / "memex"
    etc_memex.mkdir(parents=True, exist_ok=True)
    (etc_memex / "profile").write_text(profile.value + "\n", encoding="utf-8")
    (etc_memex / "language").write_text(language.value + "\n", encoding="utf-8")

    profiles_src = root / "profiles"
    profiles_dst = etc_memex / "profiles"
    if profiles_dst.exists():
        shutil.rmtree(profiles_dst)
    shutil.copytree(profiles_src, profiles_dst)

    # Copy Python package into target for completer
    opt = rootfs / "opt" / "memex-linux-installer"
    if opt.exists():
        shutil.rmtree(opt)
    opt.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC_ROOT / "memex_installer", opt / "memex_installer")
    shutil.copytree(SRC_ROOT / "memex_completer", opt / "memex_completer")
    shutil.copytree(profiles_src, opt / "profiles")

    unit_src = root / "packaging" / "systemd" / "memex-setup.service"
    unit_dst = rootfs / "etc" / "systemd" / "system" / "memex-setup.service"
    unit_dst.parent.mkdir(parents=True, exist_ok=True)
    if unit_src.exists():
        shutil.copy2(unit_src, unit_dst)

    desktop_src = root / "packaging" / "desktop" / "memex-setup.desktop"
    desktop_dst = rootfs / "etc" / "xdg" / "autostart" / "memex-setup.desktop"
    desktop_dst.parent.mkdir(parents=True, exist_ok=True)
    if desktop_src.exists():
        shutil.copy2(desktop_src, desktop_dst)

    kde_src = root / "packaging" / "kde" / "layout"
    if kde_src.exists():
        kde_dst = etc_memex / "kde-layout"
        if kde_dst.exists():
            shutil.rmtree(kde_dst)
        shutil.copytree(kde_src, kde_dst)
