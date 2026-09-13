"""真机计时脚本：走真实签到流程（默认 debug 语义，不实际打卡），输出各阶段耗时。

本地专用——pyproject 的 testpaths 只收 tests/，CI 不会跑本文件。
参数全部取自仓库根 config.json（模拟器路径 / serial / 经纬度 / 账号）。

实现方式：包装 AndroidDevice / MuMuDevice / SignupFlow 上的真实方法，记录每个
调用的起止时间戳；流程仍由 SignupFlow 驱动，计时对象就是生产代码本身，
不存在"另写一遍流程"导致的偏差。

运行：
    .venv/Scripts/python tests_local/run_timing.py
    .venv/Scripts/python tests_local/run_timing.py --shutdown     # 结束后关闭自启的模拟器
    .venv/Scripts/python tests_local/run_timing.py --real-punch   # 实际打卡（默认跳过）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deli_eplus.config import Config  # noqa: E402
from deli_eplus.core.signup import (  # noqa: E402
    AGREE_BUTTON,
    ATTENDANCE_ENTRY,
    LOGIN_BUTTON,
    LOGOUT_ITEM,
    MINE_TAB,
    PUNCH_BUTTON,
    SETTINGS_ITEM,
    SignupFlow,
)
from deli_eplus.device.base import AndroidDevice  # noqa: E402
from deli_eplus.device.mumu import MuMuDevice  # noqa: E402
from deli_eplus.log import get as get_logger  # noqa: E402

LOGIN_PAGE_WAIT = "login_page_wait"
LOGIN_PAGE_TIMEOUT = 15.0

# (时间戳, 方法名, start/end, selector)
EVENTS: list[tuple[float, str, str, str | None]] = []
PROCESS_START = time.monotonic()


def _record(kind: str, phase: str, selector: str | None) -> None:
    EVENTS.append((time.monotonic(), kind, phase, selector))


def _probe(cls, method: str, kind: str, *, selector_first: bool = True) -> None:
    original = getattr(cls, method)

    def wrapper(self, *args, **kwargs):
        selector = (
            (args[0] if args else kwargs.get("selector")) if selector_first else None
        )
        _record(kind, "start", selector)
        try:
            return original(self, *args, **kwargs)
        finally:
            _record(kind, "end", selector)

    wrapper.__name__ = method
    setattr(cls, method, wrapper)


def _probe_logout_loginpage() -> None:
    """登出流程走完后，等登录页真正渲染出来（wait_gone 在转场时就返回了）。"""
    original = SignupFlow._logout  # noqa: SLF001

    def wrapper(self, device):
        try:
            return original(self, device)
        finally:
            _record(LOGIN_PAGE_WAIT, "start", None)
            try:
                device.find(LOGIN_BUTTON, timeout=LOGIN_PAGE_TIMEOUT, poll=0.2)
            except Exception as e:  # noqa: BLE001
                self._log.warning("登出后未等到登录页: %s", e)
            finally:
                _record(LOGIN_PAGE_WAIT, "end", None)

    wrapper.__name__ = "_logout"
    SignupFlow._logout = wrapper  # noqa: SLF001


def _install_probes() -> None:
    for method in (
        "find",
        "exists",
        "wait_any",
        "wait_gone",
        "click",
        "click_until",
        "type_text",
    ):
        _probe(AndroidDevice, method, method)
    _probe(AndroidDevice, "start_app", "start_app", selector_first=False)
    _probe(MuMuDevice, "start_emulator", "start_emulator", selector_first=False)
    _probe(MuMuDevice, "set_location", "set_location", selector_first=False)
    _probe_logout_loginpage()


def _at(
    kind: str, selector: str | None, phase: str = "start", after: float | None = None
) -> float | None:
    for t, k, p, sel in EVENTS:
        if (
            k == kind
            and sel == selector
            and p == phase
            and (after is None or t >= after)
        ):
            return t
    return None


def _span(kind: str, selector: str | None, after: float | None = None) -> float | None:
    start = _at(kind, selector, "start", after=after)
    end = _at(kind, selector, "end", after=start) if start is not None else None
    return None if start is None or end is None else end - start


def _diff(later: float | None, earlier: float | None) -> float | None:
    return None if later is None or earlier is None else later - earlier


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}s"


def _report(ok: bool, total: float, final_login_visible: bool | None) -> None:
    log = get_logger("timing")
    rows: list[tuple[str, float | None]] = []

    def add(name: str, seconds: float | None) -> None:
        rows.append((name, seconds))

    add("① 启动/连接模拟器", _span("start_emulator", None))
    add("② 打开 App 到前台", _span("start_app", None))

    t_app = _at("start_app", None, "end")
    t_login_click = _at("click_until", LOGIN_BUTTON, "start")
    add("③ 进登录页 + 输入账号密码", _diff(t_login_click, t_app))
    add("④ 点登录 → 出现同意并继续", _span("click_until", LOGIN_BUTTON))
    add("⑤ 注入虚拟定位", _span("set_location", None))
    add("⑥ 点同意 → 出现智能考勤", _span("click_until", AGREE_BUTTON))

    t_attendance = _at("click", ATTENDANCE_ENTRY, "start")
    add("★A 点登录 → 点智能考勤", _diff(t_attendance, t_login_click))

    t_attendance_end = _at("click", ATTENDANCE_ENTRY, "end")
    # 注意：进登录页阶段可能先登出一次（同样是点「我的」），所以这些标记
    # 一律锚定在「点智能考勤之后」，避免取到登录前那次登出。
    t_mine_click = _at("click_until", MINE_TAB, "start", after=t_attendance_end or 0.0)
    add("⑦ 点智能考勤 → 开始登出(含打卡)", _diff(t_mine_click, t_attendance_end))
    add(
        "  ·打卡：点打卡 → 确认弹窗",
        _span("click_until", PUNCH_BUTTON, after=t_attendance_end or 0.0),
    )
    add(
        "⑧ 点我的 → 出现设置项",
        _span("click_until", MINE_TAB, after=t_attendance_end or 0.0),
    )

    t_settings = _at("click", SETTINGS_ITEM, "start", after=t_attendance_end or 0.0)
    t_logout_done = _at("wait_gone", LOGOUT_ITEM, "end")
    add("★B 点设置 → 退出登录项消失", _diff(t_logout_done, t_settings))

    t_login_page = _at(LOGIN_PAGE_WAIT, None, "end", after=t_settings or 0.0)
    add("★B2 点设置 → 登录页真正出现", _diff(t_login_page, t_settings))
    add("  ·登出后等登录页的额外耗时", _span(LOGIN_PAGE_WAIT, None))

    add("合计（run() 全程）", total)

    lines = ["", "=" * 50, "  得力E+ 真机计时报告", "=" * 50]
    for name, seconds in rows:
        lines.append(f"{name:<32} {_fmt(seconds):>10}")
    lines.append("=" * 50)
    lines.append(
        f"流程结果: {'成功' if ok else '失败/中止'}"
        f"   结束时登录页可见: {final_login_visible}"
    )
    text = "\n".join(lines)
    log.info("\n%s", text)
    print(text, flush=True)

    out_dir = PROJECT_ROOT / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report_path = out_dir / f"timing-{stamp}.txt"
    report_path.write_text(text, encoding="utf-8")
    events_path = out_dir / f"timing-{stamp}.json"
    events_path.write_text(
        json.dumps(
            [
                {
                    "t": round(t - PROCESS_START, 3),
                    "method": k,
                    "phase": p,
                    "selector": s,
                }
                for t, k, p, s in EVENTS
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\n明细已写入:\n  {report_path}\n  {events_path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="得力E+ 真机签到计时")
    parser.add_argument(
        "--shutdown", action="store_true", help="结束后关闭由本程序启动的模拟器实例"
    )
    parser.add_argument(
        "--real-punch",
        action="store_true",
        help="实际执行打卡（默认 debug，只走到打卡窗口）",
    )
    args = parser.parse_args()

    config_path = PROJECT_ROOT / "config.json"
    if not config_path.is_file():
        print(f"缺少配置文件: {config_path}", file=sys.stderr)
        return 2
    cfg = Config(config_path)
    if not cfg.users:
        print("config.json 里没有账号", file=sys.stderr)
        return 2

    log = get_logger("timing")
    log.info(
        "计时开始：serial=%s  实例=%s  路径=%s  打卡点=%s  打卡=%s",
        cfg.serial,
        cfg.emulator_num,
        cfg.emulator_path,
        cfg.location,
        "实际" if args.real_punch else "debug(跳过)",
    )

    _install_probes()

    flow = SignupFlow(
        serial=cfg.serial,
        emulator_path=cfg.emulator_path,
        emulator_num=cfg.emulator_num,
        users=cfg.users,
        location=cfg.location,
        debug=not args.real_punch,
        close_emulator_after=False,
        on_account=lambda phone, state, msg: log.info("[账号] %s %s", state, msg),
        on_run=lambda state, msg: log.info("[运行] %s %s", state, msg),
    )

    started = time.monotonic()
    ok = flow.run()
    total = time.monotonic() - started

    final_login_visible: bool | None = None
    if flow.device is not None:
        try:
            final_login_visible = flow.device.exists(LOGIN_BUTTON)
        except Exception as e:  # noqa: BLE001
            log.warning("登录页探测失败: %s", e)

    _report(ok, total, final_login_visible)

    if flow.device is not None and getattr(flow.device, "started_by_us", False):
        if args.shutdown:
            flow.device.shutdown_instance()
        else:
            log.info("模拟器由本程序启动，保留运行中（加 --shutdown 可结束后关闭）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
