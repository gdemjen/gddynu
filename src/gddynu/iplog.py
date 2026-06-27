"""IP change log and human-readable logging setup.

The IP log is append-only JSONL — one record per check — so changes over time
can be tracked and analysed later. Separately, stdlib logging writes
human-readable output to stdout (Docker-friendly).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_record(
    path: str | os.PathLike[str],
    *,
    ipv4: str | None,
    ipv6: str | None,
    changed: bool,
    action: str,
    result: str | None,
) -> dict:
    """Append one JSONL record describing a check and its outcome.

    action: "detect" | "update" | "skip" | "dry-run" | "error"
    result: the Dynu response code, or an error string, or None.
    """
    record = {
        "ts": _now_iso(),
        "ipv4": ipv4,
        "ipv6": ipv6,
        "changed": changed,
        "action": action,
        "result": result,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def append_history(
    path: str | os.PathLike[str],
    *,
    ipv4: str | None,
    ipv6: str | None,
) -> None:
    """Append one record to the IP history file when an address change is confirmed."""
    record = {"ts": _now_iso(), "ipv4": ipv4, "ipv6": ipv6}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
