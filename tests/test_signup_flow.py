"""SignupFlow 流程测试：ScriptedDevice 剧本机模拟 App 界面变迁。

打桩点只有 create_device（返回剧本设备），_prepare_app/_enter_login_page
都走真实实现，保证阶段编排本身被完整覆盖。

覆盖：完整流程阶段顺序、debugmode 跳过打卡、不在范围时刷新、打卡超时、
账号失败不中断后续账号、停止令牌即时生效、启动页处理、进度回调。
"""

from __future__ import annotations

import pytest

import deli_eplus.core.signup as signup
from deli_eplus.core.signup import (
    AGREE_BUTTON,
    ATTENDANCE_ENTRY,
    CONFIRM_BUTTON,
    IN_RANGE,
    LOGIN_BUTTON,
    LOGOUT_ITEM,
    MINE_TAB,
    NOT_IN_RANGE,
    Package,
    PUNCH_BUTTON,
    PUNCH_CONFIRM,
    PASSWORD_INPUT,
    PHONE_INPUT,
    REFRESH_BUTTON,
    SETTINGS_ITEM,
    SKIP_AD,
    SignupFlow,
)
from deli_eplus.device.exceptions import DeviceError, ElementTimeoutError

LOGIN_PAGE = {PHONE_INPUT, PASSWORD_INPUT, LOGIN_BUTTON}


class ScriptedDevice:
    """按剧本响应操作的假设备：screen 是当前可见元素集合。

    假设备默认超时很短（0.5s），让"元素不在"类失败快速暴露。
    """

    DEFAULT_TIMEOUT = 0.5

    def __init__(self, screen: set[str], transitions: dict | None = None):
        self.screen = set(screen)
        self.transitions = transitions or {}
        self.calls: list[tuple] = []
        self._stop = False

    def set_stop_check(self, check):
        self._check = check

    def start_emulator(self, timeout=180):
        self.calls.append(("start_emulator",))

    def start_app(self, package, timeout=60):
        self.calls.append(("start_app", package))

    def set_location(self, latitude, longitude, timeout=15):
        self.calls.append(("location", latitude, longitude))

    def wait_any(self, selectors, timeout=20, poll=0.5):
        for index, selector in enumerate(selectors):
            if selector in self.screen:
                return index, _ScriptedElement(self, selector)
        raise ElementTimeoutError(list(selectors), timeout)

    def find(self, selector, timeout=DEFAULT_TIMEOUT, poll=0.05):
        if selector not in self.screen:
            raise ElementTimeoutError([selector], timeout)
        return _ScriptedElement(self, selector)

    def click(self, selector, timeout=DEFAULT_TIMEOUT):
        element = self.find(selector, timeout=timeout)
        element.click()
        return element

    def click_until(self, selector, until_selector, schedule=(2.0, 3.0, 4.0)):
        last = None
        for wait in schedule:
            self.click(selector, timeout=6)
            try:
                return self.find(until_selector, timeout=wait)
            except ElementTimeoutError as e:
                last = e
        raise DeviceError(
            f"点击 {selector} 后未出现 {until_selector}（重试 {len(schedule)} 次无效）") from last

    def wait_ui_stable(self, timeout=3.0, interval=0.25):
        return None

    def type_text(self, selector, text, timeout=DEFAULT_TIMEOUT):
        if selector not in self.screen:
            raise ElementTimeoutError([selector], timeout)
        self.calls.append(("type", selector, text))

    def exists(self, selector):
        return selector in self.screen

    def wait_gone(self, selector, timeout=15, poll=0.05):
        return selector not in self.screen

    def swipe(self, *args, **kwargs):
        self.calls.append(("swipe",))
        self._apply(("swipe",))

    def _tap(self, selector):
        self.calls.append(("click", selector))
        self._apply(("click", selector))

    def _apply(self, key):
        handler = self.transitions.get(key)
        if handler:
            handler(self)


class _ScriptedElement:
    def __init__(self, device, selector):
        self._device = device
        self.selector = selector

    def click(self):
        self._device._tap(self.selector)


def goto(*elements):
    """界面变迁：清空当前屏幕后放置新元素集合。"""

    def apply(device: ScriptedDevice) -> None:
        device.screen.clear()
        device.screen.update(elements)

    return apply


def punch_transitions():
    """登录页 → 登录 → 定位 → 同意 → 考勤(已在范围) → 打卡 → 登出 → 登录页。"""
    return {
        ("click", LOGIN_BUTTON): goto(AGREE_BUTTON),
        ("click", AGREE_BUTTON): goto(ATTENDANCE_ENTRY),
        ("click", ATTENDANCE_ENTRY): goto(IN_RANGE, PUNCH_BUTTON, MINE_TAB),
        ("click", PUNCH_BUTTON): lambda d: d.screen.add(PUNCH_CONFIRM),
        ("click", PUNCH_CONFIRM): goto(MINE_TAB),  # 确认后按钮消失，回到主页
        ("click", MINE_TAB): goto(SETTINGS_ITEM),
        ("swipe",): lambda d: d.screen.add(LOGOUT_ITEM),
        ("click", LOGOUT_ITEM): goto(CONFIRM_BUTTON),
        ("click", CONFIRM_BUTTON): goto(*LOGIN_PAGE),
    }


