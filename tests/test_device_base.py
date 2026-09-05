"""device/base.py 的等待语义测试（注入假 u2 设备，不需要真模拟器）。

重点回归：
- find() 是真等待：出现返回句柄、超时抛 ElementTimeoutError、等待中可被停止；
- 底层瞬态异常被重试而不是直接崩；
- 动作失败可见（绝不静默 pass）。
"""

from __future__ import annotations

import threading

import pytest

from deli_eplus.device.base import AndroidDevice
from deli_eplus.device.exceptions import (
    AppLaunchError,
    DeviceConnectionError,
    ElementTimeoutError,
    StopRequested,
)

SEL_A = "//node[@text='A']"
SEL_B = "//node[@text='B']"


class FakeRawElement:
    def __init__(self, store, selector):
        self._store = store
        self.selector = selector
        self.text = "A"
        self.clicks = 0

    def center(self):
        return (0, 0)

    def click(self):
        self.clicks += 1
        self._store.clicks.append(self.selector)


class FakeSelector:
    def __init__(self, store, xpath):
        self._store = store
        self._xpath = xpath

    @property
    def exists(self):
        if self._store.error:
            raise self._store.error
        return self._xpath in self._store.visible

    def get_last_match(self):
        return FakeRawElement(self._store, self._xpath)


class FakeU2:
    """假的 uiautomator2 Device：visible 集合表示当前屏幕元素。"""

    def __init__(self):
        self.visible: set[str] = set()
        self.error: Exception | None = None
        self.clicks: list[str] = []
        self.cleared = 0
        self.typed: list[str] = []
        self.swipes: list[tuple] = []
        self.started: list[str] = []
        self.app_wait_result = True
        self.app_start_error: Exception | None = None

    def xpath(self, xpath):
        return FakeSelector(self, xpath)

    def clear_text(self):
        self.cleared += 1

    def send_keys(self, text):
        self.typed.append(text)

    def swipe(self, x1, y1, x2, y2, duration=0.2):
        self.swipes.append((x1, y1, x2, y2, duration))

    def app_start(self, package):
        if self.app_start_error:
            raise self.app_start_error
        self.started.append(package)

    def app_wait(self, package, timeout=5, front=False):
        return self.app_wait_result

    def info(self):  # connect() 触碰用
        return {}


@pytest.fixture
def store():
    return FakeU2()


@pytest.fixture
def device(store):
    dev = AndroidDevice("127.0.0.1:16384")
    dev._u2 = store  # 绕过 connect 直接注入
    return dev


# ---------- find / 等待语义 ----------

def test_find_returns_immediately_when_present(device, store):
    store.visible.add(SEL_A)
    element = device.find(SEL_A, timeout=0.5)
    assert element.selector == SEL_A


def test_find_waits_until_element_appears(device, store):
    def appear_later():
        threading.Event().wait(0.15)
        store.visible.add(SEL_A)

    threading.Thread(target=appear_later, daemon=True).start()
    element = device.find(SEL_A, timeout=2, poll=0.05)
    assert element.selector == SEL_A


def test_find_timeout_raises_with_selector_info(device, store):
    with pytest.raises(ElementTimeoutError) as exc:
        device.find(SEL_A, timeout=0.2, poll=0.05)
    assert SEL_A in str(exc.value)


def test_find_retry_through_transient_errors(device, store):
    def recover_later():
        threading.Event().wait(0.15)
        store.error = None
        store.visible.add(SEL_A)

    store.error = RuntimeError("adb offline")
    threading.Thread(target=recover_later, daemon=True).start()
    element = device.find(SEL_A, timeout=2, poll=0.05)
    assert element is not None


def test_find_stop_requested_while_waiting(device, store):
    device.set_stop_check(lambda: True)
    with pytest.raises(StopRequested):
        device.find(SEL_A, timeout=2, poll=0.05)


def test_wait_any_returns_first_candidate(device, store):
    store.visible.update({SEL_B})
    index, element = device.wait_any([SEL_A, SEL_B], timeout=0.5, poll=0.05)
    assert index == 1
    assert element.selector == SEL_B


def test_wait_any_timeout_lists_candidates(device, store):
    with pytest.raises(ElementTimeoutError):
        device.wait_any([SEL_A, SEL_B], timeout=0.2, poll=0.05)


# ---------- 动作 ----------

def test_click_actuates_and_is_visible_in_store(device, store):
    store.visible.add(SEL_A)
    element = device.click(SEL_A, timeout=0.5)
    assert store.clicks == [SEL_A]
    assert element._raw.clicks == 1  # noqa: SLF001


def test_click_missing_element_raises(device, store):
    with pytest.raises(ElementTimeoutError):
        device.click(SEL_A, timeout=0.15)


def test_type_text_clears_then_types(device, store):
    store.visible.add(SEL_A)
    device.type_text(SEL_A, "hello", timeout=0.5)
    assert store.cleared == 1
    assert store.typed == ["hello"]


def test_swipe_passthrough(device, store):
    device.swipe(1, 2, 3, 4, duration=0.1)
    assert store.swipes == [(1, 2, 3, 4, 0.1)]


def test_wait_gone_true_and_false(device, store):
    store.visible.add(SEL_A)
    assert device.wait_gone(SEL_A, timeout=0.1) is False

    def remove_later():
        threading.Event().wait(0.1)
        store.visible.discard(SEL_A)

    threading.Thread(target=remove_later, daemon=True).start()
    assert device.wait_gone(SEL_A, timeout=2, poll=0.05) is True


# ---------- 应用启动 ----------

def test_start_app_success(device, store):
    device.start_app("com.example", timeout=5)
    assert store.started == ["com.example"]


def test_start_app_not_installed_fails_fast(device, store):
    import uiautomator2.exceptions as u2e

    store.app_start_error = u2e.AppNotFoundError("not installed")
    with pytest.raises(AppLaunchError) as exc:
        device.start_app("com.example", timeout=5)
    assert "未安装" in str(exc.value)


def test_start_app_transient_retries_then_timeout(device, store):
    store.app_wait_result = False  # 一直起不来
    with pytest.raises(AppLaunchError) as exc:
        device.start_app("com.example", timeout=0.5)
    assert "超时" in str(exc.value)


# ---------- 连接 ----------

def test_connect_timeout_raises(monkeypatch):
    import deli_eplus.device.base as base_mod

    class BrokenU2:
        def __getattr__(self, name):
            raise RuntimeError("no device")

    dev = AndroidDevice("127.0.0.1:1")
    monkeypatch.setattr(base_mod.time, "sleep", lambda s: None)

    import uiautomator2 as u2

    def broken_connect(serial=None):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(u2, "connect", broken_connect)
    with pytest.raises(DeviceConnectionError):
        dev.connect(timeout=0.1)


def test_not_connected_raises_clean_error():
    dev = AndroidDevice("127.0.0.1:16384")
    with pytest.raises(DeviceConnectionError):
        dev.find(SEL_A, timeout=0.1)
