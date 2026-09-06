from pathlib import Path

from memex_engine.seed import seed_target
from memex_installer.models import Language, ProfileId


def test_seed_writes_profile_not_password(tmp_path: Path):
    rootfs = tmp_path / "root"
    rootfs.mkdir()
    seed_target(rootfs, ProfileId.GAMING, Language.EN)
    assert (rootfs / "etc" / "memex" / "profile").read_text(encoding="utf-8").strip() == "gaming"
    assert (rootfs / "etc" / "memex" / "language").read_text(encoding="utf-8").strip() == "en"
    assert (rootfs / "etc" / "memex" / "profiles" / "gaming.yaml").exists()
    assert not (rootfs / "etc" / "memex" / "answers.yaml").exists()
    assert (rootfs / "opt" / "memex-linux-installer" / "src" / "memex_completer").exists()
