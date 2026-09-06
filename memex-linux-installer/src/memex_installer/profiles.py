from __future__ import annotations

from pathlib import Path

import yaml

from memex_installer.models import PackageLists, ProfileId

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required profile is missing: {path.name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "apt": list(data.get("apt") or []),
        "flatpak": list(data.get("flatpak") or []),
        "special": list(data.get("special") or []),
    }


def _merge(base: dict, overlay: dict) -> PackageLists:
    apt = list(dict.fromkeys([*base["apt"], *overlay["apt"]]))
    flatpak = list(dict.fromkeys([*base["flatpak"], *overlay["flatpak"]]))
    special = list(dict.fromkeys([*base["special"], *overlay["special"]]))
    return PackageLists(apt=apt, flatpak=flatpak, special=special)


def load_profile(
    profile: ProfileId,
    profiles_dir: Path | None = None,
) -> PackageLists:
    root = profiles_dir or DEFAULT_PROFILES_DIR
    base = _load_yaml(root / "all.yaml")
    overlay = _load_yaml(root / f"{profile.value}.yaml")
    return _merge(base, overlay)
