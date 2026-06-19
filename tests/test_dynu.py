import hashlib
import urllib.parse

import pytest

from gddynu import dynu
from gddynu.config import Config


@pytest.mark.parametrize(
    "body,code,outcome",
    [
        ("good 1.2.3.4", "good", dynu.Outcome.SUCCESS),
        ("nochg", "nochg", dynu.Outcome.SUCCESS),
        ("911", "911", dynu.Outcome.TRANSIENT),
        ("servererror", "servererror", dynu.Outcome.TRANSIENT),
        ("dnserr", "dnserr", dynu.Outcome.TRANSIENT),
        ("badauth", "badauth", dynu.Outcome.FATAL),
        ("nohost", "nohost", dynu.Outcome.FATAL),
        ("notfqdn", "notfqdn", dynu.Outcome.FATAL),
        ("numhost", "numhost", dynu.Outcome.FATAL),
        ("abuse", "abuse", dynu.Outcome.FATAL),
        ("!donator", "!donator", dynu.Outcome.FATAL),
        ("unknown", "unknown", dynu.Outcome.FATAL),
        ("totally-bogus", "totally-bogus", dynu.Outcome.FATAL),
        ("", "", dynu.Outcome.FATAL),
    ],
)
def test_parse_response(body, code, outcome):
    result = dynu.parse_response(body)
    assert result.code == code
    assert result.outcome is outcome
    assert result.ok is (outcome is dynu.Outcome.SUCCESS)


def _params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


def test_build_url_plaintext():
    cfg = Config(hostname="h.dynu.net", password="pw")
    url = dynu.build_url(cfg, "1.2.3.4", None)
    p = _params(url)
    assert p["hostname"] == "h.dynu.net"
    assert p["myip"] == "1.2.3.4"
    assert p["password"] == "pw"
    assert "myipv6" not in p


def test_build_url_sha256_hash():
    cfg = Config(hostname="h", password="pw", password_hash="sha256")
    p = _params(dynu.build_url(cfg, "1.2.3.4", None))
    assert p["password"] == hashlib.sha256(b"pw").hexdigest()


def test_build_url_ipv6_included_when_enabled():
    cfg = Config(hostname="h", password="pw", use_ipv6=True)
    p = _params(dynu.build_url(cfg, "1.2.3.4", "2001:db8::1"))
    assert p["myipv6"] == "2001:db8::1"


def test_build_url_offline():
    cfg = Config(hostname="h", password="pw")
    p = _params(dynu.build_url(cfg, "1.2.3.4", None, offline=True))
    assert p["offline"] == "yes"
    assert "myip" not in p


def test_redacted_hides_password():
    cfg = Config(hostname="h", password="supersecret")
    url = dynu.build_url(cfg, "1.2.3.4", None)
    assert "supersecret" not in dynu._redacted(url)
