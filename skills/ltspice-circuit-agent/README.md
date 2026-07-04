# LTspice Circuit Agent Skill

**一句话**：让 AI agent 用 LTspice 帮电路小白完成电路设计、仿真、迭代的全自动工作流。

## 这是什么

一个可加载到任何 Claude Code agent 的 skill，提供：
- **工作流指引**（`SKILL.md`）：告诉 agent 如何用工具链辅助用户完成电路工作
- **自动化脚本**（`scripts/`）：5 个 Python 工具，覆盖 配方库 → 仿真执行 → 指标解析 → 网表转原理图
- **依赖与配置**（`assets/`）：`requirements.txt` + `config.yaml` 模板

## 使用方法

### 1. 载入 skill
把整个 `ltspice-circuit-agent/` 文件夹放到你的 `.claude/skills/` 目录下，Claude Code 会自动识别。

### 2. Agent 首次使用时会做
- 复制 `scripts/*.py` 到工程的 `tools/` 目录
- 复制 `assets/requirements.txt` 到工程根目录
- 创建 `config.yaml`（从 `assets/config.yaml.template` 复制并填入用户的 LTspice 路径）
- 安装依赖 `pip install -r requirements.txt`
- 运行验证确认工具链畅通

### 3. 用户只需说
> "我要设计一个 1kHz 的低通滤波器"

Agent 自动：
1. 调用 `circuit_lib.rc_lowpass(1000)` 生成网表
2. 调用 `run_sim.run()` 执行 LTspice 仿真
3. 调用 `parse_raw.extract()` 提取指标（截止频率、增益）
4. 判断是否满足需求，不满足则调参重新仿真
5. 用 `net2asc.convert()` 生成原理图供用户查看
6. 交付完整项目（网表 + 原理图 + 仿真结果 + 报告）

## 核心理念

- **网表为源**：`.cir` 是设计真相（纯文本，agent 可靠生成），`.asc` 是可视化投影
- **指标驱动**：Agent 读 JSON 数值判断电路质量，无需人工看波形
- **全自动闭环**：配方 → 仿真 → 指标 → 判断 → 调整 → 重新仿真，agent 独立完成

## 适用场景

- **电路小白**：懂需求但不懂电路、不会用 LTspice
- **快速原型**：需要快速验证电路方案、迭代参数
- **教学演示**：展示 AI 如何辅助硬件设计

## 文件结构

```
ltspice-circuit-agent/
├── SKILL.md                    # Agent 作业指引（SOP）
├── README.md                   # 本文件
├── scripts/                    # 工具脚本（复制到工程 tools/ 使用）
│   ├── config.py               # 配置管理
│   ├── circuit_lib.py          # 电路配方库
│   ├── run_sim.py              # 仿真执行器（异步等待）
│   ├── parse_raw.py            # 波形指标解析
│   └── net2asc.py              # 网表转原理图
└── assets/                     # 依赖与配置模板
    ├── requirements.txt        # Python 依赖
    └── config.yaml.template    # 配置模板
```

## 技术栈

- **LTspice**：ADI 官方电路仿真器（免费）
- **Python 3.9+**：工具链语言
- **spicelib**：解析 `.raw` 波形文件
- **PyYAML**：配置管理

## 许可

MIT License
