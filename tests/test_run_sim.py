from pathlib import Path

import pytest

from tools import run_sim

RC_CIR = """* RC lowpass smoke test
V1 in 0 AC 1
R1 in out 1k
C1 out 0 159n
.ac dec 20 10 100k
.end
"""


def test_run_sim_produces_raw(tmp_path):
    cir = tmp_path / "rc.cir"
    cir.write_text(RC_CIR, encoding="ascii")
    raw = run_sim.run(cir)
    assert raw.exists()
    assert raw.suffix == ".raw"
    assert raw.stat().st_size > 0


def test_run_sim_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_sim.run(tmp_path / "nope.cir")
