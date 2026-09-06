"""临时冷启动测试：内置计时 + 硬超时 + 详细日志（跑完删除）。"""

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_cold_test_output.log"
MANAGER = r"C:\Program Files\NetEase\MuMu\nx_main\MuMuManager.exe"
NO_WINDOW = 0x08000000


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


log("=== 冷启动测试开始 ===")
log("官方 shutdown 关闭模拟器…")
try:
    subprocess.run([MANAGER, "control", "-v", "0", "shutdown"],
                   capture_output=True, timeout=30, creationflags=NO_WINDOW)
    log("shutdown 命令完成")
except Exception as e:
    log(f"shutdown 异常（忽略）: {e!r}")
time.sleep(8)

log("启动 CLI 调试打卡（硬限时 330s）…")
t0 = time.time()
proc = subprocess.Popen(
    [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "deli_eplus", "--debug"],
    cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace",
)
while True:
    line = proc.stdout.readline()
    if not line and proc.poll() is not None:
        break
    if line:
        log("  " + line.rstrip())
    if time.time() - t0 > 330:
        proc.kill()
        log("!! 330s 硬超时，已强杀")
        break
rc = proc.wait()
total = time.time() - t0
log(f"CLI 退出 rc={rc} 总耗时 {total:.0f}s")
log("=== 冷启动测试结束 ===")
