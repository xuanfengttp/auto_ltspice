"""LTspice 仿真执行器(含异步等待)。

ADI 新版 LTspice 的 -b 批处理是异步的：进程立即返回，.raw/.log
产物稍后才落盘。因此这里通过轮询等待产物：等 .log 出现且含
"Total elapsed time"(表示算完)，且 .raw 出现。
"""

import subprocess
import sys
import time
from pathlib import Path

# 双模式导入：既支持 `python -m tools.run_sim`(包内导入)，
# 也支持 `python tools/run_sim.py`(直接运行，需把工程根加入 sys.path)。
try:
    from tools import config
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools import config


def run(cir_path) -> Path:
    cir = Path(cir_path)
    if not cir.exists():
        raise FileNotFoundError(f"网表文件不存在: {cir}")

    cfg = config.load()
    exe = Path(cfg["ltspice_exe"])
    raw = cir.with_suffix(".raw")
    log = cir.with_suffix(".log")

    # 清理旧产物，避免误判上一轮结果
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
        if log.exists():
            text = log.read_text(errors="ignore")
            if "Fatal Error" in text or "Error:" in text:
                raise RuntimeError(f"LTspice 仿真出错:\n{text[-500:]}")
            if raw.exists() and "Total elapsed time" in text:
                return raw
        time.sleep(interval)

    # 超时：回读 .log 尾部帮助定位真正原因(如 "only one point"、收敛失败等)
    hint = ""
    if log.exists():
        tail = log.read_text(errors="ignore")[-500:]
        hint = f"\n最后的 .log 内容(可能含线索)：\n{tail}"
    else:
        hint = "\n(未生成 .log，检查 LTspice 路径与网表语法)"
    raise TimeoutError(f"仿真超时({timeout}s)，未产出结果: {cir}{hint}")


if __name__ == "__main__":
    out = run(sys.argv[1])
    print(f"OK: {out}")
