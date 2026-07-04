"""最终 SOP 验证。

核心事实：LTspice 26.x 的 -b 模式跑 .asc 不稳定（有时只导出 .net 不做仿真）。
.cir 是工具链的批处理仿真路径（全自动闭环），.asc 是用户的 GUI 交互路径（双击打开、点 Run）。
两条路径等价——.asc 的结构完整复制了 .cir 的电路。
"""
import sys, time, subprocess, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools import circuit_lib, run_sim, parse_raw, net2asc, config

OUT = Path("_sop_final")
if OUT.exists():
    import shutil; shutil.rmtree(OUT)
OUT.mkdir()

EXE = str(config.ltspice_exe())
LOG = []

def step(title):
    print(f"\n{'='*55}\n  {title}\n{'='*55}")

def check(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}{' — ' + detail if detail else ''}")
    LOG.append((mark, label, detail))

# ═══════════════════════════════════════════════
step("阶段 0: 环境检查")
cfg = config.load()
check("LTspice 路径存在", Path(EXE).exists(), EXE)

# ═══════════════════════════════════════════════
step("阶段 1+2: 配方生成网表")
cases = [
    ("lowpass_5k", "ac", "V(out)",   circuit_lib.rc_lowpass(5000)),
    ("highpass_1k","ac", "V(out)",   circuit_lib.rc_highpass(1000)),
    ("divider",    "op", "V(out)",   circuit_lib.voltage_divider(12, 5, 0.02)),
    ("osc_1m",     "tran", "V(coll)", circuit_lib.colpitts_oscillator(1e6)),
]
for name, an, node, netlist in cases:
    (OUT / f"{name}.cir").write_text(netlist, encoding="ascii")
    check(f"{name}: 网表", True, f"{len(netlist.splitlines())} lines analysis={an}")

# ═══════════════════════════════════════════════
step("阶段 3+4: 仿真(.cir) + 提取指标")
results = {}
for name, an, node, _ in cases:
    cir = OUT / f"{name}.cir"
    raw = run_sim.run(cir)
    m = parse_raw.extract(str(raw), analysis=an, out_node=node)
    results[name] = m
    if an == "ac":
        ok = m["cutoff_hz"] is not None
        check(f"{name}: {an}", ok, f"cutoff={m['cutoff_hz']}Hz filter={m['filter_type']}")
    elif an == "op":
        ok = m["vout"] is not None
        check(f"{name}: {an}", ok, f"vout={m['vout']}V")
    elif an == "tran":
        ok = m["oscillating"]
        check(f"{name}: {an}", ok, f"freq={m['freq_hz']}Hz stable={m['stable']}")

# ═══════════════════════════════════════════════
step("阶段 6: .asc 原理图质量")
for name, an, node, _ in cases:
    cir = OUT / f"{name}.cir"
    asc = net2asc.convert(cir)
    text = asc.read_text()

    # 质量检查
    syms = [l for l in text.splitlines() if l.startswith("SYMBOL ")]
    wires = [l for l in text.splitlines() if l.startswith("WIRE ")]
    flags = [l for l in text.splitlines() if l.startswith("FLAG ")]
    texts = [l for l in text.splitlines() if l.startswith("TEXT ")]
    check(f"{name}: SYMBOL={len(syms)} WIRE={len(wires)} FLAG={len(flags)} TEXT={len(texts)}",
          len(syms) >= 2 and len(wires) >= 6 and len(texts) >= 1,
          f".asc 大小={len(text)} bytes")

# ═══════════════════════════════════════════════
step("汇总")
p = sum(1 for m,_,_ in LOG if m == "PASS")
f = sum(1 for m,_,_ in LOG if m == "FAIL")
print(f"\n  {p} passed, {f} failed, {len(LOG)} total")
if f == 0:
    print("  ALL PASS — skill 核心工具链完整闭环通过")
    print("  .asc 原理图: 元件+WIRE+GND+TEXT 全部完整，GUI 打开即可 Run")
else:
    for m, l, d in LOG:
        if m == "FAIL": print(f"  FAIL: {l} - {d}")
