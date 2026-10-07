"""First boot provisioning: checked commands, retryable checkpoints and reboot gate."""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from memex_completer.commands import run_command
from memex_completer.state import SetupState, Status
from memex_installer.errors import ErrorCode
from memex_installer.models import ProfileId
from memex_installer.profiles import load_profile
from memex_installer.secure_io import atomic_write

StepFn = Callable[[SetupState], None]


PROBE_URL = 'http://connectivity-check.ubuntu.com/'


def _nmcli_connectivity() -> str | None:
    if not shutil.which('nmcli'):
        return None
    try:
        out = subprocess.run(['nmcli', '-t', 'networking', 'connectivity', 'check'],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _http_probe(url=PROBE_URL, timeout=5) -> bool:
    # Captive portals answer 200/302; only a genuine 204 means open internet.
    try:
        with urllib.request.build_opener(_NoRedirect).open(url, timeout=timeout) as resp:
            return resp.status == 204
    except (OSError, ValueError):
        return False


def network_up(nmcli=_nmcli_connectivity, http=_http_probe) -> bool:
    if nmcli() == 'full':
        return True
    return http()


def step_gpu(state):
    run_command(state, ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'])
    run_command(state, ['ubuntu-drivers', 'install'])


def step_apt_upgrade(state):
    run_command(state, ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'])
    run_command(state, ['apt-get', '-o', 'Dpkg::Options::=--force-confold', '-y', 'full-upgrade'])


def _repository(state, name, uri, suite, components, key_url):
    run_command(state, ['apt-get', '-y', 'install', 'ca-certificates', 'curl', 'gnupg'])
    directory = Path('/etc/apt/keyrings')
    directory.mkdir(parents=True, exist_ok=True)
    key = directory / (name + '.asc')
    run_command(state, ['curl', '--proto', '=https', '--tlsv1.2', '-fsSL', '--retry', '3',
                        '--max-time', '120', key_url, '-o', str(key)])
    key.chmod(0o644)
    architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    text = f'Types: deb\nURIs: {uri}\nSuites: {suite}\nComponents: {components}\nArchitectures: {architecture}\nSigned-By: {key}\n'
    atomic_write(Path('/etc/apt/sources.list.d') / (name + '.sources'), text, 0o644)
    run_command(state, ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'])


def _install_special(name, state):
    if name == 'vscode':
        _repository(state, 'memex-vscode', 'https://packages.microsoft.com/repos/code',
                    'stable', 'main', 'https://packages.microsoft.com/keys/microsoft.asc')
        run_command(state, ['apt-get', '-y', 'install', 'code'])
    elif name == 'docker':
        import shlex
        fields = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        codename = shlex.split(fields.get('UBUNTU_CODENAME', fields['VERSION_CODENAME']))[0]
        if codename not in {'resolute', 'noble', 'jammy'}:
            raise RuntimeError('Docker repository has not been validated for this Ubuntu release.')
        _repository(state, 'memex-docker', 'https://download.docker.com/linux/ubuntu',
                    codename, 'stable', 'https://download.docker.com/linux/ubuntu/gpg')
        run_command(state, ['apt-get', '-y', 'install', 'docker-ce', 'docker-ce-cli',
                            'containerd.io', 'docker-buildx-plugin', 'docker-compose-plugin'])
        username = Path('/etc/memex/username').read_text().strip()
        run_command(state, ['usermod', '-aG', 'docker', username])
        run_command(state, ['systemctl', 'enable', '--now', 'docker'])
    elif name == 'proton-extras':
        run_command(state, ['apt-get', '-y', 'install', 'steam-devices'])
    else:
        raise ValueError(f'Unknown required installer: {name}')


def preseed_text(profile) -> str:
    lines = ['ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula boolean true']
    if profile == ProfileId.GAMING:
        for owner in ('steam', 'steam-installer'):
            lines += [f'{owner} {owner}/question select I AGREE', f'{owner} {owner}/license note']
    return '\n'.join(lines) + '\n'


def step_packages(state, profile, profiles_dir=None):
    packages = load_profile(profile, profiles_dir)
    if profile == ProfileId.GAMING:
        run_command(state, ['dpkg', '--add-architecture', 'i386'])
        run_command(state, ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'])
    # Preseed package questions for the fixed application profiles.
    run_command(state, ['debconf-set-selections'], input=preseed_text(profile))
    if packages.apt:
        run_command(state, ['apt-get', '-y', 'install', *packages.apt])
    if packages.flatpak:
        run_command(state, ['apt-get', '-y', 'install', 'flatpak'])
        run_command(state, ['flatpak', '--system', 'remote-add', '--if-not-exists',
                            'flathub', 'https://flathub.org/repo/flathub.flatpakrepo'])
        for ref in packages.flatpak:
            run_command(state, ['flatpak', '--system', 'install', '--noninteractive', '-y', 'flathub', ref])
    for special in packages.special:
        _install_special(special, state)


def step_kde_layout(state):
    # The package installs a real Plasma look-and-feel before the customer's first login.
    layout = Path('/usr/share/plasma/look-and-feel/org.memex.desktop/metadata.json')
    if not layout.is_file():
        raise RuntimeError('Memory Express Plasma layout is missing.')
    state.beat()


def step_verify(state):
    display = subprocess.check_output(['lspci', '-Dn'], text=True)
    nvidia = any(('0300:' in line or '0302:' in line) and '10de:' in line for line in display.splitlines())
    if nvidia:
        run_command(state, ['nvidia-smi'], timeout=60)
    audit = subprocess.check_output(['dpkg', '--audit'], text=True, timeout=60)
    state.beat()
    if audit.strip():
        raise RuntimeError('Package configuration is incomplete. Run Retry and check commands.log.')


def default_steps(profile, profiles_dir=None):
    return [('gpu', step_gpu), ('apt_upgrade', step_apt_upgrade),
            ('packages', lambda state: step_packages(state, profile, profiles_dir)),
            ('kde_layout', step_kde_layout)]


def run_completer(steps=None, *, state=None, wait_network=True, network_check=None,
                  profile=ProfileId.HOME, profiles_dir=None, checkpoint=False,
                  reboot_check=None, verify=None):
    state = state or SetupState()
    if state.is_complete():
        return 0
    check_net = network_check or network_up
    step_list = default_steps(profile, profiles_dir) if steps is None else steps
    done_path = state.root / 'steps-done.json'
    current = 'network'
    try:
        done = json.loads(done_path.read_text()) if checkpoint and done_path.exists() else []
        while wait_network and not check_net():
            state.write_status(Status('waiting_network', 'network', ErrorCode.NO_NET.value))
            state.beat()
            time.sleep(5)
        for current, fn in step_list:
            if checkpoint and current in done:
                continue
            state.write_status(Status('running', current))
            state.beat()
            fn(state)
            if checkpoint:
                done.append(current)
                atomic_write(done_path, json.dumps(done), 0o644)
        if reboot_check and reboot_check():
            state.write_status(Status('reboot_required', 'reboot'))
            return 0
        if verify:
            current = 'verify'
            state.write_status(Status('running', current))
            verify(state)
        state.mark_complete()
        return 0
    except Exception as exc:
        state.write_status(Status('failed', current, ErrorCode.STEP_FAIL.value, str(exc)))
        return 1


def _read_profile():
    return ProfileId(Path('/etc/memex/profile').read_text().strip())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-wait-network', action='store_true')
    args = parser.parse_args(argv)
    state = SetupState()
    try:
        profile = _read_profile()
    except (ValueError, OSError):
        state.write_status(Status('failed', 'profile', ErrorCode.STEP_FAIL.value, 'Required profile is missing or invalid.'))
        return 1
    return run_completer(state=state, wait_network=not args.no_wait_network, profile=profile,
                         profiles_dir=Path('/etc/memex/profiles'), checkpoint=True,
                         reboot_check=lambda: Path('/run/reboot-required').exists(), verify=step_verify)


if __name__ == '__main__':
    raise SystemExit(main())
