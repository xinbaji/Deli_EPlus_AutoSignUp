"""通用 Android 设备操作层（基于 uiautomator2）。

设计要点：
- 本模块只依赖 uiautomator2，不依赖任何业务/UI 代码，可整体复用到其他项目；
- uiautomator2 是重量级导入（连带 lxml/PIL/requests），因此放在 connect() 内延迟导入，
  保证 GUI 打开时不为它付出启动时间；
- find() 是"真等待"：出现即返回元素句柄，超时抛 ElementTimeoutError；
  句柄上的动作（点击/输入）作用于已命中的控件，不再重新 dump 界面层级；
- 所有轮询都先检查停止令牌，用户点"停止"最多一个 poll 周期内生效。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional, Sequence

from .exceptions import (
    AppLaunchError,
    DeviceConnectionError,
    DeviceError,
    ElementTimeoutError,
    StopRequested,
)

Selector = str
StopCheck = Callable[[], bool]


class Element:
    """已命中的具体控件。动作直接作用于底层节点，不触发新的界面 dump。"""

    def __init__(self, raw, selector: str, device):
        self._raw = raw            # uiautomator2 DeviceXMLElement
        self._device = device      # uiautomator2 Device
        self.selector = selector

    @property
    def text(self) -> str:
        return self._raw.text or ""

    @property
    def center(self) -> tuple[int, int]:
        return self._raw.center()

    def click(self) -> None:
        self._raw.click()

    def clear_and_type(self, text: str) -> None:
        """聚焦输入框，清空原内容后输入。失败会抛错，绝不静默。"""
        self._raw.click()              # 聚焦
        self._device.clear_text()      # 清空当前聚焦的输入框
        self._device.send_keys(text)


class AndroidDevice:
    """一台 adb 设备（模拟器或真机）的操作封装。"""

    def __init__(self, serial: str, *, logger: Optional[logging.Logger] = None):
        self.serial = serial
        self._log = logger or logging.getLogger("deli_eplus.device")
        self._u2 = None                     # 延迟创建的 uiautomator2 Device
        self._stop_check: Optional[StopCheck] = None

    # ---------- 停止令牌 ----------

    def set_stop_check(self, check: Optional[StopCheck]) -> None:
        self._stop_check = check

    def _check_stop(self) -> None:
        if self._stop_check is not None and self._stop_check():
            raise StopRequested()

    # ---------- 连接 ----------

    @property
    def connected(self) -> bool:
        return self._u2 is not None

    def _bounded(self, fn: Callable[[], Any], timeout: float):
        """在独立线程跑 fn 并硬限时；adb 偶发卡死也不会拖住轮询。

        返回 ("ok", 值) / ("timeout", None) / ("error", 异常)。
        卡死的探测线程无法终止（daemon 线程随进程退出），但轮询不等它。
        """
        result: dict[str, Any] = {}

        def run() -> None:
            try:
                result["value"] = fn()
            except Exception as e:  # noqa: BLE001
                result["error"] = e

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            return "timeout", None
        if "error" in result:
            return "error", result["error"]
        return "ok", result.get("value")

    def connect(self, timeout: float = 40) -> "AndroidDevice":
        """连接全部交给 u2.connect（后续命令都基于 u2），看门狗限时循环重试。

        经验值：模拟器启动后 30 秒内应完成连接，超时即视为卡死，
        尽早报错而不是无限等待。
        """
        deadline = time.monotonic() + timeout
        started = time.monotonic()
        while True:
            self._check_stop()
            state, value = self._bounded(self._u2_connect, timeout=15)
            if state == "ok":
                self._u2 = value
                self._log.info("ADB 已连接 %s（%.1f 秒）",
                               self.serial, time.monotonic() - started)
                return self
            reason = "探测超时" if state == "timeout" else f"未就绪（{value}）"
            self._log.info("等待 ADB/uiautomator（%s），u2 connect 重试…", reason)
            if time.monotonic() >= deadline:
                raise DeviceConnectionError(
                    f"连接设备 {self.serial} 超时（{timeout:g} 秒）："
                    f"请确认模拟器已运行且完成启动 · 最后状态: {reason}"
                )
            time.sleep(1)

    def _u2_connect(self):
        import uiautomator2 as u2

        device = u2.connect(self.serial)
        device.info  # 触碰一次，确认 uiautomator 服务可用
        return device

    def _require_connected(self):
        if self._u2 is None:
            raise DeviceConnectionError("设备尚未连接，请先调用 connect()")
        return self._u2

    # ---------- 应用 ----------

    def start_app(self, package: str, timeout: float = 30) -> None:
        """启动应用并确认到达前台；未安装等永久性错误立即失败，瞬态错误重试。"""
        device = self._require_connected()
        from uiautomator2.exceptions import AppNotFoundError

        deadline = time.monotonic() + timeout
        last_error: object = "尚未尝试"
        attempt = 0
        while True:
            self._check_stop()
            attempt += 1
            try:
                self._log.debug("第 %d 次尝试启动应用: %s", attempt, package)
                device.app_start(package)
                if device.app_wait(package, timeout=5, front=True):
                    self._log.info("应用已启动: %s（第 %d 次尝试）", package, attempt)
                    return
                last_error = "启动命令已执行但应用未到前台"
                self._log.debug("应用未到前台: %s", package)
            except AppNotFoundError as e:
                raise AppLaunchError(f"应用未安装: {package}") from e
            except Exception as e:
                last_error = e
            if time.monotonic() >= deadline:
                raise AppLaunchError(
                    f"启动应用超时（{timeout:g} 秒）: {package} · 最后错误: {last_error}"
                )
            time.sleep(2)

    # ---------- 元素等待 ----------

    def _wait_for(
        self, selectors: Sequence[Selector], timeout: float, poll: float
    ) -> tuple[int, Element]:
        """轮询等待任一 selector 出现；返回 (下标, 元素)。

        每轮每 selector 各 dump 一次界面层级；底层异常（设备瞬断等）
        记录后继续重试，直到超时并把最后错误带出。
        """
        device = self._require_connected()
        deadline = time.monotonic() + timeout
        selectors = list(selectors)
        last_error: Optional[Exception] = None
        while True:
            self._check_stop()
            try:
                for index, selector in enumerate(selectors):
                    sel = device.xpath(selector)
                    if sel.exists:  # 一次 dump
                        waited = time.monotonic() - (deadline - timeout)
                        self._log.debug("元素已出现: %s（等待 %.1fs）",
                                        selector, waited)
                        return index, Element(sel.get_last_match(), selector, device)
            except Exception as e:
                last_error = e
                self._log.debug("查询界面失败，稍后重试: %r", e)
            if time.monotonic() >= deadline:
                raise ElementTimeoutError(selectors, timeout, last_error)
            time.sleep(poll)

    def find(self, selector: Selector, timeout: float = 15, poll: float = 0.5) -> Element:
        """阻塞等待元素出现；超时抛 ElementTimeoutError。"""
        return self._wait_for([selector], timeout=timeout, poll=poll)[1]

    def wait_any(
        self, selectors: Sequence[Selector], timeout: float = 20, poll: float = 0.5
    ) -> tuple[int, Element]:
        """等待多个候选元素中最先出现的一个。"""
        return self._wait_for(selectors, timeout=timeout, poll=poll)

    def exists(self, selector: Selector) -> bool:
        """即时检查元素是否在当前界面上（一次 dump，不等待）。"""
        device = self._require_connected()
        try:
            return bool(device.xpath(selector).exists)
        except Exception as e:
            raise DeviceConnectionError(f"查询界面失败: {e!r}") from e

    def wait_gone(self, selector: Selector, timeout: float = 15, poll: float = 0.5) -> bool:
        """等待元素从界面消失；超时返回 False（调用方决定如何处置）。"""
        device = self._require_connected()
        deadline = time.monotonic() + timeout
        while True:
            self._check_stop()
            try:
                if not device.xpath(selector).exists:
                    return True
            except Exception as e:
                self._log.debug("查询界面失败，稍后重试: %r", e)
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll)

    # ---------- 动作 ----------

    def click(self, selector: Selector, timeout: float = 15) -> Element:
        element = self.find(selector, timeout=timeout)
        element.click()
        self._log.debug("点击: %s", selector)
        return element

    def click_until(self, selector: Selector, until_selector: Selector, *,
                    schedule: tuple[float, ...] = (2.0, 3.0, 4.0)) -> Element:
        """点击 selector 并等待 until_selector 出现；未出现再点一遍。

        每轮 = 点击一次 -> 在预算内轮询 until：
        - until 出现：立即返回（预算只是上限，成功路径不等待）
        - 预算耗尽：进入下一轮（重新 find 源并点击）
        页面切换动画期间点击可能被静默丢弃，靠多轮覆盖。
        """
        last_error: Optional[Exception] = None
        for wait in schedule:
            try:
                element = self.find(selector, timeout=6)
            except ElementTimeoutError as e:
                last_error = e
                continue
            element.click()
            self._log.debug("点击: %s", selector)
            sub_end = time.monotonic() + wait
            while True:
                self._check_stop()
                try:
                    if self.exists(until_selector):
                        return self.find(until_selector, timeout=1)
                except Exception as e:  # dump 瞬断
                    last_error = e
                if time.monotonic() >= sub_end:
                    break
                time.sleep(0.3)
            last_error = ElementTimeoutError([until_selector], wait)
        raise DeviceError(
            f"点击 {selector} 后 {sum(schedule):g} 秒内未出现 {until_selector}"
        ) from last_error

    def wait_ui_stable(self, timeout: float = 3.0, interval: float = 0.25) -> None:
        """等待界面渲染稳定：连续两次 UI 层级快照一致即认为动画结束。

        用于滑动/点击前的动态延时——动画中操作会被丢弃，而动画时长
        不固定，用快照对比代替固定 sleep。超时也返回（后续操作自带验证）。
        """
        device = self._require_connected()
        deadline = time.monotonic() + timeout
        last: Optional[str] = None
        while True:
            self._check_stop()
            try:
                current = device.dump_hierarchy()
            except Exception as e:
                self._log.debug("dump 层级失败（视为不稳定）: %r", e)
                current = None
            if current and last is not None and current == last:
                return
            last = current if current else last
            if time.monotonic() >= deadline:
                return
            time.sleep(interval)

    def type_text(self, selector: Selector, text: str, timeout: float = 15) -> None:
        element = self.find(selector, timeout=timeout)
        element.clear_and_type(text)
        self._log.debug("输入文本: %s -> %s（%d 字符）", selector, text, len(text))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.2) -> None:
        device = self._require_connected()
        device.swipe(x1, y1, x2, y2, duration=duration)

    # ---------- 虚拟定位（仅支持 MuMu 的模拟器实现，见 mumu.py） ----------

    def set_location(self, latitude: float, longitude: float) -> None:
        raise DeviceError("当前设备类型不支持设置虚拟定位")
