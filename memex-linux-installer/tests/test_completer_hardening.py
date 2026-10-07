import urllib.error
from memex_completer import service, gui
from memex_completer.state import SetupState
from memex_installer.models import ProfileId


def test_network_nmcli_full_skips_http():
    assert service.network_up(nmcli=lambda: 'full', http=lambda: 1 / 0)


def test_network_falls_back_to_http():
    assert service.network_up(nmcli=lambda: 'portal', http=lambda: True)
    assert service.network_up(nmcli=lambda: None, http=lambda: True)
    assert not service.network_up(nmcli=lambda: 'none', http=lambda: False)


def test_http_probe_requires_204(monkeypatch):
    class Resp:
        def __init__(self, status): self.status = status
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class Opener:
        def __init__(self, r): self.r = r
        def open(self, url, timeout): 
            if isinstance(self.r, Exception): raise self.r
            return self.r
    for r, want in [(Resp(204), True), (Resp(200), False), (urllib.error.URLError('x'), False)]:
        monkeypatch.setattr(service.urllib.request, 'build_opener', lambda *h, r=r: Opener(r))
        assert service._http_probe() is want


def test_nmcli_missing(monkeypatch):
    monkeypatch.setattr(service.shutil, 'which', lambda n: None)
    assert service._nmcli_connectivity() is None


def test_preseed_gaming_covers_both_steam_owners():
    text = service.preseed_text(ProfileId.GAMING)
    for owner in ('steam', 'steam-installer'):
        assert f'{owner} {owner}/question select I AGREE\n' in text
        assert f'{owner} {owner}/license note\n' in text
    assert text.endswith('\n') and 'msttcorefonts' in text


def test_preseed_home_has_no_steam():
    assert 'steam' not in service.preseed_text(ProfileId.HOME)


def test_gui_shown_until_acknowledged(tmp_path):
    state = SetupState(tmp_path / 's')
    ack = tmp_path / 'cfg' / 'ack'
    assert gui.should_show(state, ack)
    state.mark_complete()
    assert gui.should_show(state, ack)
    gui.acknowledge(ack)
    assert not gui.should_show(state, ack)


def test_ack_without_completion_still_shows(tmp_path):
    state = SetupState(tmp_path / 's')
    ack = tmp_path / 'ack'
    gui.acknowledge(ack)
    assert gui.should_show(state, ack)
