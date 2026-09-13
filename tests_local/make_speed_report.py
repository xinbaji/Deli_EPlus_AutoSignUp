"""把若干份 timing-*.txt 汇总成一份测速报告（Markdown）。

用法：
    .venv/Scripts/python tests_local/make_speed_report.py            # 取最近 3 份
    .venv/Scripts/python tests_local/make_speed_report.py a.txt b.txt
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS = PROJECT_ROOT / "logs"

ROW_RE = re.compile(r"^(.+?)\s+(-?\d+\.\d+)s\s*$")
DASH_RE = re.compile(r"^(.+?)\s+—\s*$")
FOCUS = ("★A 点登录 → 点智能考勤", "★B 点设置 → 退出登录项消失", "★B2 点设置 → 登录页真正出现")


def parse(path: Path) -> tuple[list[str], dict[str, float | None]]:
    order: list[str] = []
    values: dict[str, float | None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line) or DASH_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        if name in ("流程结果: 成功   结束时登录页可见: True",):
            continue
        value = float(m.group(2)) if m.lastindex and m.lastindex >= 2 else None
        if name not in values:
            order.append(name)
        values[name] = value
    return order, values


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}s"


def main() -> int:
    args = sys.argv[1:]
    if args:
        files = [Path(a) for a in args]
    else:
        files = sorted(LOGS.glob("timing-*.txt"))[-3:]
    if not files:
        print("找不到 timing-*.txt", file=sys.stderr)
        return 2

    runs = [parse(p) for p in files]
    order = runs[0][0]
    labels = [p.stem.replace("timing-", "") for p in files]

    lines = [
        "# 得力E+ 真机测速报告",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "- 设备：MuMu 模拟器 实例 0（Android 12）· ADB `127.0.0.1:16384`",
        "- 模拟器目录：`C:\\Program Files\\NetEase\\MuMu\\nx_main`",
        "- 打卡点：纬度 41.632339 · 经度 122.163874",
        "- 运行模式：**debug**（走完整流程，跳过实际打卡）",
        f"- 样本轮次：{len(files)}",
        "",
        "## 重点项（★A / ★B / ★B2）",
        "",
        "| 指标 | 含义 | " + " | ".join(f"第{i+1}轮" for i in range(len(files)))
        + " | 平均 | 最快 | 最慢 |",
        "|---|---|" + "---|" * (len(files) + 3),
    ]
    for name in FOCUS:
        vals = [r[1].get(name) for r in runs]
        good = [v for v in vals if v is not None]
        cells = " | ".join(fmt(v) for v in vals)
        avg = f"{sum(good)/len(good):.2f}s" if good else "—"
        lines.append(f"| {name} | — | {cells} | {avg} | "
                     f"{fmt(min(good)) if good else '—'} | {fmt(max(good)) if good else '—'} |")

    lines += ["", "## 各阶段明细", "",
              "| 阶段 | " + " | ".join(f"第{i+1}轮" for i in range(len(files))) + " |",
              "|---|" + "---|" * len(files)]
    for name in order:
        cells = " | ".join(fmt(r[1].get(name)) for r in runs)
        lines.append(f"| {name} | {cells} |")

    lines += [
        "",
        "## 口径说明",
        "",
        "- **★A 点登录 → 点智能考勤**：从点「登录」起，到点「智能考勤」为止（含注入虚拟定位）。",
        "- **★B 点设置 → 退出登录项消失**：`wait_gone(退出登录)` 返回即算完成——此时页面还在转场。",
        "- **★B2 点设置 → 登录页真正出现**：登出后等「登录」按钮真正渲染出来，才是用户看到的"
        "「回到登录页」（比 ★B 晚 0~0.5s）。",
        "- 所有等待均为「状态满足即返回」，超时预算只是上限，不是固定耗时。",
        "- 冷启动（模拟器未运行）额外 20~45s 用于安卓启动 + ADB 连接；上表为模拟器已在运行时的数值。",
        "",
        "## 结论",
        "",
    ]
    a_vals = [r[1].get(FOCUS[0]) for r in runs]
    b_vals = [r[1].get(FOCUS[2]) for r in runs]
    good_a = [v for v in a_vals if v is not None]
    good_b = [v for v in b_vals if v is not None]
    if good_a:
        lines.append(f"- ★A（点登录→点智能考勤）：**{min(good_a):.2f}~{max(good_a):.2f}s**，"
                     f"平均 {sum(good_a)/len(good_a):.2f}s。")
    if good_b:
        lines.append(f"- ★B2（点设置→登录页出现）：**{min(good_b):.2f}~{max(good_b):.2f}s**，"
                     f"平均 {sum(good_b)/len(good_b):.2f}s。")
    lines.append("- A、B 主要耗时在 App 页面切换/数据加载，框架侧（dump≈37ms）不构成瓶颈。")

    text = "\n".join(lines) + "\n"
    out = LOGS / f"speed-report-{time.strftime('%Y%m%d-%H%M%S')}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print("已写入:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
