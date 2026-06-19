# gddynu

A dynamic DNS updater for [Dynu.com](https://www.dynu.com), implementing the
[Dynu IP Update Protocol](https://www.dynu.com/en-US/DynamicDNS/IP-Update-Protocol).

It does what the stock Dynu client does, plus two extras:

1. **IP change log** — every detected public IP and every update is appended to a
   machine-readable JSONL file, so you can track when and how your address changed.
2. **Runs on Synology NAS** — a single zero-dependency Python package and a Docker
   image; run it in Container Manager (Docker) or from the DSM Task Scheduler.

## How it works

Each cycle gddynu:

1. detects your public IPv4/IPv6 from a fallback chain of external services,
2. records it in the JSONL log,
3. compares it to the last known state, and
4. sends a Dynu update **only when the address changed** (the protocol asks
   clients not to send redundant updates).

## Requirements

- Python **3.11+** (uses the stdlib `tomllib`). No third-party runtime dependencies.

## Install

```bash
pip install .
# or, from a checkout, run without installing:
python -m gddynu --help
```

## Configure

Copy [`config.example.toml`](config.example.toml) to `gddynu.toml` and edit it.
Any field can be overridden by a `GDDYNU_<UPPERCASE>` environment variable — handy
for containers and for keeping secrets out of files:

| Setting | Env var | Default |
|---|---|---|
| `hostname` | `GDDYNU_HOSTNAME` | — (required unless `username` set) |
| `username` | `GDDYNU_USERNAME` | — |
| `password` | `GDDYNU_PASSWORD` | — (required) |
| `password_hash` | `GDDYNU_PASSWORD_HASH` | `none` (`md5` / `sha256`) |
| `interval` | `GDDYNU_INTERVAL` | `300` |
| `use_ipv4` / `use_ipv6` | `GDDYNU_USE_IPV4` / `GDDYNU_USE_IPV6` | `true` / `false` |
| `state_file` | `GDDYNU_STATE_FILE` | `gddynu-state.json` |
| `log_file` | `GDDYNU_LOG_FILE` | `gddynu.jsonl` |

The `password` may be plaintext or a hash; set `password_hash` to `md5`/`sha256`
to send it hashed. Secrets are masked in logs and never written to the IP log.

## Usage

```bash
# Single run (default) — ideal for cron / Task Scheduler:
gddynu --config gddynu.toml

# Detect + log but send no update:
gddynu --config gddynu.toml --dry-run -v

# Run continuously, polling every 300s:
gddynu --config gddynu.toml --daemon --interval 300
```

Exit codes: `0` success / no change, `1` configuration or fatal account error,
`2` transient error (safe to retry).

### The IP log

`log_file` is JSONL — one record per check:

```json
{"ts": "2026-06-19T10:00:00+00:00", "ipv4": "203.0.113.7", "ipv6": null, "changed": true, "action": "update", "result": "good"}
```

`action` is one of `detect` / `update` / `skip` / `dry-run` / `error`; `result`
is the Dynu response code (e.g. `good`, `nochg`) or an error string.

## Synology NAS

### Option A — Docker (recommended, daemon mode)

1. Copy the project to your NAS (or build the image elsewhere and push it).
2. Edit [`docker-compose.yml`](docker-compose.yml) with your hostname; set
   `GDDYNU_PASSWORD` via the Container Manager environment or a `.env` file.
3. In **Container Manager → Project**, create a project from the compose file, or:

   ```bash
   GDDYNU_PASSWORD='...' docker compose up -d
   ```

State and the IP log persist in the mounted `./data` volume.

### Option B — DSM Task Scheduler (one-shot)

1. Put the package and a `gddynu.toml` in a shared folder, e.g. `/volume1/gddynu`.
2. **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**,
   run e.g. every 5 minutes:

   ```bash
   cd /volume1/gddynu && /usr/bin/python3 -m gddynu --config gddynu.toml
   ```

   (Ensure the NAS Python is 3.11+; otherwise prefer the Docker option.)

## Development

```bash
pip install -e .[dev]
pytest
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
