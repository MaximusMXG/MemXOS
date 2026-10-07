import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication
from memex_installer.store import Store
from memex_wizard.main_window import MainWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_store_name_en_fr(app):
    w = MainWindow(demo=True, store=Store('America/Vancouver', 'Burnaby'))
    assert w.store_label.text() == 'Store: Burnaby · Time zone: America/Vancouver'
    w.language_page.fr.setChecked(True)
    assert w.store_label.text() == 'Magasin : Burnaby · Fuseau horaire : America/Vancouver'
    assert w.next_btn.isEnabled()
    w.close()


def test_store_default(app, tmp_path):
    w = MainWindow(demo=True, store_path=tmp_path / 'missing.json')
    assert w.store_label.text() == 'Store: not set · Time zone: America/Edmonton (default)'
    w.close()


def test_store_invalid_disables_next(app, tmp_path):
    p = tmp_path / 'store.json'
    p.write_text('{bad')
    w = MainWindow(demo=True, store_path=p)
    assert 'invalid' in w.store_label.text()
    assert not w.next_btn.isEnabled()
    w.language_page.fr.setChecked(True)
    assert not w.next_btn.isEnabled()
    w.stack.setCurrentIndex(w.stack.count() - 1)
    w._update_nav()
    assert not w.next_btn.isEnabled() and not w.store_label.isHidden()
    w.close()
