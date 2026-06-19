from gddynu import state


def test_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    state.save_state(p, state.State(ipv4="1.2.3.4", ipv6="2001:db8::1", updated_at="t"))
    loaded = state.load_state(p)
    assert loaded.ipv4 == "1.2.3.4"
    assert loaded.ipv6 == "2001:db8::1"
    assert loaded.updated_at == "t"


def test_missing_file_returns_empty(tmp_path):
    st = state.load_state(tmp_path / "nope.json")
    assert st.ipv4 is None and st.ipv6 is None


def test_corrupt_file_returns_empty(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{ not json", encoding="utf-8")
    assert state.load_state(p).ipv4 is None


def test_has_changed_ipv4():
    st = state.State(ipv4="1.2.3.4")
    assert state.has_changed(st, "1.2.3.5", None, True, False) is True
    assert state.has_changed(st, "1.2.3.4", None, True, False) is False


def test_has_changed_ignores_disabled_family():
    st = state.State(ipv4="1.2.3.4", ipv6="2001:db8::1")
    # IPv6 differs but is disabled -> not changed
    assert state.has_changed(st, "1.2.3.4", "2001:db8::2", True, False) is False


def test_has_changed_none_detected():
    st = state.State(ipv4="1.2.3.4")
    assert state.has_changed(st, None, None, True, False) is False
