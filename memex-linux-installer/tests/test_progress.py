import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import os as _os
import pytest
from PySide6.QtWidgets import QApplication
from memex_wizard import progress
from memex_wizard.main_window import MainWindow
from memex_installer.i18n_ui import UI


def test_stage_mapping():
    assert progress.stage_key("") == "progress_disk"
    log = "start: cmd-install/stage-partitioning/builtin/cmd-block-meta:\nfinish: cmd-install/stage-partitioning/x: SUCCESS\n"
    assert progress.stage_key(log) == "progress_disk"
    log += "start: cmd-install/stage-extract/builtin/cmd-extract:\n"
    assert progress.stage_key(log) == "progress_copy"
    assert progress.stage_key(log + "start: cmd-install/stage-curthooks/x\n") == "progress_config"
    assert progress.stage_key(log + "start: cmd-install/stage-late/x\n") == "progress_finish"
    assert progress.stage_key("start: cmd-install/stage-unknown/x\n") == "progress_disk"


def test_tail_only_and_missing(tmp_path):
    f = tmp_path / "engine.log"
    f.write_text("start: cmd-install/stage-late/x\n" + "x" * 200000)
    assert len(progress.read_tail(f)) <= progress.TAIL_BYTES
    assert progress.stage_key(progress.read_tail(f)) == "progress_disk"
    assert progress.engine_progress(tmp_path / "none", now=100.0) == ("progress_disk", 100.0)
    assert progress.read_tail(tmp_path / "none") == ""


def test_idle_and_stuck(tmp_path):
    f = tmp_path / "e.log"
    f.write_text("start: cmd-install/stage-extract/x\n")
    mt = f.stat().st_mtime
    key, idle = progress.engine_progress(f, started=0, now=mt + 601)
    assert key == "progress_copy" and progress.is_stuck(idle)
    assert not progress.is_stuck(progress.engine_progress(f, 0, mt + 599)[1])
    # stale log from before this run does not count as idle time
    assert progress.engine_progress(f, started=mt + 1000, now=mt + 1005)[1] == 5


def test_strings_both_langs():
    for k in ("progress_disk", "progress_copy", "progress_config", "progress_finish", "progress_elapsed", "progress_stuck"):
        assert k in UI["en"] and k in UI["fr"]
    assert "ME-STUCK" in UI["en"]["progress_stuck"]


def test_window_updates_label(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = MainWindow(demo=True)
    log = tmp_path / "engine.log"
    log.write_text("start: cmd-install/stage-extract/x\n")
    w.engine_log = log
    old = log.stat().st_mtime - 700
    _os.utime(log, (old, old))
    w.engine_started = old - 10
    w._update_progress()
    assert t_ok(w.version_label.text())
    assert not w.stuck_label.isHidden()
    w.progress_bar.show()
    w._cleanup_engine()
    assert w.progress_bar.isHidden() and w.stuck_label.isHidden() and not w.progress_timer.isActive()
    w.close()


def t_ok(text):
    return UI["en"]["progress_copy"] in text and "Elapsed: " in text


def test_progress_ignores_previous_attempts(tmp_path):
    f = tmp_path / "engine.log"
    f.write_text("start: cmd-install/stage-curthooks: configuring installed system\n")
    offset = progress.log_size(f)
    assert progress.engine_progress(f, offset=offset)[0] == "progress_disk"
    with f.open("a") as out:
        out.write("start: cmd-install/stage-extract: writing install sources to disk\n")
    assert progress.engine_progress(f, offset=offset)[0] == "progress_copy"
