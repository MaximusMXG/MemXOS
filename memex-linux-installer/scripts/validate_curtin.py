#!/usr/bin/env python3
"""Validate representative storage plans against the exact bundled Curtin schema."""
import sys
import tarfile
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests'), str(ROOT / 'packaging')]
from build_deb import fetch_curtin
from test_storage_backend import config, answers
from memex_installer.models import InstallMode

with tempfile.TemporaryDirectory(prefix='memex-schema-') as td:
    with tarfile.open(fetch_curtin()) as archive:
        archive.extractall(td, filter='data')
    sys.path.insert(0, str(next(Path(td).iterdir())))
    from curtin.storage_config import validate_config
    for name, cfg in [('same-disk Windows', config()), ('Linux-only wipe', config(answers(InstallMode.LINUX_ONLY)))]:
        validate_config(cfg)
        print(name + ': schema valid')
