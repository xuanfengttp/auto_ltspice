from pathlib import Path
from tools import config


def test_load_returns_ltspice_path():
    cfg = config.load()
    assert "LTspice.exe" in cfg["ltspice_exe"]


def test_ltspice_exe_path_helper():
    p = config.ltspice_exe()
    assert isinstance(p, Path)
    assert p.name == "LTspice.exe"


def test_sim_timeout_default():
    assert config.load()["sim_timeout"] == 60
