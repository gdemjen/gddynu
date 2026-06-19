import pytest

from gddynu.config import Config, ConfigError, load_config


def write_toml(tmp_path, body):
    p = tmp_path / "gddynu.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_load_from_toml(tmp_path):
    p = write_toml(tmp_path, 'hostname = "h.dynu.net"\npassword = "secret"\n')
    cfg = load_config(p, env={})
    assert cfg.hostname == "h.dynu.net"
    assert cfg.password == "secret"
    assert cfg.use_ipv4 is True


def test_env_overrides_file(tmp_path):
    p = write_toml(tmp_path, 'hostname = "h.dynu.net"\npassword = "secret"\ninterval = 300\n')
    env = {"GDDYNU_PASSWORD": "fromenv", "GDDYNU_INTERVAL": "60", "GDDYNU_USE_IPV6": "true"}
    cfg = load_config(p, env=env)
    assert cfg.password == "fromenv"
    assert cfg.interval == 60
    assert cfg.use_ipv6 is True


def test_load_from_json(tmp_path):
    p = tmp_path / "gddynu.json"
    p.write_text('{"hostname": "h.dynu.net", "password": "secret", "interval": 120}',
                 encoding="utf-8")
    cfg = load_config(p, env={})
    assert cfg.hostname == "h.dynu.net"
    assert cfg.interval == 120


def test_invalid_json_raises(tmp_path):
    p = tmp_path / "gddynu.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p, env={})


def test_env_only_no_file():
    env = {"GDDYNU_HOSTNAME": "h.dynu.net", "GDDYNU_PASSWORD": "x"}
    cfg = load_config(None, env=env)
    assert cfg.hostname == "h.dynu.net"


def test_list_override():
    env = {
        "GDDYNU_HOSTNAME": "h",
        "GDDYNU_PASSWORD": "x",
        "GDDYNU_IP_SERVICES_V4": "https://a.example, https://b.example",
    }
    cfg = load_config(None, env=env)
    assert cfg.ip_services_v4 == ["https://a.example", "https://b.example"]


def test_missing_password_raises():
    with pytest.raises(ConfigError):
        load_config(None, env={"GDDYNU_HOSTNAME": "h"})


def test_unknown_key_raises(tmp_path):
    p = write_toml(tmp_path, 'hostname = "h"\npassword = "x"\nbogus = 1\n')
    with pytest.raises(ConfigError):
        load_config(p, env={})


def test_bad_hash_algo_raises():
    with pytest.raises(ConfigError):
        load_config(None, env={"GDDYNU_HOSTNAME": "h", "GDDYNU_PASSWORD": "x",
                               "GDDYNU_PASSWORD_HASH": "sha1"})


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml", env={})


def test_masked_password():
    cfg = Config(hostname="h", password="secret", password_hash="sha256")
    assert "secret" not in cfg.masked_password()
