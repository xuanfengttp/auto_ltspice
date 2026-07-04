"""电路配方库。

每个配方函数返回一个完整的 .cir 网表字符串(含元件、激励、分析指令)。
Agent 调用配方 → run_sim 仿真 → parse_raw 提取指标 → 判断是否满足需求。

约定：每个配方的 docstring 首行标注它使用的【分析类型】(ac/op/tran)，
这样 agent 知道 parse_raw 该用哪个 analysis 参数。
"""

import math

# 每个配方对应的 parse_raw analysis 参数，供 agent 自动匹配。
ANALYSIS = {
    "rc_lowpass": "ac",
    "rc_highpass": "ac",
    "voltage_divider": "op",
    "colpitts_oscillator": "tran",
}


def rc_lowpass(cutoff_hz: float, r: float = 1000.0) -> str:
    """【ac】一阶 RC 低通滤波器。给定截止频率和电阻，算出电容并生成网表。

    参数:
        cutoff_hz: 目标 -3dB 截止频率(Hz)
        r: 电阻值(Ω)，默认 1kΩ
    拓扑: V1 → R1 → out → C1 → GND
    """
    c = 1.0 / (2 * math.pi * r * cutoff_hz)
    dec_lo = cutoff_hz / 100
    dec_hi = cutoff_hz * 100
    return (
        f"* RC lowpass fc={cutoff_hz}Hz R={r}ohm\n"
        f"V1 in 0 AC 1\n"
        f"R1 in out {r:g}\n"
        f"C1 out 0 {c:.4g}\n"
        f".ac dec 20 {dec_lo:g} {dec_hi:g}\n"
        f".end\n"
    )


def rc_highpass(cutoff_hz: float, r: float = 10000.0) -> str:
    """【ac】一阶 RC 高通滤波器。给定截止频率和电阻，算出电容并生成网表。

    参数:
        cutoff_hz: 目标 -3dB 截止频率(Hz)
        r: 电阻值(Ω)，默认 10kΩ(高通常用较大电阻避免负载效应)
    拓扑: V1 → C1 → out → R1 → GND(电容串在信号路径，电阻接地)
    """
    c = 1.0 / (2 * math.pi * r * cutoff_hz)
    dec_lo = cutoff_hz / 100
    dec_hi = cutoff_hz * 100
    return (
        f"* RC highpass fc={cutoff_hz}Hz R={r}ohm\n"
        f"V1 in 0 AC 1\n"
        f"C1 in out {c:.4g}\n"
        f"R1 out 0 {r:g}\n"
        f".ac dec 20 {dec_lo:g} {dec_hi:g}\n"
        f".end\n"
    )


def voltage_divider(vin: float, vout: float, load_current: float) -> str:
    """【op】电阻分压器。给定输入电压、目标输出电压、负载电流，反算 R1/R2。

    参数:
        vin: 输入直流电压(V)
        vout: 目标输出电压(V)，需 0 < vout < vin
        load_current: 流过分压器的电流(A)，决定功耗与精度
    拓扑: V1 → R1 → out → R2(=Rload) → GND
    说明: R2 = vout/load_current，R1 = (vin-vout)/load_current。
          load_current 越大越"硬"(抗负载扰动)，但功耗越高。
    """
    if not (0 < vout < vin):
        raise ValueError(f"要求 0 < vout({vout}) < vin({vin})")
    if load_current <= 0:
        raise ValueError(f"load_current 必须 > 0，得到 {load_current}")
    r2 = vout / load_current
    r1 = (vin - vout) / load_current
    return (
        f"* Voltage divider {vin}V -> {vout}V @ {load_current*1000:g}mA\n"
        f"V1 in 0 DC {vin:g}\n"
        f"R1 in out {r1:.4g}\n"
        f"R2 out 0 {r2:.4g}\n"
        f".op\n"
        f".end\n"
    )


def colpitts_oscillator(freq_hz: float, l: float = 10e-6) -> str:
    """【tran】Colpitts(考毕兹)三极管 LC 振荡器。给定谐振频率和电感，算电容。

    参数:
        freq_hz: 目标谐振频率(Hz)
        l: 电感值(H)，默认 10µH
    说明: f = 1/(2π√(L·Cs))，Cs = C1·C2/(C1+C2)。取 C1=C2=2·Cs。
          含 NPN 三极管 + 基极偏置网络，用 .tran 观察起振。
          用 parse_raw(analysis="tran", out_node="V(coll)") 读频率/起振。
    """
    # Cs = 1/((2πf)^2 · L)，C1=C2=2Cs
    cs = 1.0 / ((2 * math.pi * freq_hz) ** 2 * l)
    c12 = 2 * cs
    # 跑约 100 个周期，输出步长为周期的 ~1/40
    period = 1.0 / freq_hz
    tstop = 100 * period
    tstep = period / 40
    return (
        f"* Colpitts LC oscillator f={freq_hz:g}Hz L={l:g}H\n"
        f"* f = 1/(2*pi*sqrt(L*Cs)), Cs = C1*C2/(C1+C2)\n"
        f"VCC vcc 0 DC 12\n"
        f"R1 vcc base 10k\n"
        f"R2 base 0 2.7k\n"
        f"RC vcc coll 220\n"
        f"RE emit 0 470\n"
        f"Q1 coll base emit QNPN\n"
        f"L1 vcc coll {l:g}\n"
        f"C1 coll emit {c12:.4g}\n"
        f"C2 emit 0 {c12:.4g}\n"
        f".ic V(coll)=0.1\n"
        f".model QNPN NPN(BF=150 IS=1e-15 VAF=100)\n"
        f".tran 0 {tstop:.4g} 0 {tstep:.4g}\n"
        f".end\n"
    )
