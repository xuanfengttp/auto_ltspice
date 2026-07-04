# LTspice AI Agent 辅助硬件开发工作流 — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

> ## ✅ 完成状态批注（2026-07-03 更新）
>
> 本计划的核心任务（Task 0-6：工具链 + 测试）**已全部实现并通过两轮真实测试验证**。之后按用户新需求做了计划外的扩展，最终交付**偏离原计划**，以实际交付物为准：
>
> - **封装为 skill**（计划外）：整套工具链封装进 `.claude/skills/ltspice-circuit-agent/`，别人 agent 载入即用。
> - **配方库扩展**：从计划的 `rc_lowpass` 一个，扩到 4 个（`rc_lowpass`/`rc_highpass`/`voltage_divider`/`colpitts_oscillator`）。
> - **parse_raw 扩展**：从"仅 AC"扩到 ac（自动分低通/高通）/op/dc/tran 四类。
> - **文档体系精简**：计划的 6 份 docs（Task 8）**未建**，内容合并进 skill 的 `SKILL.md`。
> - **示范项目**（Task 9）：以 `projects/` 下 4 个真实案例交付（低通/高通/分压/振荡）。
> - **跳过 git**：环境无 git，用户确认"只出文件、不做版本控制"，故所有 `git init`/commit 步骤未执行。
> - **命令行修正**：`python tools/xxx.py` → `python -m tools.xxx`（测试发现 ModuleNotFoundError，已修 sys.path 兜底）。
>
> 下面的原始任务清单保留作实现留痕。测试与修复的完整经过见 skill 交付物与 `projects/`。

**目标：** 搭建一套工具链 + 文档体系，让电路小白用自然语言提需求，由 AI agent 驱动 LTspice 完成"设计→仿真→读指标→迭代→交付"全自动闭环。

**架构：** 网表 `.cir` 是"真相源"。四个 Python 工具围绕它：`run_sim`(调 LTspice `-b` 仿真)、`parse_raw`(解析波形出指标)、`net2asc`(网表转原理图)、`circuit_lib`(电路配方库)。agent 读指标 JSON 判断达标并迭代。六份文档保证可交付他人。

**技术栈：** Python 3.14（`.venv`）、spicelib 1.6.2（跑仿真+解析 `.raw`）、PyYAML（配置）、matplotlib（波形图）、pytest（测试）、ADI LTspice 26.0.2。

---

## 关键技术事实（已实测验证，实现时依赖）

1. **LTspice 路径**：`D:/Users/xuanfengttp/AppData/Local/Programs/ADI/LTspice/LTspice.exe`（ADI 新版 26.0.2）。
2. **venv Python**：`D:/project/python/LTspiece/.venv/Scripts/python.exe`（3.14.6，pip 已引导）。
3. **已装库**：spicelib 1.6.2、numpy 2.5.0、PyYAML 6.0.3、matplotlib 3.11.0，均有 Py3.14 wheel。
4. **uv 未安装** → 用 `requirements.txt`（`pip install -r` 与 `uv pip install -r` 通用）。
5. **`-b` 是异步的**：`LTspice.exe -b x.cir` 立刻返回，`.raw`/`.log` 几秒后才出现 → **必须轮询等待产物**。实测 RC 电路 0.027s 算完。
6. **spicelib RawRead**：`RawRead(path).get_trace_names()` 返回 `['frequency','V(in)','V(out)',...]`；`get_trace('V(out)').get_wave()` 取波形。**坑**：AC 分析不能用 `get_axis()`（报 "does not have an axis"），频率轴要用 `get_trace('frequency').get_wave()`。
7. **当前非 git 仓库**：计划第一步先 `git init`，之后每任务 commit。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `config.yaml` | 环境配置：LTspice 路径、超时、默认输出目录。换机器只改这里 |
| `requirements.txt` | Python 依赖清单 |
| `.gitignore` | 忽略 .venv、__pycache__、*.raw、*.op.raw 等产物 |
| `tools/__init__.py` | 使 tools 成为包 |
| `tools/config.py` | 读取 config.yaml，提供路径常量（被其他工具复用，DRY） |
| `tools/run_sim.py` | 输入 .cir，调 LTspice -b，轮询等待，产出 .raw/.log |
| `tools/parse_raw.py` | 读 .raw，按 ac/tran/dc 提取指标，输出 metrics.json |
| `tools/net2asc.py` | 解析 .cir，自动布局，生成 .asc |
| `tools/circuit_lib.py` | 电路配方库：拓扑模板 + 元件计算，生成 .cir 文本 |
| `tests/test_config.py` | 测 config 读取 |
| `tests/test_run_sim.py` | 测仿真执行（含真实 LTspice 冒烟测试） |
| `tests/test_parse_raw.py` | 测指标提取 |
| `tests/test_circuit_lib.py` | 测配方生成网表 |
| `tests/test_net2asc.py` | 测原理图生成 |
| `README.md` + `docs/01~06` | 文档体系 |

