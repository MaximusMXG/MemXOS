from pathlib import Path

import pytest

from memex_installer.models import ProfileId
from memex_installer.profiles import load_profile

PROFILES = Path(__file__).resolve().parents[1] / "profiles"


@pytest.fixture
def profiles_dir() -> Path:
    return PROFILES


def test_gaming_includes_all_and_steam(profiles_dir: Path):
    pkgs = load_profile(ProfileId.GAMING, profiles_dir)
    assert "firefox" in pkgs.apt
    assert "steam" in pkgs.apt
    assert "libreoffice" not in pkgs.apt


def test_workstation_has_docker_special(profiles_dir: Path):
    pkgs = load_profile(ProfileId.WORKSTATION, profiles_dir)
    assert "docker" in pkgs.special
    assert "vscode" in pkgs.special
    assert "git" in pkgs.apt


def test_home_has_libreoffice(profiles_dir: Path):
    pkgs = load_profile(ProfileId.HOME, profiles_dir)
    assert "libreoffice" in pkgs.apt
    assert "thunderbird" in pkgs.apt
    assert "steam" not in pkgs.apt
