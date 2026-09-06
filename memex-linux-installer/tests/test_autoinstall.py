from pathlib import Path

from memex_engine.autoinstall import build_autoinstall
from memex_installer.models import (
    Answers,
    InstallMode,
    Language,
    LinuxSizePreset,
    PartitionPlan,
    ProfileId,
)


def _answers(lang: Language = Language.EN) -> Answers:
    return Answers(
        language=lang,
        profile=ProfileId.GAMING,
        target_disk_id="wwn-nvme0",
        target_disk_model="SSD",
        target_disk_size_bytes=1_000_000_000_000,
        mode=InstallMode.LINUX_ONLY,
        linux_size=LinuxSizePreset.FULL_DISK,
        display_name="Alex",
        username="alex",
        password="secret",
        hostname="alex-pc",
    )


def test_autoinstall_identity_and_locale():
    plan = PartitionPlan(
        target_disk_id="wwn-nvme0",
        wipes_target=True,
        shrinks_windows=False,
        two_disk_dual_boot=False,
        linux_size_bytes=1_000_000_000_000,
    )
    data = build_autoinstall(_answers(), plan)
    ai = data["autoinstall"]
    assert ai["identity"]["username"] == "alex"
    assert ai["identity"]["hostname"] == "alex-pc"
    assert ai["locale"].startswith("en_CA")
    assert ai["keyboard"]["layout"] == "us"
    assert "late-commands" in ai


def test_autoinstall_french():
    plan = PartitionPlan(
        target_disk_id="wwn-nvme0",
        wipes_target=True,
        shrinks_windows=False,
        two_disk_dual_boot=False,
    )
    data = build_autoinstall(_answers(Language.FR), plan)
    assert data["autoinstall"]["locale"].startswith("fr_CA")
    assert data["autoinstall"]["keyboard"]["layout"] == "ca"
