"""命令行入口：python -m deli_eplus [--debug]。

GUI 不装依赖也能跑批量签到的无界面方式；进度直接打到控制台。
"""

from __future__ import annotations

import argparse
import sys

from . import VERSION
from .config import Config, mask_phone
from .device import DeviceError
from .log import get as get_logger, setup as setup_log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="deli_eplus",
        description="得力E+ 自动签到（命令行版，与 GUI 共用同一套流程）",
    )
    parser.add_argument("--debug", action="store_true",
                        help="调试签到：走完整流程但不实际打卡")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    setup_log()
    log = get_logger("cli")
    from .core import SignupFlow  # 延迟到日志就绪后再导入

    config = Config()
    if not config.emulator_path:
        log.error("未配置模拟器路径，请先在 GUI 设置页配置（config.json: emulator_path）")
        return 1
    users = config.users
    if not users:
        log.error("没有配置任何账号，请先在 GUI 账号页添加（config.json: users）")
        return 1

    def on_account(phone: str, state: str, message: str) -> None:
        if state == "running":
            log.info("── 账号 %s 开始 ──", mask_phone(phone))
        elif state == "done":
            log.success("── 账号 %s 完成 ──", mask_phone(phone))
        elif state == "failed":
            log.error("── 账号 %s 失败: %s ──", mask_phone(phone), message)

    def on_run(state: str, message: str) -> None:
        if state == "started":
            log.success("本轮签到开始%s，共 %d 个账号",
                        "（调试模式，不实际打卡）" if args.debug else "", len(users))
        elif state == "finished":
            log.success(message or "签到结束")
        elif state == "aborted":
            log.error("签到中止: %s", message or "未知原因")

    flow = SignupFlow(
        serial=config.serial,
        emulator_path=config.emulator_path,
        emulator_num=config.emulator_num,
        users=users,
        location=config.location,
        debug=args.debug,
        on_account=on_account,
        on_run=on_run,
    )
    try:
        ok = flow.run()
    except KeyboardInterrupt:
        log.info("收到 Ctrl+C，已退出")
        return 130
    except DeviceError as e:
        log.error("设备错误: %s", e)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
