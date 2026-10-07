"""Offscreen GUI regressions for actual technician interactions."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QCoreApplication, QEvent
from memex_wizard.main_window import MainWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    window = MainWindow(demo=True)
    yield window
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_mode_and_size_are_independent(window):
    page = window.disk_page
    assert page.linux_only.isChecked()
    page._ask_dual_boot = lambda: True
    page.advanced.setChecked(True)
    page.dual_boot.setChecked(True)
    page.size_half.setChecked(True)
    assert page.dual_boot.isChecked()
    assert not page.linux_only.isChecked()
    assert not page.size_100.isChecked()


def test_return_to_disk_keeps_selection(window):
    page = window.disk_page
    page.list.setCurrentRow(1)
    selected = page._selected_disk().id
    page._populate()
    assert page._selected_disk().id == selected


@pytest.mark.parametrize('lang', ['en', 'fr'])
def test_demo_shows_preview_without_writing_customer_answers(window, tmp_path, monkeypatch, lang):
    window.lang = lang
    window.disk_page.list.setCurrentRow(1)
    assert window.disk_page.validate()
    window.display_name, window.username, window.password = 'Alex', 'alex', 'customer-secret'
    answers_path = tmp_path / 'answers.yaml'
    monkeypatch.setenv('MEMEX_ANSWERS_PATH', str(answers_path))
    shown = []
    monkeypatch.setattr(QMessageBox, 'information', lambda parent, title, body: shown.append((title, body)))
    window._install()
    assert len(shown) == 1
    assert 'aperçu' in shown[0][1].lower() if lang == 'fr' else 'preview' in shown[0][1].lower()
    assert not answers_path.exists()
    assert 'customer-secret' not in str(shown)


def test_live_discovery_failure_never_uses_fixture_disks(window, monkeypatch):
    def fail():
        raise OSError('discovery unavailable')
    monkeypatch.setattr('memex_wizard.main_window.discover_disks', fail)
    messages = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: messages.append(args))
    window.demo = False
    window._load_disks('disks_dual_two.json')
    assert window.disks == []
    assert messages


def _disk_idx(window, windows):
    return next(i for i, d in enumerate(window.disks) if d.has_windows == windows and not d.is_usb)


def test_advanced_hidden_and_resets(window):
    page = window.disk_page
    assert not page.advanced.isChecked() and page.advanced_box.isHidden()
    page._ask_dual_boot = lambda: True
    page.advanced.setChecked(True)
    page.dual_boot.setChecked(True)
    page.advanced.setChecked(False)
    assert page.linux_only.isChecked() and page.advanced_box.isHidden()


def test_dual_boot_cancel_reverts(window):
    page = window.disk_page
    page._ask_dual_boot = lambda: False
    page.advanced.setChecked(True)
    page.dual_boot.setChecked(True)
    assert page.linux_only.isChecked() and not page.dual_boot.isChecked()


def test_dual_warning_ok_needs_ack(app, window):
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QCheckBox
    from PySide6.QtCore import QTimer
    from memex_wizard.pages import disk as d
    seen = {}
    def probe():
        dlg = app.activeModalWidget()
        ok = dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        seen['before'] = ok.isEnabled()
        dlg.findChild(QCheckBox).setChecked(True)
        seen['after'] = ok.isEnabled()
        ok.click()
    QTimer.singleShot(0, probe)
    assert d.confirm_dual_boot(window, 'fr') is True
    assert seen == {'before': False, 'after': True}


def test_windows_erase_warning_and_confirm_gate(window):
    page = window.disk_page
    page.list.setCurrentRow(_disk_idx(window, True))
    assert not page.windows_warning.isHidden()
    assert page.validate()
    window.stack.setCurrentIndex(window.stack.count() - 1)
    window._update_nav()
    assert not window.next_btn.isEnabled()
    window.confirm_page.erase_ack.setChecked(True)
    assert window.next_btn.isEnabled()
    page.list.setCurrentRow(_disk_idx(window, False))
    assert page.windows_warning.isHidden()
    assert page.validate()
    window._update_nav()
    assert window.next_btn.isEnabled() and window.confirm_page.erase_ack.isHidden()


def test_confirm_dual_summary(window):
    page = window.disk_page
    page._ask_dual_boot = lambda: True
    page.advanced.setChecked(True)
    page.dual_boot.setChecked(True)
    page.list.setCurrentRow(_disk_idx(window, False))
    assert page.validate()
    window.confirm_page._refresh()
    assert not window.confirm_page.dual_note.isHidden()
    assert window.confirm_page.can_install()
