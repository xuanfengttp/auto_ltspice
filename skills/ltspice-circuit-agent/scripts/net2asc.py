"""完全重写 net2asc.py —— 正确版本。

核心改进：
1. 按节点拓扑生成 WIRE 连接，不产生短路
2. 垂直 WIRE 只从引脚到节点轨
3. 水平 WIRE 严格在同一节点轨上连接所有触及该轨的引脚柱点
4. 不生成任何使不同节点轨短路的 WIRE
5. TEXT 用 `!` 前缀（LTspice SPICE 指令）而非 `;`（注释）

元件引脚坐标来自 LTspice lib/sym/*.asy 精确提取。
"""

import sys
from pathlib import Path


# (符号名, [(引脚dx, dy), ...])
_SYMBOLS = {
    "R": ("res",     [(16, 16), (16, 96)]),
    "C": ("cap",     [(16, 0),  (16, 64)]),
    "L": ("ind",     [(16, 16), (16, 96)]),
    "V": ("voltage", [(0, 16),  (0, 96)]),
    "Q": ("npn",     [(64, 0),  (0, 48), (64, 96)]),
}


def _parse_netlist(text):
    """解析 .cir -> (components, directives)。"""
    components, directives = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("."):
            directives.append(line)
            continue
        toks = line.split()
        refdes, prefix = toks[0], toks[0][0].upper()
        if prefix not in _SYMBOLS:
            continue
        if prefix == "Q":
            nodes, val, extra = toks[1:4], (toks[4] if len(toks) > 4 else ""), toks[5:]
        else:
            nodes, val, extra = toks[1:3], (toks[3] if len(toks) > 3 else ""), toks[4:]
        components.append((refdes, nodes, val, extra))
    return components, directives


def convert(cir_path) -> Path:
    cir = Path(cir_path)
    components, directives = _parse_netlist(cir.read_text())
    if not components:
        asc = cir.with_suffix(".asc")
        asc.write_text("Version 4\nSHEET 1 880 680\n", encoding="utf-8")
        return asc

    # 收集所有信号节点(非 GND)，每个分配 Y 坐标轨
    all_nodes = set()
    for _, nodes, _, _ in components:
        all_nodes.update(nodes)
    signal_nodes = sorted(n for n in all_nodes if n != "0")

    SPACING = 96
    gnd_y = (len(signal_nodes) + 1) * SPACING
    node_y = {"0": gnd_y}
    for i, n in enumerate(signal_nodes):
        node_y[n] = (i + 1) * SPACING

    # 排序: 电压源在前
    voltage_comps = [c for c in components if c[0][0].upper() == "V"]
    other_comps = [c for c in components if c[0][0].upper() != "V"]
    ordered = voltage_comps + other_comps

    LEFT_X = 128
    COMP_SPACING = 160

    wires = set()
    flags = set()
    node_xpoints = {n: set() for n in all_nodes}

    # ── 第一遍：放元件符号，画垂直 WIRE ──
    lines = ["Version 4", "SHEET 1 1760 880"]
    for idx, (refdes, nodes, val, extra) in enumerate(ordered):
        prefix = refdes[0].upper()
        sym_name, pins = _SYMBOLS[prefix]
        sx = LEFT_X + idx * COMP_SPACING

        # 确定元件上下端 Y
        if prefix == "Q":
            y_hi, y_lo = node_y[nodes[0]], node_y[nodes[2]]
        else:
            y_hi, y_lo = node_y[nodes[0]], node_y[nodes[1]]
            if y_hi > y_lo:
                y_hi, y_lo = y_lo, y_hi
        center_y = (y_hi + y_lo) // 2
        pin0_dy = pins[0][1]
        pin_last_dy = pins[-1][1]
        sy = center_y - (pin0_dy + pin_last_dy) // 2

        lines.append(f"SYMBOL {sym_name} {sx} {sy} R0")
        lines.append(f"SYMATTR InstName {refdes}")
        if prefix == "V":
            if val.upper() == "DC" and extra:
                lines.append(f"SYMATTR Value DC {extra[0]}")
            elif val.upper() == "AC" and extra:
                lines.append(f"SYMATTR Value AC {extra[0]}")
            else:
                lines.append(f"SYMATTR Value {val}")
        else:
            lines.append(f"SYMATTR Value {val}")

        # 每个引脚 → 垂直 WIRE 到节点轨 + 收集柱点
        for pi, (pdx, pdy) in enumerate(pins):
            if pi >= len(nodes):
                continue
            node = nodes[pi]
            px, py = sx + pdx, sy + pdy
            n_y = node_y[node]
            node_xpoints[node].add(px)

            if node == "0":
                # GND: 垂直 WIRE 从引脚到 GND 轨，再往下到 FLAG
                fy = n_y + 32
                flags.add((px, fy))
                wires.add((px, py, px, fy))
            else:
                # 信号节点: 垂直 WIRE 从引脚到节点轨
                wires.add((px, py, px, n_y))

    # ── 第二遍：画水平 WIRE 在每个节点轨上 ──
    for node, xs in node_xpoints.items():
        if node == "0" or len(xs) < 2:
            continue
        x_min, x_max = min(xs), max(xs)
        n_y = node_y[node]
        # 水平 WIRE 从最左到最右
        wires.add((x_min, n_y, x_max, n_y))

    # ── 输出 WIRE ──
    for (x1, y1, x2, y2) in sorted(wires):
        lines.append(f"WIRE {x1} {y1} {x2} {y2}")

    # ── 输出 FLAG (GND) ──
    for fx, fy in sorted(flags):
        lines.append(f"FLAG {fx} {fy} 0")

    # ── 输出 TEXT (SPICE 指令，用 ! 前缀) ──
    text_base_y = gnd_y + 40
    for ti, d in enumerate(directives):
        if d == ".end":
            continue
        lines.append(f"TEXT {LEFT_X} {text_base_y + ti * 24} Left 2 !{d}")

    asc_path = cir.with_suffix(".asc")
    asc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return asc_path


if __name__ == "__main__":
    print(f"OK: {convert(sys.argv[1])}")
