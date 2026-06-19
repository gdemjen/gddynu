"""Persisted last-known IP state.

Lets us skip a Dynu request when nothing changed (the protocol asks clients not
to send redundant updates), while the IP log still records every check.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger("gddynu.state")


@dataclass
class State:
    ipv4: str | None = None
    ipv6: str | None = None
    updated_at: str | None = None  # ISO 8601 of last successful update


def load_state(path: str | os.PathLike[str]) -> State:
    p = Path(path)
    if not p.is_file():
        return State()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return State(
            ipv4=data.get("ipv4"),
            ipv6=data.get("ipv6"),
            updated_at=data.get("updated_at"),
        )
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read state file %s (%s); starting fresh.", p, exc)
        return State()


def save_state(path: str | os.PathLike[str], state: State) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write so a crash can't leave a half-written state file.
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(asdict(state), fh, indent=2)
        os.replace(tmp, p)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def has_changed(state: State, ipv4: str | None, ipv6: str | None,
                use_ipv4: bool, use_ipv6: bool) -> bool:
    """True if an enabled address differs from the persisted state."""
    if use_ipv4 and ipv4 is not None and ipv4 != state.ipv4:
        return True
    if use_ipv6 and ipv6 is not None and ipv6 != state.ipv6:
        return True
    return False
