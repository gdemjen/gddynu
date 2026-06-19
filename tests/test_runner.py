import json

from gddynu import dynu, runner, state
from gddynu.config import Config


def make_config(tmp_path, **kw):
    return Config(
        hostname="h.dynu.net",
        password="pw",
        state_file=str(tmp_path / "state.json"),
        log_file=str(tmp_path / "log.jsonl"),
        **kw,
    )


def read_log(path):
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def test_changed_ip_triggers_update(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(runner.ipdetect, "get_public_ipv4", lambda *a, **k: "203.0.113.9")
    sent = {}

    def fake_update(config, ipv4, ipv6, offline=False):
        sent["ipv4"] = ipv4
        return dynu.DynuResult("good", "good 203.0.113.9", dynu.Outcome.SUCCESS)

    monkeypatch.setattr(runner.dynu, "update", fake_update)

    result = runner.run_once(cfg)
    assert result.outcome is dynu.Outcome.SUCCESS
    assert result.changed is True
    assert sent["ipv4"] == "203.0.113.9"

    # State persisted, log has an "update" record.
    st = state.load_state(cfg.state_file)
    assert st.ipv4 == "203.0.113.9"
    records = read_log(cfg.log_file)
    assert records[-1]["action"] == "update"
    assert records[-1]["result"] == "good"


def test_unchanged_ip_skips_update(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    state.save_state(cfg.state_file, state.State(ipv4="203.0.113.9"))
    monkeypatch.setattr(runner.ipdetect, "get_public_ipv4", lambda *a, **k: "203.0.113.9")

    def boom(*a, **k):
        raise AssertionError("update should not be called when IP is unchanged")

    monkeypatch.setattr(runner.dynu, "update", boom)

    result = runner.run_once(cfg)
    assert result.changed is False
    assert result.outcome is dynu.Outcome.SUCCESS
    assert read_log(cfg.log_file)[-1]["action"] == "skip"


def test_dry_run_never_updates(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(runner.ipdetect, "get_public_ipv4", lambda *a, **k: "203.0.113.9")
    monkeypatch.setattr(runner.dynu, "update",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no update in dry-run")))

    result = runner.run_once(cfg, dry_run=True)
    assert result.changed is True
    assert read_log(cfg.log_file)[-1]["action"] == "dry-run"
    # No state written in dry-run.
    assert state.load_state(cfg.state_file).ipv4 is None


def test_no_ip_detected_is_transient(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(runner.ipdetect, "get_public_ipv4", lambda *a, **k: None)
    result = runner.run_once(cfg)
    assert result.outcome is dynu.Outcome.TRANSIENT
    assert result.exit_code == 2
    assert read_log(cfg.log_file)[-1]["result"] == "no-ip-detected"


def test_dynu_network_error_is_transient(tmp_path, monkeypatch):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(runner.ipdetect, "get_public_ipv4", lambda *a, **k: "203.0.113.9")

    def fail(*a, **k):
        raise dynu.DynuError("connection refused")

    monkeypatch.setattr(runner.dynu, "update", fail)
    result = runner.run_once(cfg)
    assert result.outcome is dynu.Outcome.TRANSIENT
    assert read_log(cfg.log_file)[-1]["action"] == "error"
