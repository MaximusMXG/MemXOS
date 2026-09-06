#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
pytest -q
python - <<'PY'
from pathlib import Path
import tempfile
from memex_installer.answers_io import save_answers
from memex_installer.models import Answers, InstallMode, Language, LinuxSizePreset, ProfileId
from memex_engine.run import main

answers = Answers(
    language=Language.EN,
    profile=ProfileId.HOME,
    target_disk_id="wwn-nvme-linux",
    target_disk_model="SSD",
    target_disk_size_bytes=2000398934016,
    mode=InstallMode.DUAL_BOOT,
    linux_size=LinuxSizePreset.FULL_DISK,
    display_name="Alex",
    username="alex",
    password="x",
    hostname="alex-pc",
)
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "answers.yaml"
    save_answers(path, answers)
    fixture = Path("tests/fixtures/disks_dual_two.json")
    rc = main([str(path), "--fixture", str(fixture), "--autoinstall-out", str(Path(td) / "ai.yaml"), "--seed-root", str(Path(td) / "root")])
    assert rc == 0, rc
print("dry_run_matrix: ok")
PY
