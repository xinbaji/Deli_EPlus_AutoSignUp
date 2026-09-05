"""设备层的类型化异常。core/UI 按类型捕获并转成用户可读的提示。"""

from __future__ import annotations

from typing import Optional, Sequence


class DeviceError(RuntimeError):
    """设备/模拟器操作错误基类。"""


class DeviceConnectionError(DeviceError):
    """ADB / uiautomator 连接失败。"""


class AppLaunchError(DeviceError):
    """应用无法启动（未安装等永久性错误，或重试超时）。"""


class LocationError(DeviceError):
    """虚拟定位设置失败。"""


class ElementTimeoutError(DeviceError):
    """在超时时间内没有等到目标元素。

    保存 selector 与期间最后一次底层错误，方便上层报出精确原因。
    """

    def __init__(self, selectors: Sequence[str], timeout: float,
                 last_error: Optional[Exception] = None):
        shown = selectors[0] if len(selectors) == 1 else f"{len(selectors)} 个候选之一"
        message = f"等待元素超时（{timeout:g} 秒）：{shown}"
        if last_error is not None:
            message += f" · 期间底层错误: {last_error!r}"
        super().__init__(message)
        self.selectors = list(selectors)
        self.timeout = timeout
        self.last_error = last_error


class StopRequested(Exception):
    """用户请求停止（由停止令牌触发，业务层应立即退出）。"""
