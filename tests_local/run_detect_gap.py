"""诊断：跑真实流程的同时高频采样，找出「界面上已有该文案，但我们的 xpath 判否」的元素。

对每个关键选择器，每轮采样基于**同一份 XML** 算两个判定：
  strict = 项目里那条 xpath（如 //android.widget.TextView[@text='设置']）
  fuzzy  = 该文案是否出现在任意节点的 text= 或 content-desc= 里
           （_text 选择器用「完全相等」，_contains 选择器用「包含」，与代码语义一致）
fuzzy 真而 strict 假 → 文案在界面上，但我们的选择器没匹配上：
    多半是节点 class 不是 TextView，或只暴露在 content-desc 里。
诊断会把这个节点的 class / content-desc 打出来。

运行：.venv/Scripts/python tests_local/run_detect_gap.py
"""

from __future__ import annotations

import re
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import uiautomator2 as u2  # noqa: E402
from uiautomator2.xpath import PageSource  # noqa: E402

from deli_eplus.config import Config  # noqa: E402
from deli_eplus.core import signup as S  # noqa: E402

# (标签, 项目里的 xpath, 文案, 匹配模式)
WATCH = [
    ("LOGIN_BUTTON", S.LOGIN_BUTTON, "登录", "exact"),
    ("AGREE_BUTTON", S.AGREE_BUTTON, "同意并继续", "exact"),
    ("ATTENDANCE_ENTRY", S.ATTENDANCE_ENTRY, "智能考勤", "exact"),
    ("MINE_TAB", S.MINE_TAB, "我的", "exact"),
    ("SETTINGS_ITEM", S.SETTINGS_ITEM, "设置", "exact"),
    ("LOGOUT_ITEM", S.LOGOUT_ITEM, "退出登录", "exact"),
    ("CONFIRM_BUTTON", S.CONFIRM_BUTTON, "确定", "exact"),
    ("PUNCH_BUTTON", S.PUNCH_BUTTON, "打卡", "exact"),
    ("SKIP_AD", S.SKIP_AD, "跳过", "exact"),
    ("IN_RANGE", S.IN_RANGE, "已在打卡", "contains"),
    ("OUT_RANGE", S.OUT_RANGE, "不在打卡", "contains"),
    ("GETTING_LOCATION", S.GETTING_LOCATION, "正在获取当前位置", "contains"),
    ("EXPIRED_HINT", S.EXPIRED_HINT, "账号已失效", "contains"),
]

NODE_RE = re.compile(r"<node([^>]*?)/?>")
ATTR_RE = {k: re.compile(k + r'="([^"]*)"') for k in ("class", "text", "content-desc")}


def fuzzy_hit(xml: str, needle: str, mode: str) -> str | None:
    """返回命中的 class（未命中返回 None）。"""
    for m in NODE_RE.finditer(xml):
        attrs = m.group(1)
        for attr in ("text", "content-desc"):
            value = (ATTR_RE[attr].search(attrs) or [None, ""])[1]
            if not value:
                continue
            ok = (value == needle) if mode == "exact" else (needle in value)
            if ok:
                return (ATTR_RE["class"].search(attrs) or [None, "?"])[1]
    return None


def main() -> int:
    cfg = Config(PROJECT_ROOT / "config.json")
    stat = {label: dict(samples=0, strict=0, fuzzy=0, miss=0, first=None, last=None, classes=set())
            for label, _, _, _ in WATCH}
    stop = threading.Event()
    samples = {"n": 0}
    t0 = time.monotonic()

    def sampler() -> None:
        d = u2.connect(cfg.serial)
        while not stop.is_set():
            try:
                xml = d.dump_hierarchy()
            except Exception:  # noqa: BLE001
                time.sleep(0.1)
                continue
            if '<hierarchy rotation="0" />' in xml:
                time.sleep(0.1)
                continue
            samples["n"] += 1
            elapsed = time.monotonic() - t0
            ps = PageSource(xml)
            for label, xpath, needle, mode in WATCH:
                st = stat[label]
                st["samples"] += 1
                try:
                    strict = len(ps.find_elements(xpath)) > 0
                except Exception:  # noqa: BLE001
                    strict = False
                cls = fuzzy_hit(xml, needle, mode)
                st["strict"] += int(strict)
                st["fuzzy"] += int(cls is not None)
                if cls is not None and not strict:
                    st["miss"] += 1
                    st["first"] = st["first"] if st["first"] is not None else elapsed
                    st["last"] = elapsed
                    st["classes"].add(cls)
            time.sleep(0.1)

    from deli_eplus.core.signup import SignupFlow
    flow = SignupFlow(
        serial=cfg.serial, emulator_path=cfg.emulator_path, emulator_num=cfg.emulator_num,
        users=cfg.users, location=cfg.location, debug=True, close_emulator_after=False,
        on_run=lambda s, m: print(f"[运行] {s} {m}", flush=True),
    )
    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    ok = flow.run()
    stop.set()
    thread.join(3)

    print(f"\n流程结果: {ok} | 采样轮数: {samples['n']}")
    print("=" * 92)
    print(f"{'选择器':<20}{'strict':>8}{'fuzzy':>8}{'漏检':>7}  首次/最后(s)      命中节点 class")
    print("-" * 92)
    for label, _, _, _ in WATCH:
        st = stat[label]
        span = "-" if st["first"] is None else f"{st['first']:.2f}/{st['last']:.2f}"
        cls = ",".join(sorted(st["classes"])) if st["classes"] else "-"
        flag = "  <<< 漏检" if st["miss"] else ""
        print(f"{label:<20}{st['strict']:>8}{st['fuzzy']:>8}{st['miss']:>7}  {span:<16} {cls}{flag}")
    print("=" * 92)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
