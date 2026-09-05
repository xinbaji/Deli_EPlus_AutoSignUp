"""设备层对外接口：类型化异常 + 通用设备 + MuMu 实现 + 工厂。"""

from __future__ import annotations

from .base import AndroidDevice, Element
from .exceptions import (
    AppLaunchError,
    DeviceConnectionError,
    DeviceError,
    ElementTimeoutError,
    LocationError,
    StopRequested,
)
from .mumu import MuMuDevice


def create_device(
    serial: str, emulator_path: str, instance: str, *, logger=None
) -> AndroidDevice:
    """按配置创建设备对象；目前只支持 MuMu。"""
    if "mumu" not in emulator_path.lower():
        raise DeviceError(
            f"暂只支持 MuMu 模拟器，当前配置的路径不是 MuMu 目录：{emulator_path or '<未配置>'}"
        )
    return MuMuDevice(serial, emulator_path, instance or "0", logger=logger)


__all__ = [
    "AndroidDevice",
    "Element",
    "MuMuDevice",
    "create_device",
    "AppLaunchError",
    "DeviceConnectionError",
    "DeviceError",
    "ElementTimeoutError",
    "LocationError",
    "StopRequested",
]
