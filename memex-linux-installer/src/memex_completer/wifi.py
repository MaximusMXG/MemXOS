"""Wi-Fi helpers around nmcli for first-boot setup. Passwords are never logged."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Callable

# runner(args, input=None) -> stdout; raises WifiError (or any Exception) on failure.
Runner = Callable[..., str]


class WifiError(Exception):
    """nmcli failed. str() is nmcli's stderr/stdout (never contains argv)."""


@dataclass(frozen=True)
class Network:
    ssid: str
    signal: int
    secured: bool
    in_use: bool = False


def run_nmcli(args: list[str], input: str | None = None) -> str:
    try:
        proc = subprocess.run(args, input=input, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.SubprocessError) as exc:
        raise WifiError(type(exc).__name__) from None
    if proc.returncode != 0:
        raise WifiError((proc.stderr or proc.stdout or "").strip())
    return proc.stdout


def split_terse(line: str) -> list[str]:
    """Split an `nmcli -t` line on ':' honoring '\\:' and '\\\\' escapes."""
    fields, cur, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur.append(line[i + 1])
            i += 2
            continue
        if c == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    fields.append("".join(cur))
    return fields


def scan(runner: Runner = run_nmcli) -> list[Network]:
    out = runner(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"])
    best: dict[str, Network] = {}
    for line in out.splitlines():
        f = split_terse(line)
        if len(f) < 4:
            continue
        ssid = f[1].strip()
        if not ssid:
            continue
        try:
            signal = max(0, min(100, int(f[2])))
        except ValueError:
            signal = 0
        net = Network(ssid, signal, f[3].strip() not in ("", "--"), f[0].strip() == "*")
        old = best.get(ssid)
        if old is None or net.signal > old.signal:
            best[ssid] = net
    return sorted(best.values(), key=lambda n: (-n.signal, n.ssid))


def has_wifi(runner: Runner = run_nmcli) -> bool:
    try:
        out = runner(["nmcli", "-t", "-f", "TYPE", "device"])
    except Exception:
        return False
    return any(line.strip() == "wifi" for line in out.splitlines())


def classify_error(text: str) -> str:
    """Map nmcli output to 'wrong_password' | 'not_found' | 'generic'."""
    low = (text or "").lower()
    if any(s in low for s in ("secrets were required", "invalid password", "wrong password", "802-1x supplicant", "4-way handshake")):
        return "wrong_password"
    if "no network with ssid" in low or "not found" in low and "ssid" in low:
        return "not_found"
    return "generic"


def connect(ssid: str, password: str | None, runner: Runner = run_nmcli) -> None:
    """Connect and persist a system-wide connection. Raises WifiError(kind) with kind from classify_error.

    Password handling: `nmcli --ask` reads the secret from stdin, keeping it off argv (visible in
    /proc to same-user processes). If that attempt fails for a reason other than a bad password/SSID
    (e.g. an nmcli build that insists on a tty), we retry once with `password <pw>` on argv: briefly
    visible to same-user processes, acceptable on a single-user PC during setup. It is never logged,
    and WifiError messages come from nmcli output only.

    System-wide: nmcli run from the user's session creates a connection with no per-user permission
    restriction and psk-flags 0 (secret stored by NetworkManager in /etc/NetworkManager/system-connections,
    root-only 0600), so it autoconnects at boot before login, which the root completer needs. We still
    enforce permissions "" / psk-flags 0 / autoconnect yes explicitly, best effort.
    """
    base = ["nmcli", "device", "wifi", "connect", ssid]
    try:
        if password:
            try:
                runner(["nmcli", "--ask", "device", "wifi", "connect", ssid], input=password + "\n")
            except Exception as exc:
                if classify_error(str(exc)) != "generic":
                    raise
                runner(base + ["password", password])
        else:
            runner(base)
    except Exception as exc:
        raise WifiError(classify_error(str(exc))) from None
    if password:
        try:
            runner(["nmcli", "connection", "modify", ssid, "connection.permissions", "",
                    "802-11-wireless-security.psk-flags", "0", "connection.autoconnect", "yes"])
        except Exception:
            pass  # connected already; defaults are normally system-wide


def bars(signal: int) -> str:
    n = 0 if signal <= 0 else min(4, 1 + signal // 26)
    return "▂▄▆█"[:n].ljust(4, "·")