def make_flow(monkeypatch, screen, transitions, *, users=None, debug=False,
              stop=None, run_events=None, patch_punch_timeout=False):
    if patch_punch_timeout:
        monkeypatch.setattr(signup, "PUNCH_TIMEOUT", 0.3)
    device = ScriptedDevice(screen, transitions)
    account_events: list[tuple] = []
    run_events = run_events if run_events is not None else []
    monkeypatch.setattr(signup, "create_device", lambda *a, **k: device)
    flow = SignupFlow(
        serial="s", emulator_path="C:/MuMu", emulator_num="0",
        users=users or {"13800001111": "pw"},
        location={"latitude": 31.2, "longitude": 121.4},
        debug=debug,
        on_account=lambda p, s, m: account_events.append((p, s, m)),
        on_run=lambda s, m: run_events.append((s, m)),
        stop_check=(stop or (lambda: False)),
    )
    return device, flow, account_events, run_events


def test_full_flow_order_and_events(monkeypatch):
    device, flow, account_events, run_events = make_flow(
        monkeypatch, set(LOGIN_PAGE), punch_transitions()
    )
    ok = flow.run()

    assert ok is True
    calls = device.calls
    assert ("start_emulator",) in calls
    assert ("start_app", Package) in calls
    assert ("type", PHONE_INPUT, "13800001111") in calls
    assert ("type", PASSWORD_INPUT, "pw") in calls
    assert ("location", 31.2, 121.4) in calls
    # 阶段顺序：登录 → 定位 → 打卡确认 → 退出登录
    login_index = calls.index(("type", PHONE_INPUT, "13800001111"))
    location_index = calls.index(("location", 31.2, 121.4))
    punch_index = calls.index(("click", PUNCH_CONFIRM))
    logout_index = calls.index(("click", LOGOUT_ITEM))
    assert login_index < location_index < punch_index < logout_index
    assert account_events[-1][1] == "done"
    assert run_events[-1][0] == "finished"
    assert "1/1" in run_events[-1][1]


def test_debug_mode_skips_actual_punch(monkeypatch):
    device, flow, _, _ = make_flow(
        monkeypatch, set(LOGIN_PAGE), punch_transitions(), debug=True
    )
    ok = flow.run()

    assert ok is True
    assert ("click", PUNCH_BUTTON) not in device.calls
    assert ("click", PUNCH_CONFIRM) not in device.calls
    # 但登录、定位、登出等步骤都完整走了一遍
    assert ("click", LOGIN_BUTTON) in device.calls
    assert ("location", 31.2, 121.4) in device.calls
    assert ("click", LOGOUT_ITEM) in device.calls


def test_out_of_range_refreshes_until_in_range(monkeypatch):
    transitions = punch_transitions()
    # 改为：进入考勤页时"不在打卡范围内"，刷新两次后才进入范围
    transitions[("click", ATTENDANCE_ENTRY)] = goto(
        NOT_IN_RANGE, REFRESH_BUTTON, MINE_TAB)

    device = ScriptedDevice(set(LOGIN_PAGE), transitions)
    state = {"refreshes": 0}
    old_apply = device._apply

    def apply(key):
        old_apply(key)
        if key == ("click", REFRESH_BUTTON):
            state["refreshes"] += 1
            if state["refreshes"] >= 2:
                device.screen.discard(NOT_IN_RANGE)
                device.screen.add(IN_RANGE)
                device.screen.add(PUNCH_BUTTON)

    device._apply = apply
    flow = SignupFlow(
        serial="s", emulator_path="C:/MuMu", emulator_num="0",
        users={"13800001111": "pw"}, location={"latitude": 45, "longitude": 45},
        on_account=lambda *a: None, on_run=lambda *a: None,
    )
    monkeypatch.setattr(signup, "create_device", lambda *a, **k: device)

    assert flow.run() is True
    assert state["refreshes"] >= 2


def test_punch_window_timeout_marks_account_failed(monkeypatch):
    monkeypatch.setattr(signup, "PUNCH_TIMEOUT", 0.3)
    # 考勤页既无"已在范围"也无"不在范围"：等待超时
    transitions = {
        ("click", LOGIN_BUTTON): goto(AGREE_BUTTON),
        ("click", AGREE_BUTTON): goto(ATTENDANCE_ENTRY),
    }
    run_events: list[tuple] = []
    _, flow, account_events, run_events = make_flow(
        monkeypatch, set(LOGIN_PAGE), transitions,
        run_events=run_events, patch_punch_timeout=False,
    )
    ok = flow.run()

    assert ok is False
    assert account_events[-1][1] == "failed"
    # 账号级失败不中止流程：以 finished 结束
    assert run_events[-1][0] == "finished"


