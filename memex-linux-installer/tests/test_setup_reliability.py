import json
import sys
from pathlib import Path
import pytest
from memex_completer.commands import run_command
from memex_completer.service import run_completer
from memex_completer.state import SetupState, Status
from memex_installer.models import ProfileId
from memex_installer.profiles import load_profile


def test_failed_step_never_marks_complete_and_retry_resumes(tmp_path):
    state = SetupState(tmp_path)
    called = []
    def first(s):
        called.append('first')
    def failure(s):
        raise RuntimeError('download failed')
    assert run_completer([('one', first), ('two', failure)], state=state, wait_network=False, checkpoint=True) == 1
    assert not state.is_complete()
    assert state.read_status().step == 'two'
    assert run_completer([('one', first), ('two', lambda s: called.append('second'))], state=state,
                         wait_network=False, checkpoint=True) == 0
    assert called == ['first', 'second']


def test_reboot_blocks_success_until_next_boot(tmp_path):
    state = SetupState(tmp_path)
    assert run_completer([], state=state, wait_network=False, reboot_check=lambda: True) == 0
    assert not state.is_complete()
    assert state.read_status().phase == 'reboot_required'
    assert run_completer([], state=state, wait_network=False, reboot_check=lambda: False) == 0
    assert state.is_complete()


def test_missing_profile_fails_instead_of_empty_success(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_profile(ProfileId.HOME, tmp_path)


def test_corrupt_status_does_not_crash_gui(tmp_path):
    state = SetupState(tmp_path)
    state.status_path.write_text('{')
    assert state.read_status() is None


def test_failed_status_is_not_later_relabelled_stuck(tmp_path):
    state = SetupState(tmp_path)
    state.write_status(Status('failed', 'packages'))
    state.heartbeat_path.write_text('1')
    assert not state.is_stuck()


def test_checked_command_failure_and_timeout(tmp_path):
    state = SetupState(tmp_path / 'state')
    with pytest.raises(RuntimeError):
        run_command(state, [sys.executable, '-c', 'raise SystemExit(9)'], log_dir=tmp_path / 'logs')
    with pytest.raises(TimeoutError):
        run_command(state, [sys.executable, '-c', 'import time; time.sleep(10)'],
                    timeout=0.03, log_dir=tmp_path / 'logs')
    assert state.heartbeat_age() < 2
    assert (tmp_path / 'logs/commands.log').exists()
