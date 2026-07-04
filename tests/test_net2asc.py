from pathlib import Path
from tools import net2asc

RC_CIR = """* RC lowpass
V1 in 0 AC 1
R1 in out 1000
C1 out 0 159n
.ac dec 20 10 100k
.end
"""


def test_net2asc_produces_asc(tmp_path):
    cir = tmp_path / "design.cir"
    cir.write_text(RC_CIR, encoding="ascii")
    asc = net2asc.convert(cir)
    assert asc.exists()
    text = asc.read_text()
    assert text.startswith("Version 4")
    assert "SYMBOL" in text
    assert text.count("SYMBOL") >= 3


def test_net2asc_has_ground(tmp_path):
    cir = tmp_path / "design.cir"
    cir.write_text(RC_CIR, encoding="ascii")
    asc = net2asc.convert(cir)
    assert "FLAG" in asc.read_text()