def test_account_failure_continues_to_next_account(monkeypatch):
    monkeypatch.setattr(signup, "PUNCH_TIMEOUT", 0.3)
    transitions = {
        ("click", LOGIN_BUTTON): goto(AGREE_BUTTON),
        ("click", AGREE_BUTTON): goto(ATTENDANCE_ENTRY),
    }
    users = {"13800001111": "pw", "13800002222": "pw"}
    _, flow, account_events, _ = make_flow(
        monkeypatch, set(LOGIN_PAGE), transitions, users=users,
        patch_punch_timeout=False,
    )
    ok = flow.run()

    assert ok is False
    states = {p: s for p, s, _ in account_events}
    assert states["13800001111"] == "failed"
    assert "13800002222" in states  # 第二个账号仍被尝试


def test_stop_token_aborts_flow(monkeypatch):
    device, flow, _, run_events = make_flow(
        monkeypatch, set(LOGIN_PAGE), punch_transitions(), stop=lambda: True
    )
    ok = flow.run()

    assert ok is False
    assert run_events[-1][0] == "aborted"


def test_enter_login_page_handles_ad_and_logout():
    """广告页 → 跳过 → 已登录 → 退出 → 登录页。"""
    transitions = {
        ("click", SKIP_AD): goto(MINE_TAB),
        ("click", MINE_TAB): goto(SETTINGS_ITEM),
        ("swipe",): lambda d: d.screen.add(LOGOUT_ITEM),
        ("click", LOGOUT_ITEM): goto(CONFIRM_BUTTON),
        ("click", CONFIRM_BUTTON): goto(LOGIN_BUTTON),
    }
    device = ScriptedDevice({SKIP_AD}, transitions)
    flow = SignupFlow(
        serial="s", emulator_path="C:/MuMu", emulator_num="0",
        users={}, location={"latitude": 45, "longitude": 45},
        on_account=lambda *a: None, on_run=lambda *a: None,
    )
    flow._enter_login_page(device)

    assert ("click", SKIP_AD) in device.calls
    assert ("click", LOGOUT_ITEM) in device.calls
    assert LOGIN_BUTTON in device.screen


def test_enter_login_page_timeout(monkeypatch):
    monkeypatch.setattr(signup, "ENTER_LOGIN_TIMEOUT", 0.4)
    device = ScriptedDevice(set())  # 黑屏：什么都等不到
    flow = SignupFlow(
        serial="s", emulator_path="C:/MuMu", emulator_num="0",
        users={}, location={"latitude": 45, "longitude": 45},
        on_account=lambda *a: None, on_run=lambda *a: None,
    )
    with pytest.raises(DeviceError) as exc:
        flow._enter_login_page(device)
    assert "登录页" in str(exc.value)


def test_logout_click_lost_then_retry(monkeypatch):
    """加固：点「退出登录」没弹确定 → 再点一遍，第二次生效。"""
    transitions = punch_transitions()
    counter = {"n": 0}

    def flaky_logout(d):
        counter["n"] += 1
        if counter["n"] >= 2:  # 第一次点击被吞，第二次才弹确定
            d.screen.clear()
            d.screen.update({CONFIRM_BUTTON})

    transitions[("click", LOGOUT_ITEM)] = flaky_logout
    device = ScriptedDevice(set(LOGIN_PAGE), transitions)
    flow = SignupFlow(
        serial="s", emulator_path="C:/MuMu", emulator_num="0",
        users={"13800001111": "pw"}, location={"latitude": 45, "longitude": 45},
        debug=True, on_account=lambda *a: None, on_run=lambda *a: None,
    )
    monkeypatch.setattr(signup, "create_device", lambda *a, **k: device)

    assert flow.run() is True
    logout_clicks = [c for c in device.calls if c == ("click", LOGOUT_ITEM)]
    assert len(logout_clicks) >= 2  # 确实重试了
    assert ("click", CONFIRM_BUTTON) in device.calls


def test_login_click_lost_then_retry(monkeypatch):
    """加固：登录点击被动画吞掉 → 以「同意并继续」出现为准重试。"""
    transitions = punch_transitions()
    counter = {"n": 0}

    def flaky_login(d):
        counter["n"] += 1
        if counter["n"] >= 2:
            d.screen.clear()
            d.screen.update({AGREE_BUTTON})

    transitions[("click", LOGIN_BUTTON)] = flaky_login
    device = ScriptedDevice(set(LOGIN_PAGE), transitions)
    flow = SignupFlow(
        serial="s", emulator_path="C:/MuMu", emulator_num="0",
        users={"13800001111": "pw"}, location={"latitude": 45, "longitude": 45},
        debug=True, on_account=lambda *a: None, on_run=lambda *a: None,
    )
    monkeypatch.setattr(signup, "create_device", lambda *a, **k: device)

    assert flow.run() is True
    login_clicks = [c for c in device.calls if c == ("click", LOGIN_BUTTON)]
    assert len(login_clicks) >= 2
