import time
from pathlib import Path

from memex_completer.service import run_completer
from memex_completer.state import STUCK_SECONDS, SetupState, Status


def test_complete_skips(tmp_path: Path):
    state = SetupState(tmp_path)
    state.mark_complete()
    called = []

    def step(_s):
        called.append(1)

    assert run_completer(steps=[("x", step)], state=state, wait_network=False) == 0
    assert called == []


def test_runs_steps_and_completes(tmp_path: Path):
    state = SetupState(tmp_path)
    order = []

    def make(name):
        def step(s: SetupState):
            order.append(name)
            s.beat()

        return step

    rc = run_completer(
        steps=[("a", make("a")), ("b", make("b"))],
        state=state,
        wait_network=False,
        network_check=lambda: True,
    )
    assert rc == 0
    assert order == ["a", "b"]
    assert state.is_complete()


def test_heartbeat_and_stuck(tmp_path: Path):
    state = SetupState(tmp_path)
    state.write_status(Status(phase="running", step="gpu", message="x"))
    state.heartbeat_path.write_text(str(time.time() - STUCK_SECONDS - 5), encoding="utf-8")
    assert state.is_stuck()
