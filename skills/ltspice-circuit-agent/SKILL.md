---
name: ltspice-circuit-agent
description: "AI agent 辅助电路小白使用 LTspice 完成电路设计、仿真与迭代的自动化工作流——网表为源、指标驱动、全自动闭环"
version: "1.0.0"
license: MIT
metadata:
  hermes:
    tags: [hardware, ltspice, circuit-design, automation]
---

# LTspice 电路 Agent 工作流

**面向场景**：用户是电路小白（不懂电路、不熟悉 LTspice），但非常懂需求。Agent 用这套工具帮他完成：
1. **设计**：从需求生成网表（调用配方库或手动构造）
2. **仿真**：自动运行 LTspice 批处理、等待产物
3. **验证**：自动解析波形文件、提取指标、判断是否满足需求
4. **迭代**：指标不符 → 调参/改拓扑 → 重新仿真，全自动闭环

**核心理念**：
- **网表为源**：`.cir` 网表是设计真相（纯文本，agent 可靠生成），`.asc` 原理图是同一电路的**忠实可视化副本**（自包含、可直接 Run 仿真，点 Run 出波形）
- **指标驱动**：Agent 读 JSON 数值指标判断电路质量，无需解读波形图
- **全自动闭环**：配方 → 仿真 → 指标 → 判断 → 调整 → 重新仿真，agent 独立完成

---

## 前置条件

**用户环境**：
- Windows 系统，已安装 ADI LTspice（典型路径 `C:\Program Files\ADI\LTspice\LTspice.exe` 或 `%LOCALAPPDATA%\Programs\ADI\LTspice\LTspice.exe`）
- Python 3.9+（推荐 3.14+），有 venv 或其他虚拟环境管理工具

**Agent 准备**：
1. **复制工具到工程**：把本 skill 的 `scripts/` 下所有 `.py` 文件复制到用户工程的 `tools/` 目录
2. **复制依赖清单**：把 `assets/requirements.txt` 复制到工程根目录
3. **创建 config.yaml**：复制 `assets/config.yaml.template` 到工程根目录改名为 `config.yaml`，修改 `ltspice_exe` 为用户本机实际路径（问用户或用 PowerShell 搜索：`Get-ChildItem 'C:\Program Files' -Recurse -Filter LTspice.exe -ErrorAction SilentlyContinue`）
4. **安装依赖**：`pip install -r requirements.txt`（或用 uv/pip-tools 等工具）
5. **验证环境**：运行一次示例仿真确认 LTspice 批处理能正常工作

---

## 命令行注意事项（Windows PowerShell）

本工具链在 Windows + PowerShell 环境下使用，有两个 shell 层面的坑（**非工具 bug**，但照做者极易踩），务必注意：

1. **含括号的节点名必须加引号**：`V(out)`、`V(coll)` 里的括号会被 PowerShell 当成子表达式解析并报错。命令行传节点名时写成 `'V(out)'`。
   - ❌ `python -m tools.parse_raw x.raw ac V(out)` → 报错 `'out' is not recognized`
   - ✅ `python -m tools.parse_raw x.raw ac 'V(out)'`
2. **多行 Python 代码不要用 `python -c` 内联**：PowerShell 的 here-string 会重新解析内容导致 `SyntaxError`。需要跑多行逻辑时，**写成 `.py` 脚本文件再运行**，或用 `python -m tools.xxx` 调用现成工具。
3. **脚本要在工程根目录运行**：`from tools import config` 依赖工程根在 `sys.path` 上。在 `projects/` 子目录里直接跑脚本会 `import tools` 失败——回到工程根运行，或用 `python -m tools.xxx`（脚本已有 sys.path 兜底，但根目录运行最稳妥）。

---

## 工具说明

### 1. `tools/config.py`
**职责**：集中管理配置（LTspice 路径、超时参数），DRY 原则。

**接口**：
```python
from tools import config
cfg = config.load()          # 返回 dict
exe = config.ltspice_exe()   # 返回 Path 对象
pdir = config.projects_dir() # 返回 Path 对象
```

### 2. `tools/circuit_lib.py`
**职责**：电路配方库。每个函数返回完整的 `.cir` 网表字符串。

