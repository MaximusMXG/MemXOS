from pathlib import Path
from PySide6.QtWidgets import QMessageBox
from memex_engine.run import main
from memex_installer.answers_io import save_answers
from test_storage_backend import answers


def test_cli_cannot_install_using_fixture_disks(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'answers.yaml'
    save_answers(path, answers())
    calls = []
    monkeypatch.setattr('memex_engine.run.install', lambda *args: calls.append(args))
    assert main([str(path), '--install', '--fixture', 'anything.json', '--confirm-disk', 'disk-1']) == 2
    assert not calls


def test_cli_only_reports_installed_after_backend_returns_success(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'answers.yaml'
    save_answers(path, answers())
    def failed(*args):
        raise RuntimeError('failed')
    monkeypatch.setattr('memex_engine.run.install', failed)
    assert main([str(path), '--install', '--confirm-disk', 'disk-1']) == 2
    assert 'os_installed' not in capsys.readouterr().out
