"""从 .raw 波形文件解析出电路指标(JSON 格式)，供 agent 判断电路性能。

支持四类分析，用 analysis 参数分派：
- "ac"  : 交流频响 —— 通带增益、-3dB 截止频率(自动区分低通/高通)
- "op"  : 直流工作点 —— 节点电压、支路电流、功耗
- "dc"  : 直流扫描 —— 同 op(取扫描的每个点)，这里取输出节点电压序列
- "tran": 瞬态 —— 起振判断、振荡频率、峰峰值、稳定性(用于振荡器等)

关键陷阱：
- AC 分析的频率轴用 get_trace('frequency')，不能用 get_axis()。
- tran 分析的时间轴用 get_trace('time')。
"""

import json
import sys
import math
from pathlib import Path

from spicelib import RawRead


def _db(mag):
    return 20 * math.log10(mag) if mag > 0 else -999.0


def _extract_ac(raw, out_node) -> dict:
    """AC 频响：通带增益 + -3dB 截止频率(自动区分低通/高通)。"""
    freq = [abs(x) for x in raw.get_trace("frequency").get_wave()]
    vout = [abs(x) for x in raw.get_trace(out_node).get_wave()]
    gains_db = [_db(v) for v in vout]
    passband = max(gains_db)
    target = passband - 3.0
    cutoff = None

    # 低通：增益从高到低递减；高通：从低到高递增。用首尾增益判断趋势。
    is_lowpass = gains_db[0] > gains_db[-1]
    for i in range(1, len(gains_db)):
        # 低通找下穿点(前高后低)，高通找上穿点(前低后高)
        crossed = (
            gains_db[i] <= target <= gains_db[i - 1]
            if is_lowpass
            else gains_db[i - 1] <= target <= gains_db[i]
        )
        if crossed:
            f0, f1 = freq[i - 1], freq[i]
            g0, g1 = gains_db[i - 1], gains_db[i]
            cutoff = f0 + (target - g0) * (f1 - f0) / (g1 - g0)
            break

    return {
        "analysis": "ac",
        "filter_type": "lowpass" if is_lowpass else "highpass",
        "passband_gain_db": round(passband, 3),
        "cutoff_hz": round(cutoff, 2) if cutoff else None,
        "points": len(freq),
    }


def _val(x):
    """取实部标量(op/dc 的值可能是 complex 或 numpy 标量)。"""
    return float(x.real) if hasattr(x, "real") else float(x)


def _extract_op(raw, out_node) -> dict:
    """直流工作点：输出节点电压 + 所有可读到的节点电压/支路电流。"""
    names = raw.get_trace_names()
    voltages = {}
    currents = {}
    for name in names:
        low = name.lower()
        try:
            w = raw.get_trace(name).get_wave()
        except Exception:
            continue
        if not len(w):
            continue
        v = _val(w[0])
        if low.startswith("v(") or low == "v":
            voltages[name] = round(v, 6)
        elif low.startswith("i("):
            currents[name] = round(v, 9)

    vout = None
    if out_node in voltages:
        vout = voltages[out_node]
    return {
        "analysis": "op",
        "vout": vout,
        "out_node": out_node,
        "voltages": voltages,
        "currents": currents,
    }


def _extract_dc(raw, out_node) -> dict:
    """直流扫描：输出节点电压随扫描变量变化的序列。"""
    vout = [_val(x) for x in raw.get_trace(out_node).get_wave()]
    return {
        "analysis": "dc",
        "out_node": out_node,
        "vout_first": round(vout[0], 6),
        "vout_last": round(vout[-1], 6),
        "points": len(vout),
    }