**现有配方**（每个配方 docstring 首行标注其分析类型 ac/op/tran）：
- `rc_lowpass(cutoff_hz, r=1000.0) -> str`：一阶 RC 低通滤波器【ac】
- `rc_highpass(cutoff_hz, r=10000.0) -> str`：一阶 RC 高通滤波器【ac】
- `voltage_divider(vin, vout, load_current) -> str`：电阻分压器，反算 R1/R2【op】
- `colpitts_oscillator(freq_hz, l=10e-6) -> str`：Colpitts 三极管 LC 振荡器【tran】

**分析类型映射**：`circuit_lib.ANALYSIS` 字典记录每个配方对应的 `parse_raw` analysis 参数，agent 可据此自动匹配指标提取方式。

**扩展方法**：用户需要新电路类型时，agent 在此添加新配方函数（参考现有配方格式：参数 → 计算元件值 → 拼接网表字符串，包含元件、激励、分析指令），并在 `ANALYSIS` 字典登记其分析类型。

**使用示例**：
```python
from tools.circuit_lib import rc_lowpass
netlist = rc_lowpass(cutoff_hz=1000, r=1000)  # 生成 1kHz 截止的 RC 低通网表
Path("my_filter.cir").write_text(netlist, encoding="utf-8")
```

### 3. `tools/run_sim.py`
**职责**：执行 LTspice 批处理仿真，处理异步等待（ADI LTspice `-b` 模式会立即返回，产物稍后落盘）。

**接口**：
```python
from tools.run_sim import run
raw_path = run("my_filter.cir")  # 阻塞等待，返回 .raw 文件路径（Path 对象）
# 失败抛异常：FileNotFoundError（网表不存在）、RuntimeError（仿真错误）、TimeoutError（超时）
```

**关键机制**：
- 清理旧产物（`.raw`/`.log`）避免误判
- 轮询等待：`.log` 出现 **且** 包含 `"Total elapsed time"` **且** `.raw` 存在 → 成功
- 错误检测：`.log` 中出现 `"Fatal Error"` 或 `"Error:"` → 立即抛 RuntimeError
- 超时保护：默认 60 秒（`config.yaml` 中 `sim_timeout` 可调）；**超时时会回读 `.log` 尾部附在异常里**，帮助定位真正原因（如 `.dc` 单点扫描不产 `.raw` 这类问题）

**命令行用法**（调试）：
```powershell
# 注意：必须用 -m 模块方式运行（脚本内有跨模块导入）
python -m tools.run_sim my_filter.cir
# 成功输出：OK: my_filter.raw
# （直接 python tools/run_sim.py 也已兼容，脚本内有 sys.path 兜底）
```

### 4. `tools/parse_raw.py`
**职责**：从 `.raw` 波形文件解析出数值指标（JSON 格式），供 agent 判断电路性能。

**支持的分析类型**（用 `analysis` 参数分派）：
- `"ac"`：交流频响 → 通带增益、-3dB 截止频率（**自动区分低通/高通**，返回 `filter_type`）
- `"op"`：直流工作点 → 输出电压 `vout`、所有节点电压、支路电流
- `"dc"`：直流扫描 → 输出节点电压序列（首/末值、点数）
- `"tran"`：瞬态 → 起振判断 `oscillating`、振荡频率 `freq_hz`、峰峰值、稳定性（用于振荡器）

**接口**：
```python
from tools.parse_raw import extract
# AC 滤波器
m = extract("filter.raw", analysis="ac", out_node="V(out)")
# {"analysis":"ac", "filter_type":"lowpass", "passband_gain_db":-0.0, "cutoff_hz":997.44, "points":81}
# DC 工作点（分压器等）
m = extract("divider.raw", analysis="op", out_node="V(out)")
# {"analysis":"op", "vout":3.3, "voltages":{...}, "currents":{...}}
# 瞬态（振荡器等）
m = extract("osc.raw", analysis="tran", out_node="V(coll)")
# {"analysis":"tran", "oscillating":true, "freq_hz":1048704.6, "vpp_steady":1.25, "stable":true, ...}
```

