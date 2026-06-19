from gddynu import ipdetect


def test_parse_valid_ipv4():
    assert ipdetect._parse("203.0.113.7\n", 4) == "203.0.113.7"


def test_parse_rejects_wrong_version():
    assert ipdetect._parse("2001:db8::1", 4) is None
    assert ipdetect._parse("203.0.113.7", 6) is None


def test_parse_extra_text():
    assert ipdetect._parse("Your IP: 203.0.113.7 here", 4) is None  # first token not an IP
    assert ipdetect._parse("203.0.113.7 extra", 4) == "203.0.113.7"


def test_parse_garbage():
    assert ipdetect._parse("not-an-ip", 4) is None
    assert ipdetect._parse("", 4) is None
    assert ipdetect._parse(None, 4) is None


def test_detect_falls_back(monkeypatch):
    calls = []

    def fake_fetch(url, timeout):
        calls.append(url)
        return None if url == "s1" else "203.0.113.7"

    monkeypatch.setattr(ipdetect, "_fetch", fake_fetch)
    ip = ipdetect.get_public_ipv4(["s1", "s2", "s3"], timeout=1)
    assert ip == "203.0.113.7"
    assert calls == ["s1", "s2"]  # stopped after first success


def test_detect_all_fail(monkeypatch):
    monkeypatch.setattr(ipdetect, "_fetch", lambda url, timeout: None)
    assert ipdetect.get_public_ipv4(["s1", "s2"], timeout=1) is None
