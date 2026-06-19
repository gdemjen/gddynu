"""Dynu IP Update Protocol client.

Reference: https://www.dynu.com/en-US/DynamicDNS/IP-Update-Protocol
"""

from __future__ import annotations

import hashlib
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("gddynu.dynu")

_USER_AGENT = "gddynu/0.1 (+https://github.com/gddynu/gddynu)"


class Outcome(Enum):
    """How the caller should treat a Dynu response."""

    SUCCESS = "success"  # update applied or no change needed
    TRANSIENT = "transient"  # retry later (server busy / maintenance)
    FATAL = "fatal"  # configuration/account problem — retrying won't help


# Maps the documented response codes to an outcome class. The text returned by
# Dynu may be e.g. "good 1.2.3.4" or "nochg", so we match on the first token.
_RESPONSE_OUTCOMES: dict[str, Outcome] = {
    "good": Outcome.SUCCESS,
    "nochg": Outcome.SUCCESS,
    "911": Outcome.TRANSIENT,
    "servererror": Outcome.TRANSIENT,
    "dnserr": Outcome.TRANSIENT,
    "badauth": Outcome.FATAL,
    "nohost": Outcome.FATAL,
    "notfqdn": Outcome.FATAL,
    "numhost": Outcome.FATAL,
    "abuse": Outcome.FATAL,
    "!donator": Outcome.FATAL,
    "unknown": Outcome.FATAL,
}

_HUMAN: dict[str, str] = {
    "good": "Update successful.",
    "nochg": "IP unchanged (no update needed).",
    "911": "Dynu is under maintenance; retry in ~10 minutes.",
    "servererror": "Dynu server-side error; retry later.",
    "dnserr": "Dynu DNS error; retry later.",
    "badauth": "Authentication failed — check username/password.",
    "nohost": "Hostname not found in this account.",
    "notfqdn": "Hostname is not a valid fully-qualified domain name.",
    "numhost": "Too many hostnames in one request (max 20).",
    "abuse": "Account blocked for abuse.",
    "!donator": "Requested feature is restricted to members.",
    "unknown": "Malformed request.",
}


@dataclass
class DynuResult:
    code: str  # first response token, e.g. "good"
    raw: str  # full response body
    outcome: Outcome

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.SUCCESS

    @property
    def message(self) -> str:
        return _HUMAN.get(self.code, f"Unrecognised response: {self.raw!r}")


class DynuError(Exception):
    """Raised on a network/transport failure talking to Dynu."""


def _password_param(password: str, algo: str) -> str:
    if algo == "none":
        return password
    if algo == "md5":
        return hashlib.md5(password.encode("utf-8")).hexdigest()  # noqa: S324 (protocol-defined)
    if algo == "sha256":
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
    raise ValueError(f"Unsupported password hash algorithm: {algo!r}")


def build_url(config, ipv4: str | None, ipv6: str | None, offline: bool = False) -> str:
    """Build the Dynu update URL for the given addresses.

    `config` is a gddynu.config.Config (duck-typed to avoid a circular import).
    """
    params: dict[str, str] = {}
    if config.hostname:
        params["hostname"] = config.hostname
    if config.username:
        params["username"] = config.username
    if config.group:
        params["group"] = config.group
    if offline:
        params["offline"] = "yes"
    else:
        if config.use_ipv4 and ipv4:
            params["myip"] = ipv4
        if config.use_ipv6 and ipv6:
            params["myipv6"] = ipv6
    params["password"] = _password_param(config.password, config.password_hash)

    return f"{config.endpoint}?{urllib.parse.urlencode(params)}"


def _redacted(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(k, "****" if k == "password" else v) for k, v in query]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(redacted)))


def update(config, ipv4: str | None, ipv6: str | None, offline: bool = False) -> DynuResult:
    """Send an update to Dynu and classify the response."""
    url = build_url(config, ipv4, ipv6, offline=offline)
    log.debug("Dynu request: %s", _redacted(url))

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=config.http_timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", "replace").strip()
    except (urllib.error.URLError, OSError) as exc:
        raise DynuError(f"Failed to reach Dynu: {exc}") from exc

    return parse_response(body)


def parse_response(body: str) -> DynuResult:
    code = body.split()[0].strip().lower() if body.strip() else ""
    outcome = _RESPONSE_OUTCOMES.get(code, Outcome.FATAL)
    return DynuResult(code=code, raw=body, outcome=outcome)