def _extract_tran(raw, out_node) -> dict:
    """瞬态：起振判断、振荡频率(过零点法)、峰峰值、稳定性。"""
    time = [abs(x) for x in raw.get_trace("time").get_wave()]
    signal = [_val(x) for x in raw.get_trace(out_node).get_wave()]

    n = len(time)
    if n < 10:
        return {"analysis": "tran", "error": "数据点太少", "total_points": n}

    # 用后半段分析稳态(跳过起振暂态)
    half = n // 2
    t_steady = time[half:]
    s_steady = signal[half:]

    dc_offset = sum(s_steady) / len(s_steady)
    vpp = max(s_steady) - min(s_steady)

    # 过零点检测(相对直流偏置)求频率
    ac_signal = [v - dc_offset for v in s_steady]
    zero_crossings = []
    for i in range(1, len(ac_signal)):
        if ac_signal[i - 1] < 0 <= ac_signal[i]:  # 上升过零
            t0, t1 = t_steady[i - 1], t_steady[i]
            v0, v1 = ac_signal[i - 1], ac_signal[i]
            zero_crossings.append(t0 + (0 - v0) * (t1 - t0) / (v1 - v0))

    if len(zero_crossings) >= 2:
        periods = [zero_crossings[i] - zero_crossings[i - 1]
                   for i in range(1, len(zero_crossings))]
        avg_period = sum(periods) / len(periods)
        freq = 1.0 / avg_period if avg_period > 0 else 0
    else:
        avg_period = None
        freq = 0

    oscillating = vpp > 0.1

    # 稳定性：比较稳态段前 1/4 与后 1/4 的峰峰值
    q = len(s_steady) // 4
    early_pp = (max(s_steady[:q]) - min(s_steady[:q])) if q > 0 else vpp
    late_pp = (max(s_steady[-q:]) - min(s_steady[-q:])) if q > 0 else vpp
    drift = abs(late_pp - early_pp) / early_pp if early_pp > 0 else 0

    return {
        "analysis": "tran",
        "node": out_node,
        "oscillating": oscillating,
        "freq_hz": round(freq, 2),
        "vpp_steady": round(vpp, 4),
        "dc_offset": round(dc_offset, 4),
        "amplitude_drift": round(drift, 4),
        "stable": drift < 0.1,
        "zero_crossings": len(zero_crossings),
        "total_points": n,
    }


_DISPATCH = {
    "ac": _extract_ac,
    "op": _extract_op,
    "dc": _extract_dc,
    "tran": _extract_tran,
}


def _resolve_node(raw, out_node):
    """解析输出节点。先精确匹配，失败则智能 fallback。

    .asc 仿真产生的节点名往往是匿名 N001/N002（因无 LABEL），
    .cir 仿真则保留原始节点名（in/out/vcc 等）。
    此函数优先使用 out_node，若找不到则从所有 V(*) trace 中推断。
    """
    names = raw.get_trace_names()
    voltage_traces = [n for n in names if n.startswith("V(")]

    # 1. 精确匹配
    if out_node in names:
        return out_node

    # 2. 找不到指定节点 -> fallback 到最后一个 V(*) trace（通常是输出节点）
    #    .asc 仿真中 N002 这样的匿名节点是递增分配的，最后一个 V 是电路输出端
    if voltage_traces:
        # 排除 frequency 和 V(0)/GND
        candidates = [v for v in voltage_traces
                      if v != "V(0)" and "frequency" not in v.lower()]
        if candidates:
            fallback = candidates[-1]  # 最后一个电压 trace
            return fallback

    # 3. 绝望返回原值让外层报错
    return out_node


def extract(raw_path, analysis="ac", out_node="V(out)") -> dict:
    """从 .raw 提取指标。analysis: ac|op|dc|tran。"""
    fn = _DISPATCH.get(analysis)
    if fn is None:
        raise ValueError(
            f"未知的分析类型: {analysis}（支持 {'/'.join(_DISPATCH)}）"
        )
    raw = RawRead(str(raw_path))
    resolved = _resolve_node(raw, out_node)
    return fn(raw, resolved)


def main():
    if len(sys.argv) < 2:
        print("用法: python -m tools.parse_raw <raw文件> [ac|op|dc|tran] [节点名]")
        sys.exit(1)
    raw = sys.argv[1]
    analysis = sys.argv[2] if len(sys.argv) > 2 else "ac"
    out_node = sys.argv[3] if len(sys.argv) > 3 else "V(out)"
    m = extract(raw, analysis=analysis, out_node=out_node)
    out = Path(raw).with_name("metrics.json")
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
