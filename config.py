import re
from pathlib import Path

import yaml  # type: ignore

DEFAULT_CONFIG = {
    "server": None,
    "user": None,
    "token": None,
}


def is_valid_url(url: str) -> bool:
    """
    Check if the URL starts with http:// or https:// and is followed
    by a valid domain or IPv4 address.
    """
    pattern = re.compile(
        r"^(https?://)"
        r"(([a-zA-Z0-9.-]+)|"
        r"(\d{1,3}(\.\d{1,3}){3}))"
        r"(:\d+)?"
        r"(/.*)?$"
    )
    return bool(pattern.match(url))


def load_config():
    path = Path.home() / ".arty-mc.yml"

    if not path.exists():
        raise RuntimeError("Config file missing: ~/.arty-mc.yml")

    with open(path) as f:
        data = yaml.safe_load(f)

    cfg = {**DEFAULT_CONFIG, **data}

    server = cfg.get("server")
    if not server:
        raise RuntimeError("Config error: 'server' not defined")

    if not is_valid_url(server):
        raise RuntimeError(f"Config error: server '{server}' is not a valid URL.")

    return cfg
