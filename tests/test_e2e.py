"""端到端闭环冒烟测试。

验证「配方 → 网表 → 仿真 → 指标」整条链路对齐：
circuit_lib 生成网表 → run_sim 调 LTspice 产出 .raw → parse_raw 提取指标。
这是整个方案的核心闭环，证明 agent 自动迭代闭环技术上成立。
"""

from tools import circuit_lib, run_sim, parse_raw


def test_rc_lowpass_end_to_end(tmp_path):
    # 1. 配方生成网表
    net = circuit_lib.rc_lowpass(cutoff_hz=1000, r=1000)
    cir = tmp_path / "design.cir"
    cir.write_text(net, encoding="ascii")
    # 2. 仿真
    raw = run_sim.run(cir)
    # 3. 提取指标
    m = parse_raw.extract(raw, analysis="ac")
    # 4. 验证达标：截止频率接近设计目标 1kHz（±10%）
    assert 900 < m["cutoff_hz"] < 1100
