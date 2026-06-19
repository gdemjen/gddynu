"""Public IP detection.

Queries a chain of external "what is my IP" services and returns the first
valid answer. Detection is independent of the Dynu update so the address can be
logged even when no update is sent.
"""

from __future__ import annotations

import ipaddress
import logging
import urllib.error
import urllib.request

log = logging.getLogger("gddynu.ipdetect")

_USER_AGENT = "gddynu/0.1 (+https://github.com/gddynu/gddynu)"


def _fetch(url: str, timeout: float) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only by config)
            return resp.read().decode("utf-8", "replace").strip()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.debug("IP service %s failed: %s", url, exc)
        return None


def _parse(text: str | None, want_version: int) -> str | None:
    if not text:
        return None
    # Some services wrap the address in extra text; take the first token.
    candidate = text.split()[0].strip()
    try:
        addr = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if addr.version != want_version:
        return None
    return str(addr)


def _detect(services: list[str], version: int, timeout: float) -> str | None:
    for url in services:
        ip = _parse(_fetch(url, timeout), version)
        if ip is not None:
            log.debug("Detected IPv%d %s via %s", version, ip, url)
            return ip
    return None


def get_public_ipv4(services: list[str], timeout: float = 15.0) -> str | None:
    return _detect(services, 4, timeout)


def get_public_ipv6(services: list[str], timeout: float = 15.0) -> str | None:
    return _detect(services, 6, timeout)
