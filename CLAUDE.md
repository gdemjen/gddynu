# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev dependencies
pip install -e .[dev]

# Run all tests
pytest

# Run a single test file
pytest tests/test_dynu.py

# Run the tool directly without installing
python -m gddynu --help

# Single update cycle
python -m gddynu --config gddynu.json

# Dry-run with verbose logging
python -m gddynu --config gddynu.json --dry-run -v

# Daemon mode
python -m gddynu --config gddynu.json --daemon --interval 300
```

## Architecture

The main execution flow is: `cli.py` → `runner.run_once()` → `ipdetect`, `dynu`, `state`, `iplog`.

- **cli.py** — parses args, loads config, dispatches to `run_once` or `run_daemon`
- **runner.py** — one update cycle: detect IP → compare to saved state → send Dynu update → append JSONL log entry → save new state
- **config.py** — `Config` dataclass loaded from JSON/TOML then overridden by `GDDYNU_*` env vars; `load_config()` validates before returning
- **dynu.py** — HTTP client for the Dynu IP Update Protocol; `build_url()` constructs the request, `parse_response()` maps response codes to `Outcome` enum (`SUCCESS` / `FATAL` / `TRANSIENT`)
- **ipdetect.py** — tries a fallback chain of external plain-text IP services (e.g. api.ipify.org)
- **state.py** — persists last-known IPv4/IPv6 in a JSON file; `has_changed()` drives whether an update is sent
- **iplog.py** — appends one JSONL record per cycle; also sets up stdlib logging

## Key design constraints

- **No runtime dependencies** — stdlib only (`urllib`, `logging`, `json`, `hashlib`). The only optional dep is `tomli` as a TOML backport for Python < 3.11.
- **Python 3.8 minimum** — must run on Synology DSM's bundled Python. Avoid 3.9+ syntax (e.g. `dict | dict` merge, `list[str]` subscript at runtime without `from __future__ import annotations`).
- **TOML config needs Python 3.11+ or `tomli`; JSON config works everywhere** — prefer JSON examples when targeting Synology.
- **Exit codes are meaningful**: 0 = success/no change, 1 = fatal config/auth error (don't retry), 2 = transient network error (safe to retry). The Dynu protocol expects clients to respect these.
- Passwords are always redacted before logging; `build_url()` embeds the password in the query string (protocol-defined), so `_redacted()` must be used for any log output of URLs.
