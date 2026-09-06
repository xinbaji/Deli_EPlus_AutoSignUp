"""开机自启：Windows 注册表 HKCU Run 键（无需管理员权限）。

仅打包版支持（源码模式注册表命令行不可靠，返回运行时错误）。
"""

from __future__ import annotations

import sys

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DeliEPlus_AutoSignUp"


class AutostartError(RuntimeError):
    pass


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    raise AutostartError("开发模式不支持设置开机自启（请使用打包版）")


def is_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    import winreg

    if enabled:
        command = _command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