---

## 任务 0：工程初始化

**文件：**
- 创建：`.gitignore`、`requirements.txt`、`config.yaml`

- [ ] **步骤 1：git init**

```bash
cd D:/project/python/LTspiece
git init
```

- [ ] **步骤 2：写 `.gitignore`**

```
.venv/
__pycache__/
*.pyc
*.raw
*.op.raw
*.log
_probe/
projects/**/*.raw
projects/**/*.op.raw
```

- [ ] **步骤 3：写 `requirements.txt`**

```
spicelib==1.6.2
numpy==2.5.0
PyYAML==6.0.3
matplotlib==3.11.0
pytest==8.3.4
```

- [ ] **步骤 4：写 `config.yaml`**

```yaml
# LTspice 可执行文件路径（换机器改这里）
ltspice_exe: "D:/Users/xuanfengttp/AppData/Local/Programs/ADI/LTspice/LTspice.exe"
# 仿真等待产物的超时（秒）
sim_timeout: 60
# 轮询间隔（秒）
poll_interval: 0.5
# 默认项目输出根目录
projects_dir: "projects"
```

- [ ] **步骤 5：安装依赖并验证**

运行：`D:/project/python/LTspiece/.venv/Scripts/python.exe -m pip install -r requirements.txt`
预期：全部 already satisfied 或 successfully installed。

- [ ] **步骤 6：Commit**

```bash
git add .gitignore requirements.txt config.yaml
git commit -m "chore: 工程初始化，环境配置与依赖清单"
```

---

## 任务 1：config 模块（配置读取）

**文件：**
- 创建：`tools/__init__.py`（空）、`tools/config.py`
- 测试：`tests/test_config.py`

- [ ] **步骤 1：写失败的测试** `tests/test_config.py`

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
预期：FAIL（`ModuleNotFoundError: No module named 'tools'` 或 config）。

- [ ] **步骤 3：写 `tools/__init__.py`（空文件）与 `tools/config.py`**

```python
# tools/config.py
from pathlib import Path
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"

def load() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ltspice_exe() -> Path:
    return Path(load()["ltspice_exe"])

def projects_dir() -> Path:
    return _ROOT / load()["projects_dir"]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
预期：3 passed。

- [ ] **步骤 5：Commit**

```bash
git add tools/__init__.py tools/config.py tests/test_config.py
git commit -m "feat: config 模块读取环境配置"
```

---

## 任务 2：run_sim（仿真执行器，含异步等待）

**文件：**
- 创建：`tools/run_sim.py`
- 测试：`tests/test_run_sim.py`

**关键：** `-b` 异步，必须轮询等待 `.raw` 出现且 `.log` 含 "Total elapsed time"（表示算完）。

- [ ] **步骤 1：写失败的测试** `tests/test_run_sim.py`

```python
from pathlib import Path
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
    import pytest
    with pytest.raises(FileNotFoundError):
        run_sim.run(tmp_path / "nope.cir")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/Scripts/python.exe -m pytest tests/test_run_sim.py -v`
预期：FAIL（module/attribute 未定义）。

- [ ] **步骤 3：写 `tools/run_sim.py`**

```python
# tools/run_sim.py
import subprocess
import sys
import time
from pathlib import Path
from tools import config