**命令行用法**：
```powershell
# PowerShell 下含括号的节点名必须加引号！
python -m tools.parse_raw my_filter.raw ac 'V(out)'
# 参数：<raw文件> [ac|op|dc|tran] [节点名]
# 输出 JSON 到终端，同时保存到 metrics.json（同目录）
```

**重要陷阱**：
- AC 分析的频率轴用 `get_trace('frequency').get_wave()`，**不能**用 `get_axis()`（会抛 "This RAW file does not have an axis"）
- tran 分析的时间轴用 `get_trace('time').get_wave()`
- 指标语义要与电路匹配：`cutoff_hz`（-3dB 截止）只对滤波器有意义，别套用到 LC 谐振腔（谐振峰 ≠ 截止频率）

### 5. `tools/net2asc.py`
**职责**：将 `.cir` 网表转换为**自包含、可直接 Run 仿真的完整原理图 `.asc`**。用户双击 `.asc` → LTspice 打开 → 看到完整电路（元件符号 + 按节点互连 WIRE + 接地 + 标注值 + 仿真指令）→ 点 Run → 出波形。不依赖 `.cir`。

**.asc 是 `.cir` 的忠实可视化副本**——网表描述什么电路，原理图就画出什么电路，二者等价。

**支持的元件**：R、C、L、V（电压源）、Q（NPN 三极管）。元件引脚坐标来自 LTspice 标准符号库，互连精确。

**限制**：
- 不支持 PMOS/NMOS/运放（符号坐标待补充）
- 复杂拓扑（反馈环路多的电路）会产生交叉连线，原理图可跑但不美观

**接口**：
```python
from tools.net2asc import convert
asc_path = convert("my_filter.cir")  # 返回同名 .asc 文件路径
```

**命令行用法**：
```powershell
python -m tools.net2asc my_filter.cir
# 成功输出：OK: my_filter.asc
# 生成后直接双击 .asc 文件，LTspice 会打开并显示完整电路，点 Run 即可仿真
```

---

## Agent 工作流（标准作业程序 SOP）

### 阶段 0：环境检查（首次使用）
1. 确认用户已安装 LTspice，获取路径写入 `config.yaml`
2. 复制 `scripts/*.py` 到工程 `tools/` 目录
3. 复制 `assets/requirements.txt` 到工程根目录
4. 安装依赖 `pip install -r requirements.txt`
5. 跑一个最简单的验证（例如生成 1kHz RC 低通 → 仿真 → 解析指标），确认工具链畅通

### 阶段 1：需求理解
**Agent 要做的**：
- 问清楚用户要设计什么电路（滤波器？放大器？振荡器？）
- 问清楚性能指标（例如：截止频率 1kHz、通带增益 0dB、负载电阻 10kΩ）
- 问清楚约束条件（例如：电阻不超过 100kΩ、电容用常见值）

**输出**：明确的需求描述（写成注释或文档）

### 阶段 2：设计（生成网表）
**两种路径**：

**路径 A：调用配方库**（推荐，适用于常见电路）
```python
from tools.circuit_lib import rc_lowpass
netlist = rc_lowpass(cutoff_hz=1000, r=1000)
Path("projects/my_project/filter.cir").write_text(netlist, encoding="utf-8")
```

**路径 B：手动构造网表**（适用于配方库没有的电路）
- Agent 根据电路拓扑知识，手写 SPICE 网表字符串
- 包含：元件定义、激励源、分析指令（`.ac`/`.tran`/`.dc`）
- 例子见 `circuit_lib.py` 中的 `rc_lowpass` 函数体

**注意事项**：
- 网表是纯文本，agent 可以可靠生成（比生成原理图坐标简单得多）
- 激励和分析指令必须匹配：AC 分析需要 `AC` 源、`.ac` 指令；瞬态分析需要时域源、`.tran` 指令

### 阶段 3：仿真
```python
from tools.run_sim import run
try:
    raw_path = run("projects/my_project/filter.cir")
    print(f"仿真成功：{raw_path}")
except RuntimeError as e:
    print(f"仿真失败：{e}")
    # Agent 读取错误信息，判断是网表语法错误还是收敛问题，调整后重试
except TimeoutError:
    print("仿真超时，可能电路过于复杂或配置的 sim_timeout 太短")
```

