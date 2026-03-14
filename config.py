from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "server": None,
    "user": None,
    "token": None,
}


def load_config():
    path = Path.home() / ".arty-mc.yml"

    if not path.exists():
        raise RuntimeError("Config file missing: ~/.arty-mc.yml")

    with open(path) as f:
        data = yaml.safe_load(f)

    cfg = {**DEFAULT_CONFIG, **data}

    if not cfg["server"]:
        raise RuntimeError("Config error: 'server' not defined")

    return cfg
