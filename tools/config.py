from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"


def load() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ltspice_exe() -> Path:
    return Path(load()["ltspice_exe"])


def projects_dir() -> Path:
    return _ROOT / load()["projects_dir"]
