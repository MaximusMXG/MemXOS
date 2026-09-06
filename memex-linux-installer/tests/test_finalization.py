from pathlib import Path
from memex_engine.finalize import configure_files


def test_finalization_enables_service_and_removes_live_autologin(tmp_path):
    root = tmp_path / 'target'
    (root / 'etc/sddm.conf.d').mkdir(parents=True)
    (root / 'etc/sddm.conf.d/live.conf').write_text('[Autologin]\nUser=kubuntu\nSession=plasma\n[Theme]\nCurrent=breeze\n')
    configure_files(root, {'profile': 'gaming', 'language': 'fr', 'username': 'alex',
                          'hostname': 'alex-pc', 'dual_boot': True})
    unit = root / 'etc/systemd/system/multi-user.target.wants/memex-setup.service'
    assert unit.is_symlink() and unit.resolve().is_file()
    assert 'fr_CA' in (root / 'etc/default/locale').read_text()
    assert 'Autologin' not in (root / 'etc/sddm.conf.d/live.conf').read_text()
    assert '[Theme]' in (root / 'etc/sddm.conf.d/live.conf').read_text()
    assert 'false' in (root / 'etc/default/grub.d/90-memex.cfg').read_text()
    assert 'Gaming=true' in (root / 'etc/memex/plasma-profile').read_text()
