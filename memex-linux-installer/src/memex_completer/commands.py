"""Checked commands with bounded duration, persistent logs and live heartbeat."""
import os
import subprocess
import time
from pathlib import Path


def run_command(state, command, *, input=None, timeout=1800, log_dir=None):
    directory = log_dir or Path('/var/log/memex-setup')
    directory.mkdir(parents=True, exist_ok=True, mode=0o755)
    with (directory / 'commands.log').open('ab') as log:
        # All commands use fixed public arguments. Credentials must never use this runner.
        log.write(('\n$ ' + ' '.join(command) + '\n').encode())
        log.flush()
        env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'LC_ALL': 'C'}
        with subprocess.Popen(command, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT, env=env) as process:
            try:
                if input is not None:
                    process.stdin.write(input.encode())
                    process.stdin.close()
                deadline = time.monotonic() + timeout
                while True:
                    state.beat()
                    try:
                        returncode = process.wait(timeout=min(10, max(0.01, deadline - time.monotonic())))
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f'{command[0]} exceeded its time limit. See commands.log.')
                if returncode:
                    raise RuntimeError(f'{command[0]} failed (exit {returncode}). See /var/log/memex-setup/commands.log.')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
