"""本地真机冒烟测试：覆盖 CI 上测不了的部分。

CI 测试全部打桩；本文件走真机真路径——MuMuManager 启动实例、ADB/uiautomator2
连接、真实 UI dump、真实 App 启动，正对应历次"冷启动连不上/连上卡死"类问题。

不包含真实账号签到（有实际打卡副作用，需要时在 GUI/CLI 里跑 --debug 观察）。

前置：MuMu 已安装并在 config.json 配好；未运行会自动拉起（冷启动约 1-3 分钟）。
运行：script/test_local.bat，或 .venv/Scripts/python -m pytest tests_local -v
"""

from __future__ import annotations

from deli_eplus.core.signup import Package


def test_mumu_install_ok(device):
    """模拟器路径检测通过（目录里有 MuMuNxMain.exe）。"""
    assert device.check_install() == []


def test_adb_connected(device):
    """ADB/uiautomator2 已连上且服务可用（u2.connect + info 探活全过）。"""
    assert device.connected
    _ = device._require_connected().info  # 再探一次，确认 atx-agent 正常应答


def test_ui_dump(device):
    """能 dump 出界面层级（中文环境也能正常解码）。"""
    xml = device._require_connected().dump_hierarchy()
    assert "<hierarchy" in xml


def test_deli_app_installed(device):
    """得力 E+ 已安装在模拟器里。"""
    u2 = device._require_connected()
    assert Package in u2.app_list()


def test_app_can_launch(device):
    """应用能拉起到前台（生产 start_app 的重试路径真实可用）。"""
    device.start_app(Package, timeout=60)
    current = device._require_connected().app_current()
    # uiautomator2 3.x 的 app_current() 返回 dict
    package = current["package"] if isinstance(current, dict) else current.package
    assert package == Package
