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
