"""Command-line interface for gddynu."""

from __future__ import annotations

import argparse
import logging
import sys

from gddynu import __version__
from gddynu.config import ConfigError, load_config
from gddynu.daemon import run_daemon
from gddynu.iplog import setup_logging
from gddynu.runner import run_once

log = logging.getLogger("gddynu.cli")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gddynu",
        description="Dynamic DNS updater for Dynu.com with IP change logging.",
    )
    p.add_argument("-c", "--config", help="Path to a TOML config file.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true",
                      help="Run a single update and exit (default).")
    mode.add_argument("--daemon", action="store_true",
                      help="Run continuously, updating every --interval seconds.")
    mode.add_argument("--web", action="store_true",
                      help="Start the IP history web UI server.")
    p.add_argument("--interval", type=int,
                   help="Daemon poll interval in seconds (overrides config).")
    p.add_argument("--dry-run", action="store_true",
                   help="Detect and log the IP but do not send any update.")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 1

    if args.web:
        from gddynu.webserver import run_web
        try:
            run_web(config)
        except ValueError as exc:
            log.error("%s", exc)
            return 1
        return 0

    if args.interval is not None:
        config.interval = args.interval

    if args.daemon:
        return run_daemon(config, dry_run=args.dry_run)

    result = run_once(config, dry_run=args.dry_run)
    return result.exit_code


def web_main(argv: list[str] | None = None) -> None:
    """Entry point for the ``gddynu-web`` command."""
    p = argparse.ArgumentParser(
        prog="gddynu-web",
        description="IP history web UI for gddynu.",
    )
    p.add_argument("-c", "--config", help="Path to config file (TOML or JSON).")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)
    setup_logging(args.verbose)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    from gddynu.webserver import run_web
    try:
        run_web(config)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
