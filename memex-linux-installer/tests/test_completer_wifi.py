import pytest

from memex_completer import wifi


def test_scan_parses_escapes_dedupes_sorts():
    out = "\n".join([
        "*:Home\\:5G:70:WPA2",
        ":Home\\:5G:40:WPA2",
        ":Cafe:85:",
        "::90:WPA2",
        ":Back\\\\slash:20:WPA3",
    ])
    calls = []
    nets = wifi.scan(lambda a, **k: calls.append(a) or out)
    assert [n.ssid for n in nets] == ["Cafe", "Home:5G", "Back\\slash"]
    assert [n.signal for n in nets] == [85, 70, 20]
    assert [n.secured for n in nets] == [False, True, True]
    assert nets[1].in_use
    assert calls[0][:3] == ["nmcli", "-t", "-f"] and "--rescan" in calls[0]


def test_has_wifi():
    assert wifi.has_wifi(lambda a, **k: "ethernet\nwifi\nloopback\n")
    assert not wifi.has_wifi(lambda a, **k: "ethernet\nloopback\n")

    def boom(a, **k):
        raise wifi.WifiError("x")

    assert not wifi.has_wifi(boom)


def test_connect_password_via_stdin_not_argv():
    calls = []
    wifi.connect("Home", "s3cret", lambda a, input=None: calls.append((a, input)) or "")
    assert calls[0] == (["nmcli", "--ask", "device", "wifi", "connect", "Home"], "s3cret\n")
    assert all("s3cret" not in " ".join(a) for a, _ in calls)
    assert calls[1][0][:4] == ["nmcli", "connection", "modify", "Home"]
    assert "802-11-wireless-security.psk-flags" in calls[1][0]


def test_connect_open_network():
    calls = []
    wifi.connect("Cafe", None, lambda a, input=None: calls.append(a) or "")
    assert calls == [["nmcli", "device", "wifi", "connect", "Cafe"]]


def test_connect_falls_back_to_argv_on_generic_failure():
    calls = []

    def runner(a, input=None):
        calls.append(a)
        if "--ask" in a:
            raise wifi.WifiError("Error: needs tty")
        return ""

    wifi.connect("Home", "pw", runner)
    assert ["nmcli", "device", "wifi", "connect", "Home", "password", "pw"] in calls


@pytest.mark.parametrize("text,kind", [
    ("Error: Connection activation failed: Secrets were required, but not provided.", "wrong_password"),
    ("Error: No network with SSID 'x' found.", "not_found"),
    ("Error: something odd", "generic"),
])
def test_connect_error_mapping_no_password_leak(text, kind):
    def runner(a, input=None):
        raise wifi.WifiError(text + " pw123")

    with pytest.raises(wifi.WifiError) as e:
        wifi.connect("Home", "pw123", runner)
    assert str(e.value) == kind


def _window(tmp_path, monkeypatch, has, phase):
    from PySide6.QtWidgets import QApplication
    from memex_completer import gui
    from memex_completer.state import SetupState, Status

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(gui.wifi, "has_wifi", lambda *a, **k: has)
    st = SetupState(tmp_path)
    st.write_status(Status(phase=phase, step="net", updated_at=__import__("time").time()))
    st.heartbeat_path.write_text("1")
    w = gui.CompleterWindow(st)
    w.lang = "en"
    return w


def test_wifi_button_shown_when_waiting_and_wifi(tmp_path, monkeypatch):
    w = _window(tmp_path, monkeypatch, True, "waiting_network")
    assert not w.wifi_btn.isHidden() and not w.netset_btn.isHidden()


def test_wifi_button_hidden_without_wifi(tmp_path, monkeypatch):
    w = _window(tmp_path, monkeypatch, False, "waiting_network")
    assert w.wifi_btn.isHidden() and not w.netset_btn.isHidden()


def test_wifi_button_hidden_in_other_phase(tmp_path, monkeypatch):
    w = _window(tmp_path, monkeypatch, True, "running")
    assert w.wifi_btn.isHidden() and w.netset_btn.isHidden()
