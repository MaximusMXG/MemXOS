from pathlib import Path

from memex_installer.answers_io import load_answers, save_answers
from memex_installer.models import (
    Answers,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)


def test_round_trip(tmp_path: Path):
    answers = Answers(
        language=Language.EN,
        profile=ProfileId.GAMING,
        target_disk_id="wwn-0x1234",
        target_disk_model="Samsung SSD 990",
        target_disk_size_bytes=2_000_000_000_000,
        mode=InstallMode.DUAL_BOOT,
        linux_size=LinuxSizePreset.GB_100,
        display_name="Alex Customer",
        username="alex",
        password="secret",
        hostname="alex-pc",
    )
    path = tmp_path / "answers.yaml"
    save_answers(path, answers)
    loaded = load_answers(path)
    assert loaded.profile == ProfileId.GAMING
    assert loaded.username == "alex"
    assert loaded.mode == InstallMode.DUAL_BOOT
    assert loaded.linux_size == LinuxSizePreset.GB_100
    assert loaded.password.startswith("$6$")
    assert "secret" not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600


def test_hostname_from_username():
    assert Answers.hostname_for("Alex") == "alex-pc"
    assert Answers.hostname_for("bob_smith") == "bob-smith-pc"


def test_username_from_display():
    assert Answers.username_from_display("Alex Customer") == "alex"
