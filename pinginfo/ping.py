"""Ping helpers using the system ping command for cross-platform support."""

from __future__ import annotations

import asyncio
import ipaddress
import platform
import re
import socket
from dataclasses import dataclass
from typing import Iterable

_LATENCY_RE = re.compile(r"time[=<]\s*(?P<value>\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


@dataclass(frozen=True)
class PingResult:
    host: str
    latency_ms: float | None
    success: bool
    message: str
    reverse_name: str | None


def _ping_command(host: str, timeout_s: float) -> list[str]:
    system = platform.system().lower()
    if system.startswith("win"):
        timeout_ms = max(1, int(timeout_s * 1000))
        return ["ping", "-n", "1", "-w", str(timeout_ms), host]
    return ["ping", "-c", "1", "-W", str(int(timeout_s)), host]


def ping_command_hint(timeout_s: float) -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return f"ping -n 1 -w {max(1, int(timeout_s * 1000))} <host>"
    return f"ping -c 1 -W {int(timeout_s)} <host>"


def _parse_latency(output: str) -> float | None:
    match = _LATENCY_RE.search(output)
    if not match:
        return None
    return float(match.group("value"))


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


async def _reverse_lookup(host: str) -> str | None:
    if not _is_ip(host):
        return None
    try:
        name, _, _ = await asyncio.to_thread(socket.gethostbyaddr, host)
    except (socket.herror, socket.gaierror):
        return None
    return name


async def ping_once(host: str, timeout_s: float) -> PingResult:
    command = _ping_command(host, timeout_s)
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        return PingResult(host, None, False, "ping command not found", None)

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s + 1)
    except asyncio.TimeoutError:
        proc.kill()
        return PingResult(host, None, False, "timeout", None)

    output = (stdout or b"").decode(errors="ignore")
    latency = _parse_latency(output)
    success = proc.returncode == 0 and latency is not None
    message = "ok" if success else "unreachable"
    reverse_name = await _reverse_lookup(host)
    return PingResult(host, latency, success, message, reverse_name)


async def ping_hosts(hosts: Iterable[str], timeout_s: float) -> list[PingResult]:
    tasks = [ping_once(host, timeout_s) for host in hosts]
    return await asyncio.gather(*tasks)
