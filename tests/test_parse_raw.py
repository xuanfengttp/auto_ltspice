from pathlib import Path

from tools import run_sim, parse_raw, circuit_lib

RC_CIR = """* RC lowpass
V1 in 0 AC 1
R1 in out 1k
C1 out 0 159n
.ac dec 20 10 100k
.end
"""


def test_ac_metrics_cutoff_near_1khz(tmp_path):
    cir = tmp_path / "rc.cir"
    cir.write_text(RC_CIR, encoding="ascii")
    raw = run_sim.run(cir)
    m = parse_raw.extract(raw, analysis="ac", out_node="V(out)")
    # RC: fc = 1/(2*pi*1k*159n) ≈ 1000 Hz，容差 ±10%
    assert 900 < m["cutoff_hz"] < 1100
    # 通带增益接近 0 dB
    assert -1.0 < m["passband_gain_db"] < 0.5


def test_ac_highpass_detected_and_cutoff(tmp_path):
    cir = tmp_path / "hp.cir"
    cir.write_text(circuit_lib.rc_highpass(cutoff_hz=1000, r=10000), encoding="ascii")
    raw = run_sim.run(cir)
    m = parse_raw.extract(raw, analysis="ac", out_node="V(out)")
    # 自动识别为高通，且截止频率接近 1kHz（曾经的 bug：返回 null）
    assert m["filter_type"] == "highpass"
    assert m["cutoff_hz"] is not None
    assert 900 < m["cutoff_hz"] < 1100


def test_op_voltage_divider(tmp_path):
    cir = tmp_path / "div.cir"
    cir.write_text(circuit_lib.voltage_divider(vin=12, vout=5, load_current=0.02), encoding="ascii")
    raw = run_sim.run(cir)
    m = parse_raw.extract(raw, analysis="op", out_node="V(out)")
    # 输出电压精确 5V（容差 ±0.1V）
    assert m["vout"] is not None
    assert 4.9 < m["vout"] < 5.1


def test_tran_oscillator_starts_up(tmp_path):
    cir = tmp_path / "osc.cir"
    cir.write_text(circuit_lib.colpitts_oscillator(freq_hz=500e3), encoding="ascii")
    raw = run_sim.run(cir)
    m = parse_raw.extract(raw, analysis="tran", out_node="V(coll)")
    # 起振且频率接近 500kHz（±5%）
    assert m["oscillating"] is True
    assert 475e3 < m["freq_hz"] < 525e3

