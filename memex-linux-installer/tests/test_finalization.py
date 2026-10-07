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


def test_purge_only_installed_packages():
    from memex_engine.finalize import PURGE_CANDIDATES, installed_packages
    status = {'casper': 'install ok installed', 'calamares': 'deinstall ok config-files'}
    assert installed_packages(PURGE_CANDIDATES, lambda p: status.get(p, '')) == ['casper']


def test_groups_filtered_by_target_etc_group():
    from memex_engine.finalize import USER_GROUPS, existing_groups
    text = 'root:x:0:\nsudo:x:27:\nadm:x:4:\nlpadmin:x:7:\nusers:x:100:\n'
    assert existing_groups(USER_GROUPS, text) == ['sudo', 'adm', 'lpadmin', 'users']
    assert {'lpadmin', 'cdrom', 'dip', 'users', 'plugdev'} <= set(USER_GROUPS)
