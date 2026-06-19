"""One update cycle: detect -> compare with state -> update -> log."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from gddynu import dynu, ipdetect, iplog, state
from gddynu.config import Config

log = logging.getLogger("gddynu.runner")


@dataclass
class CycleResult:
    outcome: dynu.Outcome
    changed: bool
    ipv4: str | None
    ipv6: str | None
    detail: str

    @property
    def exit_code(self) -> int:
        # 0 success/nochg, 1 fatal, 2 transient (retryable).
        return {
            dynu.Outcome.SUCCESS: 0,
            dynu.Outcome.FATAL: 1,
            dynu.Outcome.TRANSIENT: 2,
        }[self.outcome]


def run_once(config: Config, *, dry_run: bool = False) -> CycleResult:
    """Detect the current public IP, update Dynu if it changed, log everything."""
    ipv4 = ipdetect.get_public_ipv4(config.ip_services_v4, config.http_timeout) if config.use_ipv4 else None
    ipv6 = ipdetect.get_public_ipv6(config.ip_services_v6, config.http_timeout) if config.use_ipv6 else None

    if config.use_ipv4 and ipv4 is None:
        log.warning("Could not detect a public IPv4 address.")
    if config.use_ipv6 and ipv6 is None:
        log.warning("Could not detect a public IPv6 address.")

    if ipv4 is None and ipv6 is None:
        iplog.append_record(config.log_file, ipv4=None, ipv6=None,
                            changed=False, action="error", result="no-ip-detected")
        return CycleResult(dynu.Outcome.TRANSIENT, False, None, None, "No public IP detected.")

    st = state.load_state(config.state_file)
    changed = state.has_changed(st, ipv4, ipv6, config.use_ipv4, config.use_ipv6)
    log.info("Detected IPv4=%s IPv6=%s (changed=%s)", ipv4, ipv6, changed)

    if dry_run:
        iplog.append_record(config.log_file, ipv4=ipv4, ipv6=ipv6,
                            changed=changed, action="dry-run", result=None)
        return CycleResult(dynu.Outcome.SUCCESS, changed, ipv4, ipv6, "Dry run; no update sent.")

    if not changed:
        iplog.append_record(config.log_file, ipv4=ipv4, ipv6=ipv6,
                            changed=False, action="skip", result="nochg")
        log.info("IP unchanged; skipping Dynu update.")
        return CycleResult(dynu.Outcome.SUCCESS, False, ipv4, ipv6, "IP unchanged.")

    try:
        result = dynu.update(config, ipv4, ipv6)
    except dynu.DynuError as exc:
        iplog.append_record(config.log_file, ipv4=ipv4, ipv6=ipv6,
                            changed=changed, action="error", result=str(exc))
        log.error("%s", exc)
        return CycleResult(dynu.Outcome.TRANSIENT, changed, ipv4, ipv6, str(exc))

    iplog.append_record(config.log_file, ipv4=ipv4, ipv6=ipv6,
                        changed=changed, action="update", result=result.code)

    if result.ok:
        st.ipv4 = ipv4 if config.use_ipv4 else st.ipv4
        st.ipv6 = ipv6 if config.use_ipv6 else st.ipv6
        st.updated_at = datetime.now(timezone.utc).isoformat()
        state.save_state(config.state_file, st)
        log.info("Dynu: %s (%s)", result.code, result.message)
    else:
        log.error("Dynu: %s (%s)", result.code, result.message)

    return CycleResult(result.outcome, changed, ipv4, ipv6, result.message)
