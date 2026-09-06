"""本地真机测试夹具：连真实的 MuMu 模拟器。

CI 不收集本目录（pyproject testpaths = ["tests"]），只有本地主动跑：
    script/test_local.bat        # 或 .venv/Scripts/python -m pytest tests_local

- 模拟器路径 / serial 取自仓库根的 config.json，缺配置或未装 MuMu 时跳过；
- 模拟器没在运行会自动拉起（复用生产同款 start_emulator 分阶段启动），
  设 DELI_LOCAL_NO_START=1 可禁止自动启动，未运行时直接跳过；
- 若模拟器是由测试拉起的，结束时自动关闭；用户自己开的不动。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deli_eplus.config import Config  # noqa: E402
from deli_eplus.device.exceptions import DeviceError  # noqa: E402
from deli_eplus.device.mumu import MuMuDevice  # noqa: E402


@pytest.fixture(scope="module")
def config() -> Config:
    path = PROJECT_ROOT / "config.json"
    if not path.is_file():
        pytest.skip("仓库根没有 config.json，请先在 GUI 设置页配置模拟器")
    return Config(path=path)


@pytest.fixture(scope="module")
def device(config) -> MuMuDevice:
    """按 config.json 连接（必要时启动）模拟器，整个模块共用一台。"""
    if sys.platform != "win32":
        pytest.skip("本地真机测试仅支持 Windows")
    dev = MuMuDevice(config.serial, config.emulator_path, config.emulator_num)
    missing = dev.check_install()
    if missing:
        pytest.skip("MuMu 未安装或路径无效：" + "；".join(missing))

    info = dev.get_instance_info()
    running = bool(info and info.get("is_process_started"))
    if not running and os.environ.get("DELI_LOCAL_NO_START"):
        pytest.skip("模拟器未运行，且 DELI_LOCAL_NO_START=1 禁止自动启动")

    try:
        dev.start_emulator()
    except DeviceError as e:
        pytest.fail(f"启动/连接模拟器失败: {e}")

    yield dev
    if dev.started_by_us:
        dev.shutdown_instance()