**异常处理**：
- `RuntimeError`：LTspice 报错（语法错误、元件值非法、收敛失败等），agent 读取 `.log` 文件最后 500 字符，分析错误原因
- `TimeoutError`：仿真时间超过 `sim_timeout`（默认 60 秒），可能需要简化电路或放宽扫描范围

### 阶段 4：指标提取与验证

**先确定分析类型**：`analysis` 参数必须与网表的分析指令匹配——
`.ac`→`"ac"`、`.op`→`"op"`、`.dc`→`"dc"`、`.tran`→`"tran"`。
用配方库时可查 `circuit_lib.ANALYSIS[配方名]` 自动得到。用错类型会读不到指标。

```python
from tools.parse_raw import extract
# 例：AC 滤波器
metrics = extract(raw_path, analysis="ac", out_node="V(out)")
print(f"通带增益：{metrics['passband_gain_db']} dB")
print(f"截止频率：{metrics['cutoff_hz']} Hz")

# Agent 判断是否满足需求
target_cutoff = 1000  # 用户需求
tolerance = 0.05      # 允许 5% 误差
if metrics['cutoff_hz'] and abs(metrics['cutoff_hz'] - target_cutoff) / target_cutoff < tolerance:
    print("✓ 指标符合需求")
else:
    print(f"✗ 截止频率偏差过大，需要调整")
```

**不同电路的验证要点**：
- 滤波器（ac）：看 `cutoff_hz`、`passband_gain_db`、`filter_type`
- 分压器/偏置（op）：看 `vout`、`currents`（核对电压和功耗）
- 振荡器（tran）：看 `oscillating`（是否起振）、`freq_hz`、`stable`

**Agent 的判断逻辑**：
- 对比实际指标与目标需求
- 如果不符，分析原因（例如：截止频率偏低 → 电容值偏大 → 减小电容）
- 进入迭代阶段

### 阶段 5：迭代调优
**Agent 自动调参**：
```python
# 例：截止频率实测 900Hz，目标 1000Hz，偏低 10%
# 原因：电容偏大（C = 1/(2πRf)，f 偏低说明 C 偏大）
# 调整：减小电容 10%
new_netlist = rc_lowpass(cutoff_hz=1000, r=1000)  # 配方会自动算出正确的 C
# 或手动微调：old_c * 0.9
# 重新仿真
raw_path = run("projects/my_project/filter_v2.cir")
metrics = extract(raw_path, analysis="ac")
# 重复判断，直到满足需求或达到最大迭代次数
```

**迭代策略**：
- 简单电路（如 RC 滤波器）：直接用配方公式反算，一次到位
- 复杂电路：二分法、梯度下降、或经验公式逐步逼近
- 设置最大迭代次数（例如 10 次）防止死循环

### 阶段 6：交付
**生成产物**：
1. **网表**：`filter.cir`（设计真相，版本管理的源文件）
2. **原理图**：`filter.asc`（可视化，供用户在 LTspice 中查看）
   ```python
   from tools.net2asc import convert
   asc_path = convert("projects/my_project/filter.cir")
   ```
3. **仿真结果**：`filter.raw`（波形数据）、`metrics.json`（指标摘要）
4. **项目报告**：用 markdown 写一份报告，包含：
   - 需求描述
   - 最终电路参数（R、C 值）
   - 仿真指标（截止频率、增益等）
   - 使用说明（如何在 LTspice 中打开 `.asc`）

**目录结构示例**：
```
projects/
  my_lowpass_1khz/
    filter.cir          # 网表（源）
    filter.asc          # 原理图（自动生成）
    filter.raw          # 波形（仿真产物）
    filter.log          # 仿真日志
    metrics.json        # 指标摘要
    README.md           # 项目报告
```

---

## 常见问题与陷阱

### 1. LTspice `-b` 批处理异步问题
**现象**：`subprocess.run([ltspice, "-b", "x.cir"])` 立即返回，但 `.raw` 文件几秒后才出现。  
**原因**：ADI LTspice 26.0+ 的 `-b` 模式是异步的。  
**解决**：`run_sim.py` 已实现轮询等待机制，agent 直接调用 `run()` 即可。

