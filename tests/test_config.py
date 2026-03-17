from pathlib import Path

import pytest  # type: ignore
import yaml  # type: ignore

from arty_mc.config import is_valid_url, load_config  # type: ignore


def test_is_valid_url_valid():
    assert is_valid_url("http://example.com")
    assert is_valid_url("https://example.com")
    assert is_valid_url("https://example.com:8080")
    assert is_valid_url("https://example.com/path")


def test_is_valid_url_invalid():
    assert not is_valid_url("ftp://example.com")
    assert not is_valid_url("example.com")
    assert not is_valid_url("not-a-url")


def test_load_config_success(tmp_path, monkeypatch):
    config_file = tmp_path / ".arty-mc.yml"

    config_file.write_text(
        yaml.safe_dump(
            {
                "server": "https://example.com",
                "user": "test",
                "token": "abc",
            }
        )
    )

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config()
    assert cfg["server"] == "https://example.com"
    assert cfg["user"] == "test"
    assert cfg["token"] == "abc"


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="Config file missing"):
        load_config()


def test_load_config_missing_server(tmp_path, monkeypatch):
    config_file = tmp_path / ".arty-mc.yml"

    config_file.write_text(
        yaml.safe_dump(
            {
                "user": "test",
                "token": "abc",
            }
        )
    )

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="server"):
        load_config()


def test_load_config_invalid_url(tmp_path, monkeypatch):
    config_file = tmp_path / ".arty-mc.yml"

    config_file.write_text(
        yaml.safe_dump(
            {
                "server": "not-a-url",
            }
        )
    )

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="not a valid URL"):
        load_config()
