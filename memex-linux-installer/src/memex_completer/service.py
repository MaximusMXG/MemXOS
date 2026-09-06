"""Root first-boot completer: gpu → apt → packages → kde_layout."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from memex_completer.state import SetupState, Status
from memex_installer.errors import ErrorCode
from memex_installer.models import ProfileId
from memex_installer.profiles import load_profile

StepFn = Callable[[SetupState], None]


def network_up() -> bool:
    return shutil.which("ping") is not None and subprocess.call(
        ["ping", "-c", "1", "-W", "2", "1.1.1.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) == 0


def step_gpu(state: SetupState) -> None:
    state.beat()
    if shutil.which("ubuntu-drivers"):
        subprocess.run(["ubuntu-drivers", "autoinstall"], check=False)
    state.beat()


def step_apt_upgrade(state: SetupState) -> None:
    state.beat()
    subprocess.run(["apt-get", "update"], check=True)
    state.beat()
    subprocess.run(["apt-get", "-y", "full-upgrade"], check=True)
    state.beat()


def step_packages(state: SetupState, profile: ProfileId, profiles_dir: Path | None = None) -> None:
    pkgs = load_profile(profile, profiles_dir)
    state.beat()
    if pkgs.apt:
        subprocess.run(["apt-get", "-y", "install", "--no-install-recommends", *pkgs.apt], check=True)
    state.beat()
    if pkgs.flatpak and shutil.which("flatpak"):
        subprocess.run(["flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"], check=False)
        for ref in pkgs.flatpak:
            subprocess.run(["flatpak", "install", "-y", "flathub", ref], check=False)
            state.beat()
    for special in pkgs.special:
        _install_special(special, state)
        state.beat()


def _install_special(name: str, state: SetupState) -> None:
    state.beat()
    if name == "vscode":
        # Official Microsoft .deb path — best effort on network
        subprocess.run(
            [
                "bash",
                "-lc",
                "curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg && "
                "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/code stable main' > /etc/apt/sources.list.d/vscode.list && "
                "apt-get update && apt-get -y install code",
            ],
            check=False,
        )
    elif name == "docker":
        subprocess.run(
            [
                "bash",
                "-lc",
                "apt-get -y install ca-certificates curl && "
                "install -m 0755 -d /etc/apt/keyrings && "
                "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && "
                "chmod a+r /etc/apt/keyrings/docker.asc && "
                "apt-get update && apt-get -y install docker-ce docker-ce-cli containerd.io || apt-get -y install docker.io",
            ],
            check=False,
        )
    elif name == "proton-extras":
        subprocess.run(["apt-get", "-y", "install", "steam-devices"], check=False)


def step_kde_layout(state: SetupState) -> None:
    state.beat()
    layout = Path("/etc/memex/kde-layout")
    if layout.exists():
        # Placeholder: copy notes / configs for Plasma look-and-feel
        dest = Path("/etc/memex/kde-layout-applied")
        dest.write_text("applied\n", encoding="utf-8")
    state.beat()


def default_steps(profile: ProfileId, profiles_dir: Path | None = None) -> list[tuple[str, StepFn]]:
    return [
        ("gpu", step_gpu),
        ("apt_upgrade", step_apt_upgrade),
        ("packages", lambda s: step_packages(s, profile, profiles_dir)),
        ("kde_layout", step_kde_layout),
    ]


def run_completer(
    steps: list[tuple[str, StepFn]] | None = None,
    *,
    state: SetupState | None = None,
    wait_network: bool = True,
    network_check: Callable[[], bool] | None = None,
    profile: ProfileId = ProfileId.HOME,
    profiles_dir: Path | None = None,
) -> int:
    state = state or SetupState()
    if state.is_complete():
        return 0

    check_net = network_check or network_up
    step_list = steps or default_steps(profile, profiles_dir)

    if wait_network and not check_net():
        state.write_status(
            Status(phase="waiting_network", step="network", error_code=ErrorCode.NO_NET.value, message="Waiting for network")
        )
        while not check_net():
            time.sleep(5)
            state.beat()

    try:
        for name, fn in step_list:
            state.write_status(Status(phase="running", step=name, message=f"Running {name}"))
            state.beat()
            fn(state)
            state.beat()
        state.mark_complete()
        return 0
    except Exception as exc:  # noqa: BLE001 - surface to GUI
        state.write_status(
            Status(
                phase="failed",
                step=state.read_status().step if state.read_status() else "unknown",
                error_code=ErrorCode.STEP_FAIL.value,
                message=str(exc),
            )
        )
        return 1


def _read_profile() -> ProfileId:
    path = Path("/etc/memex/profile")
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        try:
            return ProfileId(value)
        except ValueError:
            return ProfileId.HOME
    return ProfileId.HOME


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wait-network", action="store_true")
    args = parser.parse_args(argv)
    return run_completer(wait_network=not args.no_wait_network, profile=_read_profile())


if __name__ == "__main__":
    raise SystemExit(main())
