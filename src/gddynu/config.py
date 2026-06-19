"""Configuration loading and validation.

A TOML file provides the base configuration; environment variables prefixed
with ``GDDYNU_`` override individual fields (handy for Docker / Synology).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

DEFAULT_ENDPOINT = "https://api.dynu.com/nic/update"

# Default fallback chains for public IP detection. Each service must return the
# bare IP address as plain text (optionally with surrounding whitespace).
DEFAULT_IP_SERVICES_V4 = [
    "https://api-ipv4.dynu.com/",
    "https://api.ipify.org",
    "https://ipv4.icanhazip.com",
]
DEFAULT_IP_SERVICES_V6 = [
    "https://api64.ipify.org",
    "https://ipv6.icanhazip.com",
]

VALID_HASH_ALGOS = ("none", "md5", "sha256")


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


@dataclass
class Config:
    # --- credentials / target ---
    hostname: str = ""
    username: str | None = None
    password: str = ""
    # How `password` should be interpreted/sent: plaintext ("none") or a hash.
    password_hash: str = "none"
    group: str | None = None

    # --- behaviour ---
    interval: int = 300  # seconds, daemon mode
    use_ipv4: bool = True
    use_ipv6: bool = False
    endpoint: str = DEFAULT_ENDPOINT
    http_timeout: float = 15.0

    # --- files ---
    state_file: str = "gddynu-state.json"
    log_file: str = "gddynu.jsonl"

    # --- IP detection ---
    ip_services_v4: list[str] = field(default_factory=lambda: list(DEFAULT_IP_SERVICES_V4))
    ip_services_v6: list[str] = field(default_factory=lambda: list(DEFAULT_IP_SERVICES_V6))

    def masked_password(self) -> str:
        """A log-safe representation of the password."""
        if not self.password:
            return "<unset>"
        return f"<{self.password_hash if self.password_hash != 'none' else 'plaintext'}:****>"

    def validate(self) -> None:
        if not self.hostname and not self.username:
            raise ConfigError("Either 'hostname' or 'username' must be set.")
        if not self.password:
            raise ConfigError("'password' is required (plaintext or a hash).")
        if self.password_hash not in VALID_HASH_ALGOS:
            raise ConfigError(
                f"'password_hash' must be one of {VALID_HASH_ALGOS}, got {self.password_hash!r}."
            )
        if not self.use_ipv4 and not self.use_ipv6:
            raise ConfigError("At least one of 'use_ipv4' / 'use_ipv6' must be enabled.")
        if self.interval < 1:
            raise ConfigError("'interval' must be a positive number of seconds.")


# Env var name -> (field name, coercion function)
def _as_bool(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes", "on")


def _as_list(v: str) -> list[str]:
    return [item.strip() for item in v.split(",") if item.strip()]


_ENV_FIELDS: dict[str, tuple[str, object]] = {
    "GDDYNU_HOSTNAME": ("hostname", str),
    "GDDYNU_USERNAME": ("username", str),
    "GDDYNU_PASSWORD": ("password", str),
    "GDDYNU_PASSWORD_HASH": ("password_hash", str),
    "GDDYNU_GROUP": ("group", str),
    "GDDYNU_INTERVAL": ("interval", int),
    "GDDYNU_USE_IPV4": ("use_ipv4", _as_bool),
    "GDDYNU_USE_IPV6": ("use_ipv6", _as_bool),
    "GDDYNU_ENDPOINT": ("endpoint", str),
    "GDDYNU_HTTP_TIMEOUT": ("http_timeout", float),
    "GDDYNU_STATE_FILE": ("state_file", str),
    "GDDYNU_LOG_FILE": ("log_file", str),
    "GDDYNU_IP_SERVICES_V4": ("ip_services_v4", _as_list),
    "GDDYNU_IP_SERVICES_V6": ("ip_services_v6", _as_list),
}


def load_config(path: str | os.PathLike[str] | None, env: dict[str, str] | None = None) -> Config:
    """Load configuration from a TOML file, then apply ``GDDYNU_*`` env overrides.

    The TOML file is optional when every required field is supplied via the
    environment (the typical Docker case).
    """
    env = dict(os.environ if env is None else env)
    data: dict = {}

    if path is not None:
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"Config file not found: {p}")
        with p.open("rb") as fh:
            data = tomllib.load(fh)

    valid_names = {f.name for f in fields(Config)}
    unknown = set(data) - valid_names
    if unknown:
        raise ConfigError(f"Unknown config keys: {', '.join(sorted(unknown))}")

    cfg = Config(**{k: v for k, v in data.items() if k in valid_names})

    for env_name, (field_name, coerce) in _ENV_FIELDS.items():
        if env_name in env and env[env_name] != "":
            setattr(cfg, field_name, coerce(env[env_name]))  # type: ignore[operator]

    cfg.validate()
    return cfg