### 2. spicelib AC 分析频率轴陷阱
**现象**：`raw.get_axis()` 抛异常 "This RAW file does not have an axis"。  
**原因**：AC 分析的频率不是 axis，而是一个普通 trace。  
**解决**：用 `raw.get_trace('frequency').get_wave()`（`parse_raw.py` 已处理）。

### 3. 网表语法错误
**现象**：`run_sim.py` 抛 `RuntimeError`，`.log` 中有 "Error" 或 "Fatal Error"。  
**排查**：
- 元件名首字母必须匹配类型（R、C、L、V 等）
- 节点名不能有空格或特殊字符（用 `_` 或数字）
- 分析指令必须与激励匹配（AC 源配 `.ac`、时域源配 `.tran`）

### 4. 仿真超时
**现象**：`run_sim.py` 抛 `TimeoutError`。  
**先看异常信息**：超时异常里会附上 `.log` 尾部内容，**先读这段线索**——很多"超时"其实是网表问题（例如 `.dc V1 10 10 1` 单点扫描 LTspice 判定 "only one point" 不产 `.raw`，应改用 `.op`）。  
**若 `.log` 确无错误**（真的算得慢）：
- 减少扫描点数（`.ac dec 20` → `.ac dec 10`）
- 增大 `config.yaml` 中的 `sim_timeout`
- 简化电路（例如减少非线性元件）

### 5. 配方库缺失电路类型
**现象**：用户要设计的电路 `circuit_lib.py` 里没有。  
**现有配方**：rc_lowpass、rc_highpass、voltage_divider、colpitts_oscillator。  
**解决**：
- Agent 查阅 SPICE 语法手册，手动构造网表字符串（参考现有配方的网表格式）
- 或者在 `circuit_lib.py` 中添加新配方函数，并在 `ANALYSIS` 字典登记分析类型

### 6. 指标全为空 / 语义不对
**现象**：`extract()` 返回的关键字段是 `None`，或数值明显不合理。  
**排查**：
- `analysis` 参数是否与网表分析指令匹配（`.op` 却传了 `"ac"`）
- `out_node` 节点名是否正确（振荡器输出常是 `V(coll)` 而非 `V(out)`）
- 指标语义是否适配电路（`cutoff_hz` 只对滤波器有意义，别用于 LC 谐振腔）

### 7. 数值发散未被察觉
**现象**：仿真"成功"，但节点电压高达数十万伏（物理不合理）。  
**原因**：LTspice 数值不稳定，但 `run_sim.py` 只看是否算完，不判断物理合理性。  
**解决**：agent 提取指标后应核对数值范围（电压/电流是否在合理量级），发现异常值即视为设计问题，调整后重试。

---

## 扩展方向

1. **更多配方**：已有低通/高通/分压/振荡；可继续加带通、二阶巴特沃斯、共射放大器等
2. **更多分析细化**：tran 补充上升时间/过冲、dc 补充扫描曲线拐点
3. **参数扫描**：批量仿真多组参数，找最优解
4. **成本优化**：从 E12/E24 电阻系列中选择最接近的标准值
5. **灵敏度分析**：元件容差 ±10% 时指标变化范围

---

## 红线（Agent 绝不要做的事）

1. **绝不**手动编辑 `.asc` 原理图文件（坐标复杂、易错，交给 `net2asc.py`）
2. **绝不**跳过仿真直接猜测指标（必须运行 LTspice 获得真实结果）
3. **绝不**忽略 `run_sim.py` 的异常（必须读异常里的 `.log` 线索，调整后重试）
4. **绝不**用 `get_axis()` 读取 AC 分析频率（用 `get_trace('frequency')`）；tran 用 `get_trace('time')`
5. **绝不**用错 `analysis` 参数（必须与网表分析指令匹配 ac/op/dc/tran）
6. **绝不**在未确认指标符合需求、且数值物理合理时就交付（必须验证通过）

---

## 总结

这套工具链让 agent 能像真正的硬件工程师一样工作：理解需求 → 设计电路 → 仿真验证 → 迭代优化 → 交付产物。关键是**网表为源**（agent 擅长生成文本）、**指标驱动**（agent 读 JSON 判断，无需人工看波形）、**全自动闭环**（agent 独立完成整个流程）。

用户只需要表达需求，agent 处理所有技术细节。