def run(cir_path) -> Path:
    cir = Path(cir_path)
    if not cir.exists():
        raise FileNotFoundError(f"网表文件不存在: {cir}")
    cfg = config.load()
    exe = Path(cfg["ltspice_exe"])
    raw = cir.with_suffix(".raw")
    log = cir.with_suffix(".log")
    # 清理旧产物，避免误判
    for f in (raw, log):
        if f.exists():
            f.unlink()
    # -b 批处理，异步启动
    subprocess.Popen([str(exe), "-b", str(cir)])
    # 轮询等待：log 出现且含 "Total elapsed time"，raw 出现
    timeout = cfg["sim_timeout"]
    interval = cfg["poll_interval"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        if log.exists() and raw.exists():
            text = log.read_text(errors="ignore")
            if "Total elapsed time" in text:
                return raw
            if "Fatal Error" in text or "Error:" in text:
                raise RuntimeError(f"LTspice 仿真出错:\n{text[-500:]}")
        time.sleep(interval)
    raise TimeoutError(f"仿真超时({timeout}s)，未产出结果: {cir}")

if __name__ == "__main__":
    out = run(sys.argv[1])
    print(f"OK: {out}")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_run_sim.py -v`
预期：2 passed（真实调用 LTspice，约几秒）。

- [ ] **步骤 5：Commit**

```bash
git add tools/run_sim.py tests/test_run_sim.py
git commit -m "feat: run_sim 调 LTspice -b 仿真并轮询等待产物"
```

---

## 任务 3：parse_raw（波形解析出指标）

**文件：**
- 创建：`tools/parse_raw.py`
- 测试：`tests/test_parse_raw.py`

**关键：** AC 频率轴用 `get_trace('frequency').get_wave()`，不能用 `get_axis()`。第一版实现 AC 指标（截止频率、通带增益）；tran/dc 留接口但先只做 AC，保持范围聚焦。

- [ ] **步骤 1：写失败的测试** `tests/test_parse_raw.py`

```python
from pathlib import Path
from tools import run_sim, parse_raw

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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/Scripts/python.exe -m pytest tests/test_parse_raw.py -v`
预期：FAIL。

- [ ] **步骤 3：写 `tools/parse_raw.py`**

```python
# tools/parse_raw.py
import json
import sys
import math
from pathlib import Path
from spicelib import RawRead

def _db(mag):
    return 20 * math.log10(mag) if mag > 0 else -999.0

def extract(raw_path, analysis="ac", out_node="V(out)") -> dict:
    raw = RawRead(str(raw_path))
    if analysis == "ac":
        freq = [abs(x) for x in raw.get_trace("frequency").get_wave()]
        vout = [abs(x) for x in raw.get_trace(out_node).get_wave()]
        gains_db = [_db(v) for v in vout]
        passband = max(gains_db)
        # -3dB 截止：从通带增益下降 3dB 的第一个频点
        target = passband - 3.0
        cutoff = None
        for i in range(1, len(gains_db)):
            if gains_db[i] <= target <= gains_db[i-1]:
                # 线性插值
                f0, f1 = freq[i-1], freq[i]
                g0, g1 = gains_db[i-1], gains_db[i]
                cutoff = f0 + (target - g0) * (f1 - f0) / (g1 - g0)
                break
        return {
            "analysis": "ac",
            "passband_gain_db": round(passband, 3),
            "cutoff_hz": round(cutoff, 2) if cutoff else None,
            "points": len(freq),
        }
    raise NotImplementedError(f"暂未实现的分析类型: {analysis}")

def main():
    raw = sys.argv[1]
    analysis = sys.argv[2] if len(sys.argv) > 2 else "ac"
    m = extract(raw, analysis=analysis)
    out = Path(raw).with_name("metrics.json")
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_parse_raw.py -v`
预期：1 passed。

- [ ] **步骤 5：Commit**

```bash
git add tools/parse_raw.py tests/test_parse_raw.py
git commit -m "feat: parse_raw 提取 AC 截止频率与通带增益"
```

---

## 任务 4：circuit_lib（电路配方库，先做 RC 一阶低通）

**文件：**
- 创建：`tools/circuit_lib.py`
- 测试：`tests/test_circuit_lib.py`

**范围：** 本任务只做 1 个配方 `rc_lowpass`，端到端打通"配方→网表→仿真→指标达标"。其余配方在任务 7 扩展。

- [ ] **步骤 1：写失败的测试** `tests/test_circuit_lib.py`

```python
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
    # 电容值应出现在网表中且量级正确（1.5e-07 ~ 1.7e-07）
    import re
    m = re.search(r"C1 out 0 ([0-9.eE+-]+)", net)
    assert m
    c = float(m.group(1))
    assert 1.5e-7 < c < 1.7e-7
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/Scripts/python.exe -m pytest tests/test_circuit_lib.py -v`
预期：FAIL。

- [ ] **步骤 3：写 `tools/circuit_lib.py`**

```python
# tools/circuit_lib.py
import math

def rc_lowpass(cutoff_hz: float, r: float = 1000.0) -> str:
    """一阶 RC 低通滤波器配方。给定截止频率和电阻，算出电容并生成网表。"""
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
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_circuit_lib.py -v`
预期：2 passed。

- [ ] **步骤 5：Commit**

```bash
git add tools/circuit_lib.py tests/test_circuit_lib.py
git commit -m "feat: circuit_lib 首个配方 rc_lowpass"
```

---

## 任务 5：端到端闭环冒烟测试

**文件：**
- 创建：`tests/test_e2e.py`

**目的：** 验证"配方→网表→仿真→指标"整条链路对齐，这是整个方案的核心闭环。

- [ ] **步骤 1：写端到端测试** `tests/test_e2e.py`

```python
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
```

- [ ] **步骤 2：运行验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_e2e.py -v`
预期：1 passed。这证明 agent 的自动迭代闭环技术上成立。

- [ ] **步骤 3：Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: 端到端闭环冒烟测试（配方→仿真→指标）"
```

---

## 任务 6：net2asc（网表转原理图）

**文件：**
- 创建：`tools/net2asc.py`
- 测试：`tests/test_net2asc.py`

**范围：** 用 spicelib 的 `AscEditor` 能力困难（它是读 .asc 而非写）。第一版自己实现最简单的**线性链式布局**：把元件从左到右一字排开、上下接地，保证简单电路能在 LTspice 打开。复杂布局不追求，YAGNI。

**先做技术验证：** 实现前，工作者需先手工造一个最简 .asc（一个电阻）在 LTspice 打开确认格式，再据此写生成器。.asc 格式要点：`Version 4` 头、`SHEET 1 W H`、`SYMBOL <type> x y R0`、`WIRE x1 y1 x2 y2`、`FLAG x y 0`（接地）。

- [ ] **步骤 1：写失败的测试** `tests/test_net2asc.py`

```python
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
    # 三个元件 V1 R1 C1 都有符号
    assert text.count("SYMBOL") >= 3

def test_net2asc_has_ground(tmp_path):
    cir = tmp_path / "design.cir"
    cir.write_text(RC_CIR, encoding="ascii")
    asc = net2asc.convert(cir)
    assert "FLAG" in asc.read_text()  # 接地符号
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv/Scripts/python.exe -m pytest tests/test_net2asc.py -v`
预期：FAIL。

- [ ] **步骤 3：写 `tools/net2asc.py`**

```python
# tools/net2asc.py
import sys
from pathlib import Path

# LTspice 元件类型 → 符号名映射
_SYM = {"R": "res", "C": "cap", "L": "ind", "V": "voltage"}

def _parse_netlist(text):
    """提取元件行（跳过 * 注释、. 指令）。返回 [(refdes, nodes, value_tokens)]。"""
    parts = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("."):
            continue
        toks = line.split()
        refdes = toks[0]
        if refdes[0].upper() in _SYM:
            parts.append((refdes, toks[1:3], toks[3:]))
    return parts

def convert(cir_path) -> Path:
    cir = Path(cir_path)
    parts = _parse_netlist(cir.read_text())
    lines = ["Version 4", "SHEET 1 880 680"]
    x = 96
    for refdes, nodes, vals in parts:
        sym = _SYM[refdes[0].upper()]
        lines.append(f"SYMBOL {sym} {x} 96 R0")
        lines.append(f"SYMATTR InstName {refdes}")
        if vals:
            lines.append(f"SYMATTR Value {vals[0]}")
        # 元件底部接地引线 + FLAG
        lines.append(f"WIRE {x+16} 176 {x+16} 224")
        lines.append(f"FLAG {x+16} 224 0")
        x += 192
    asc = cir.with_suffix(".asc")
    asc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return asc

if __name__ == "__main__":
    print(f"OK: {convert(sys.argv[1])}")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_net2asc.py -v`
预期：2 passed。

- [ ] **步骤 5：人工验证（重要）**

用 net2asc 生成一个 .asc，在 LTspice 打开确认不报错、能看到元件。若格式有问题，据实际报错调整符号坐标/引脚。记录到 `docs/06-常见问题.md`。

- [ ] **步骤 6：Commit**

```bash
git add tools/net2asc.py tests/test_net2asc.py
git commit -m "feat: net2asc 网表转原理图（线性布局）"
```

---

## 任务 7：扩展配方库（Sallen-Key、运放放大器、RC 高通、分压）

**文件：**
- 修改：`tools/circuit_lib.py`
- 修改：`tests/test_circuit_lib.py`

**说明：** 每个配方一个函数，同一模式（算参数→拼网表字符串）。逐个 TDD。此处给出 RC 高通作为完整样板，其余（sallen_key_lowpass、noninverting_amp、voltage_divider）按同一结构实现，各配一个"网表含关键元件"的测试。

- [ ] **步骤 1：为 rc_highpass 写测试**（追加到 `tests/test_circuit_lib.py`）

```python
def test_rc_highpass_netlist():
    net = circuit_lib.rc_highpass(cutoff_hz=1000, r=1000)
    # 高通：R 和 C 位置互换，C 在信号路径
    assert "C1 in out" in net
    assert "R1 out 0 1000" in net
    assert ".ac" in net
```

- [ ] **步骤 2：运行验证失败**

运行：`.venv/Scripts/python.exe -m pytest tests/test_circuit_lib.py::test_rc_highpass_netlist -v`
预期：FAIL。

- [ ] **步骤 3：实现 rc_highpass**（追加到 `tools/circuit_lib.py`）

```python
def rc_highpass(cutoff_hz: float, r: float = 1000.0) -> str:
    """一阶 RC 高通滤波器配方。"""
    c = 1.0 / (2 * math.pi * r * cutoff_hz)
    return (
        f"* RC highpass fc={cutoff_hz}Hz R={r}ohm\n"
        f"V1 in 0 AC 1\n"
        f"C1 in out {c:.4g}\n"
        f"R1 out 0 {r:g}\n"
        f".ac dec 20 {cutoff_hz/100:g} {cutoff_hz*100:g}\n"
        f".end\n"
    )
```

- [ ] **步骤 4：运行验证通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_circuit_lib.py -v`
预期：全部 passed。

- [ ] **步骤 5：同法实现 voltage_divider**（追加）

测试：
```python
def test_voltage_divider():
    net = circuit_lib.voltage_divider(vin=5, vout=2.5, r_total=10000)
    assert "V1 in 0 5" in net
    assert "R1 in out" in net
    assert "R2 out 0" in net
    assert ".op" in net
```

实现：
```python
def voltage_divider(vin: float, vout: float, r_total: float = 10000.0) -> str:
    """电阻分压器。R2/(R1+R2)=vout/vin。"""
    r2 = r_total * vout / vin
    r1 = r_total - r2
    return (
        f"* voltage divider vin={vin} vout={vout}\n"
        f"V1 in 0 {vin:g}\n"
        f"R1 in out {r1:.4g}\n"
        f"R2 out 0 {r2:.4g}\n"
        f".op\n"
        f".end\n"
    )
```

- [ ] **步骤 6：运行全部配方测试通过**

运行：`.venv/Scripts/python.exe -m pytest tests/test_circuit_lib.py -v`
预期：全部 passed。

- [ ] **步骤 7：Commit**

```bash
git add tools/circuit_lib.py tests/test_circuit_lib.py
git commit -m "feat: 扩展配方库（rc_highpass, voltage_divider）"
```

> **注：** sallen_key_lowpass、noninverting_amp（含运放，需 .lib 模型）在文档 `05-电路配方库.md` 说明扩展方法，作为后续增量。运放配方依赖 LTspice 内置 UniversalOpamp2，实现时需在网表加 `.lib` 或用理想运放模型——本任务先交付无源配方，运放配方标记为"下一增量"。

---

## 任务 8：文档体系

**文件：**
- 创建：`README.md`、`docs/01-快速开始.md`、`docs/02-工作指引.md`、`docs/03-Agent协作规范.md`、`docs/04-工具链参考.md`、`docs/05-电路配方库.md`、`docs/06-常见问题.md`

**说明：** 每份文档内容依据前面已实现并测试通过的工具编写，确保文档与代码一致（不写未实现的功能）。

- [ ] **步骤 1：写 `README.md`**

内容要点（据实际工具编写）：
- 一句话定位：AI agent 辅助电路小白用 LTspice 做设计-仿真-迭代。
- 环境要求：Windows、Python 3.14、ADI LTspice、`.venv`。
- 快速开始：`pip install -r requirements.txt` → 指向 `docs/01-快速开始.md`。
- 目录结构说明（tools/ projects/ docs/）。

- [ ] **步骤 2：写 `docs/01-快速开始.md`**

手把手 5 分钟：激活 venv → 装依赖 → 跑 `python -m pytest tests/test_e2e.py` 看闭环通过 → 解释这代表什么。

- [ ] **步骤 3：写 `docs/02-工作指引.md`（小白日常）**

- 怎么提需求（给模板："我要一个 [类型] 电路，[关键指标]，看 [什么]"）。
- 举例：好需求 vs 模糊需求。
- 怎么验收 report.md、怎么在 LTspice 打开 .asc。

- [ ] **步骤 4：写 `docs/03-Agent协作规范.md`（喂给 AI 的 SOP，最关键）**

明确 agent 收到需求后的流程：
1. 澄清需求→确定分析类型(ac/tran/dc)和达标指标。
2. 查 circuit_lib 选配方→生成 design.cir 到 `projects/YYYY-MM-DD-<name>/`。
3. 调 run_sim → parse_raw → 读 metrics.json。
4. 对照目标判定；未达标改参数重跑（记录到 iterations.md），最多 N 轮。
5. 达标后 net2asc 出图 + 写 report.md。
6. 每步留痕。附一个完整 RC 低通的示范对话。

- [ ] **步骤 5：写 `docs/04-工具链参考.md`**

四个脚本的命令行用法、参数、输入输出、退出码，均据实际实现。

- [ ] **步骤 6：写 `docs/05-电路配方库.md`**

已有配方清单（rc_lowpass/rc_highpass/voltage_divider）+ 参数说明 + "如何加新配方"步骤（写函数→写测试→跑通）。

- [ ] **步骤 7：写 `docs/06-常见问题.md`**

据实测记录：仿真超时怎么办、-b 异步等待、AC 用 frequency trace 不用 get_axis、.asc 打开报错排查、换机器改 config.yaml。

- [ ] **步骤 8：Commit**

```bash
git add README.md docs/
git commit -m "docs: 完整文档体系（README + 6 份指引）"
```

---

## 任务 9：示范项目（交付样例）

**文件：**
- 创建：`projects/2026-07-01-lowpass-1khz/`（design.cir、design.asc、metrics.json、iterations.md、report.md）

**目的：** 提供一个完整走通的真实样例，新用户照着看就懂。

- [ ] **步骤 1：用工具链生成完整样例**

```bash
# 生成网表→仿真→指标→原理图，产物放入项目目录
.venv/Scripts/python.exe -c "from tools import circuit_lib; open('projects/2026-07-01-lowpass-1khz/design.cir','w').write(circuit_lib.rc_lowpass(1000,1000))"
.venv/Scripts/python.exe tools/run_sim.py projects/2026-07-01-lowpass-1khz/design.cir
.venv/Scripts/python.exe tools/parse_raw.py projects/2026-07-01-lowpass-1khz/design.raw ac
.venv/Scripts/python.exe tools/net2asc.py projects/2026-07-01-lowpass-1khz/design.cir
```

- [ ] **步骤 2：手写 `iterations.md` 和 `report.md`**

iterations.md 记录一轮设计过程；report.md 汇总需求→电路→BOM→指标→结论。作为文档 02/03 引用的实例。

- [ ] **步骤 3：Commit**

```bash
git add projects/2026-07-01-lowpass-1khz/design.cir projects/2026-07-01-lowpass-1khz/design.asc projects/2026-07-01-lowpass-1khz/metrics.json projects/2026-07-01-lowpass-1khz/iterations.md projects/2026-07-01-lowpass-1khz/report.md
git commit -m "docs: 示范项目 1kHz 低通滤波器完整样例"
```

---

## 自检结果

**规格覆盖度：** 规格第 3 章架构→任务 1-6；第 6 章四工具→run_sim(任务2)/parse_raw(任务3)/net2asc(任务6)/circuit_lib(任务4,7)；第 7 章文档体系→任务8；第 4 章工作流留痕→任务8 文档03 + 任务9 样例；成功标准第 4 条(仅凭文档跑通)→任务8+9。全部覆盖。

**范围裁剪对齐：** parse_raw 第一版只做 AC（tran/dc 留接口）、net2asc 只做线性布局、运放配方标为下一增量——均符合规格 YAGNI 裁剪，且在计划中明确标注。

**占位符扫描：** 无 TODO/待定；每个代码步骤含完整代码；文档任务因内容依赖前序实现结果，给出明确要点清单而非占位符。

**类型一致性：** `config.load()`/`ltspice_exe()`、`run_sim.run(cir)→Path`、`parse_raw.extract(raw, analysis, out_node)→dict`（键 cutoff_hz/passband_gain_db）、`circuit_lib.rc_lowpass(cutoff_hz, r)→str`、`net2asc.convert(cir)→Path` 全计划一致。
