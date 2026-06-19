"""Daemon loop: run a cycle every `interval` seconds until stopped."""

from __future__ import annotations

import logging
import random
import signal
import threading

from gddynu import dynu
from gddynu.config import Config
from gddynu.runner import run_once

log = logging.getLogger("gddynu.daemon")

# Back off harder on transient errors so we don't hammer Dynu during an outage.
_TRANSIENT_BACKOFF = 60.0
_MAX_JITTER = 5.0


def run_daemon(config: Config, *, dry_run: bool = False) -> int:
    stop = threading.Event()

    def _handle(signum, _frame):
        log.info("Received signal %s; shutting down.", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    log.info("Starting daemon (interval=%ss, dry_run=%s).", config.interval, dry_run)
    while not stop.is_set():
        try:
            result = run_once(config, dry_run=dry_run)
            delay = float(config.interval)
            if result.outcome is dynu.Outcome.TRANSIENT:
                delay = max(_TRANSIENT_BACKOFF, delay)
                log.warning("Transient problem (%s); retrying in %.0fs.", result.detail, delay)
        except Exception:  # noqa: BLE001 — daemon must never die on a single cycle
            log.exception("Unexpected error during update cycle; continuing.")
            delay = max(_TRANSIENT_BACKOFF, float(config.interval))

        delay += random.uniform(0, _MAX_JITTER)
        # Interruptible sleep so SIGTERM stops us promptly.
        stop.wait(delay)

    log.info("Daemon stopped.")
    return 0
