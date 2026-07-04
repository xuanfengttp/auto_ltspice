from tools import circuit_lib


def test_rc_lowpass_netlist_contains_parts():
    net = circuit_lib.rc_lowpass(cutoff_hz=1000, r=1000)
    assert "V1 in 0 AC 1" in net
    assert "R1 in out 1000" in net
    assert ".ac" in net
    assert ".end" in net


def test_rc_lowpass_cap_value_correct():
    # C = 1/(2*pi*R*fc)，R=1k, fc=1k → ≈159nF
    net = circuit_lib.rc_lowpass(cutoff_hz=1000, r=1000)
    import re
    m = re.search(r"C1 out 0 ([0-9.eE+-]+)", net)
    assert m
    c = float(m.group(1))
    assert 1.5e-7 < c < 1.7e-7


def test_rc_highpass_topology_and_cap():
    # 高通：电容串在信号路径(C1 in out)，电阻接地(R1 out 0)
    net = circuit_lib.rc_highpass(cutoff_hz=1000, r=10000)
    assert "C1 in out" in net
    assert "R1 out 0 10000" in net
    assert ".ac" in net
    import re
    c = float(re.search(r"C1 in out ([0-9.eE+-]+)", net).group(1))
    # C = 1/(2*pi*10k*1k) ≈ 15.9nF
    assert 1.5e-8 < c < 1.7e-8


def test_voltage_divider_resistor_reverse_calc():
    # R2 = vout/I, R1 = (vin-vout)/I；12V→5V @20mA → R1=350, R2=250
    net = circuit_lib.voltage_divider(vin=12, vout=5, load_current=0.02)
    assert "V1 in 0 DC 12" in net
    assert "R1 in out 350" in net
    assert "R2 out 0 250" in net
    assert ".op" in net


def test_voltage_divider_rejects_invalid_vout():
    # vout 必须严格小于 vin
    import pytest
    with pytest.raises(ValueError):
        circuit_lib.voltage_divider(vin=5, vout=5, load_current=0.01)


def test_colpitts_uses_tran_and_has_transistor():
    net = circuit_lib.colpitts_oscillator(freq_hz=500e3)
    assert "Q1 coll base emit QNPN" in net
    assert ".model QNPN NPN" in net
    assert ".tran" in net
    assert ".ic V(coll)=0.1" in net


def test_analysis_map_registered():
    # 每个配方都在 ANALYSIS 字典登记了分析类型
    assert circuit_lib.ANALYSIS["rc_lowpass"] == "ac"
    assert circuit_lib.ANALYSIS["rc_highpass"] == "ac"
    assert circuit_lib.ANALYSIS["voltage_divider"] == "op"
    assert circuit_lib.ANALYSIS["colpitts_oscillator"] == "tran"

