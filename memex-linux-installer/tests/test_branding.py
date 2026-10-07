import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / 'packaging/branding'
sys.path.insert(0, str(ROOT / 'packaging'))
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deb  # noqa: E402
import make_logo  # noqa: E402


def test_logo_crop_and_shrink():
    grid = make_logo.crop((BRANDING / 'me-logo-source.txt').read_text().splitlines())
    assert grid[0].strip() and grid[-1].strip()
    assert min(len(r) - len(r.lstrip()) for r in grid if r.strip()) == 0
    small = make_logo.shrink(grid)
    assert small and max(map(len, small)) <= 40
    assert all(r == r.rstrip() for r in small)


def test_logo_files_match_script():
    grid = make_logo.crop((BRANDING / 'me-logo-source.txt').read_text().splitlines())
    assert (BRANDING / 'memxos-logo.txt').read_text() == '\n'.join(make_logo.shrink(grid)) + '\n'
    assert (BRANDING / 'memxos-logo-large.txt').read_text().strip()


def test_fastfetch_config_parses_and_references_logo():
    text = (BRANDING / 'fastfetch/config.jsonc').read_text()
    text = text.replace('@MEMXOS_VERSION@', '2026.09')
    config = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
    assert Path(config['logo']['source']).name == 'memxos-logo.txt'
    assert (BRANDING / Path(config['logo']['source']).name).exists()
    os_module = next(m for m in config['modules'] if isinstance(m, dict) and m['type'] == 'os')
    assert '{pretty-name}' in os_module['format'] and 'MemXOS 2026.09' in os_module['format']


def test_brand_version_matches_product_version():
    assert re.fullmatch(r'\d{4}\.\d{2}', build_deb.brand_version())


@pytest.mark.skipif(not shutil.which('dpkg-deb') or not (ROOT / 'vendor/curtin.tar.gz').exists(),
                    reason='needs dpkg-deb and cached curtin')
def test_deb_contains_branding(tmp_path):
    deb = build_deb.build(tmp_path)
    listing = subprocess.run(['dpkg-deb', '-c', str(deb)], capture_output=True, text=True, check=True).stdout
    for path in ('etc/xdg/fastfetch/config.jsonc', 'etc/xdg/kcm-about-distrorc',
                 'usr/share/memxos/memxos-logo.txt', 'usr/share/memxos/memxos-logo-large.txt'):
        assert './' + path in listing
    assert 'etc/os-release' not in listing
