"""得力E+ 签到流程 —— 全项目唯一实现，GUI 与 CLI 共用。

职责：编排设备操作完成「启动模拟器 → 打开 App → 进入登录页 → 逐账号
登录 → 定位 → 打卡 → 登出」，通过两个回调把进度交给调用方渲染：
    on_account(phone, state, message)   state: running / done / failed
    on_run(state, message)              state: started / finished / aborted
所有可能卡住的等待都带超时；停止令牌在每个阶段边界生效。
"""

from __future__ import annotations

import time
from typing import Callable, Mapping, Optional

from ..device import (
    AndroidDevice,
    DeviceError,
    ElementTimeoutError,
    StopRequested,
    create_device,
)
from ..config import mask_phone
from ..log import get as get_logger

Package = "com.delicloud.app.smartoffice"
ResourcePrefix = f"{Package}:id/"

# ---------- 界面元素选择器 ----------
# 文本类控件统一用 resource-id 精确到 TextView，避免误匹配


def _text(text: str) -> str:
    return f"//android.widget.TextView[@text='{text}']"


PHONE_INPUT = f"//android.widget.EditText[@resource-id='{ResourcePrefix}et_phone']"
PASSWORD_INPUT = f"//android.widget.EditText[@resource-id='{ResourcePrefix}et_password']"

SKIP_AD = _text("跳过")            # 启动广告页
MINE_TAB = _text("我的")           # 底部导航
SETTINGS_ITEM = _text("设置")
LOGOUT_ITEM = _text("退出登录")
CONFIRM_BUTTON = _text("确定")      # 各类弹窗的确认
LOGIN_BUTTON = _text("登录")
AGREE_BUTTON = _text("同意并继续")
ATTENDANCE_ENTRY = _text("智能考勤")
IN_RANGE = _text("已在打卡范围内")
NOT_IN_RANGE = _text("不在打卡范围内")
REFRESH_BUTTON = _text("刷新")
PUNCH_BUTTON = _text("打卡")
PUNCH_CONFIRM = "//android.widget.ImageButton"   # 打卡弹出的确认大按钮

# 登录页候选：广告(跳过) / 已登录(我的) / 目标(登录)
LAUNCH_CANDIDATES = (SKIP_AD, MINE_TAB, LOGIN_BUTTON)
# 考勤页候选
RANGE_CANDIDATES = (IN_RANGE, NOT_IN_RANGE)

# MuMu 1080P 分辨率下，设置页向上滑动以露出"退出登录"
SCROLL_UP = (515, 1662, 515, 457, 0.3)
MAX_SWIPE_ATTEMPTS = 4

ENTER_LOGIN_TIMEOUT = 120   # 从打开 App 到见到登录按钮的总时限
PUNCH_TIMEOUT = 90          # 等待"已在打卡范围内"的时限


class SignupFlow:
    """一次完整的批量签到运行。单次使用：创建后调用 run()（应在工作线程中）。"""

    def __init__(
        self,
        *,
        serial: str,
        emulator_path: str,
        emulator_num: str,
        users: Mapping[str, str],
        location: Mapping[str, float],
        debug: bool = False,
        on_account: Optional[Callable[[str, str, str], None]] = None,
        on_run: Optional[Callable[[str, str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
    ):
        self._serial = serial
        self._emulator_path = emulator_path
        self._emulator_num = emulator_num
        self._users = dict(users)
        self._location = dict(location)
        self._debug = debug
        self._on_account = on_account or (lambda *a: None)
        self._on_run = on_run or (lambda *a: None)
        self._stop_check = stop_check or (lambda: False)
        self._log = get_logger("signup")
        self.device = None  # run() 后持有设备对象（供退出时关闭模拟器）

    # ---------- 入口 ----------

    def run(self) -> bool:
        """执行签到。返回 True 表示本轮全部账号处理完毕（含个别失败）。"""
        self._emit_run("started", "调试签到" if self._debug else "")
        try:
            device = create_device(
                self._serial, self._emulator_path, self._emulator_num,
                logger=get_logger("device"),
            )
            device.set_stop_check(self._stop_check)
            self.device = device

            self._prepare_app(device)
            self._enter_login_page(device)

            failed = 0
            for phone, password in self._users.items():
                self._check_stop()
                self._emit_account(phone, "running", "")
                try:
                    self._signup_one(device, phone, password)
                except StopRequested:
                    raise
                except DeviceError as e:
                    self._log.error("账号 %s 签到失败: %s", mask_phone(phone), e)
                    self._emit_account(phone, "failed", str(e))
                    failed += 1
                    continue
                self._log.success("账号 %s 签到完成", mask_phone(phone))
                self._emit_account(phone, "done", "")

            total = len(self._users)
            if failed:
                self._emit_run("finished", f"本轮结束：{total - failed}/{total} 成功，{failed} 失败")
                return False
            self._emit_run("finished", f"本轮结束：{total}/{total} 全部成功")
            return True

        except StopRequested:
            self._log.info("签到已由用户停止")
            self._emit_run("aborted", "已停止")
            return False
        except DeviceError as e:
            self._log.error("签到中止: %s", e)
            self._emit_run("aborted", str(e))
            return False
        except Exception as e:  # 未知错误也不能让线程带着异常消失
            self._log.exception("未预期的错误: %s", e)
            self._emit_run("aborted", f"未预期的错误: {e}")
            return False

    # ---------- 阶段 ----------

    def _prepare_app(self, device: AndroidDevice) -> None:
        self._check_stop()
        self._log.info("启动模拟器（实例 %s）…", self._emulator_num)
        device.start_emulator()
        self._log.info("打开得力E+ …")
        device.start_app(Package)

    def _enter_login_page(self, device: AndroidDevice) -> None:
        """处理启动页：关广告、退出已登录账号，直到出现登录按钮。"""
        deadline = time.monotonic() + ENTER_LOGIN_TIMEOUT
        while True:
            self._check_stop()
            try:
                index, element = device.wait_any(LAUNCH_CANDIDATES, timeout=5, poll=0.5)
            except ElementTimeoutError:
                if time.monotonic() > deadline:
                    raise DeviceError(
                        f"{ENTER_LOGIN_TIMEOUT} 秒内未能进入登录页：请手动确认 App 界面"
                    )
                continue

            if index == 0:            # 启动广告
                element.click()
                self._dismiss_popup(device)
            elif index == 1:          # 已有账号在登录状态，先退出
                self._log.info("检测到已登录账号，正在退出…")
                self._logout(device)
            else:
                self._log.info("已进入登录页")
                return

    def _signup_one(self, device: AndroidDevice, phone: str, password: str) -> None:
        self._check_stop()
        self._log.info("正在登录 %s", mask_phone(phone))
        device.type_text(PHONE_INPUT, phone)
        device.type_text(PASSWORD_INPUT, password)
        # 登录点击可能被切换动画吞掉：以"同意并继续"出现为准，无效就再点
        device.click_until(LOGIN_BUTTON, AGREE_BUTTON, schedule=(2.5, 4.0, 6.0))

        # 登录后、进入主页前设置虚拟定位，确保考勤页面读到正确位置
        device.set_location(
            float(self._location.get("latitude", 45.0)),
            float(self._location.get("longitude", 45.0)),
        )
        device.click_until(AGREE_BUTTON, ATTENDANCE_ENTRY, schedule=(2.0, 3.0))
        self._punch(device)
        self._logout(device)

    def _punch(self, device: AndroidDevice) -> None:
        self._check_stop()
        deadline = time.monotonic() + PUNCH_TIMEOUT
        reclicked = False
        while True:
            self._check_stop()
            try:
                index, _ = device.wait_any(RANGE_CANDIDATES, timeout=2.0, poll=0.4)
            except ElementTimeoutError:
                if time.monotonic() > deadline:
                    raise DeviceError(
                        f"等待打卡窗口超时（{PUNCH_TIMEOUT} 秒）："
                        "请检查模拟器定位经纬度是否为考勤点附近"
                    )
                if not reclicked:
                    # 智能考勤点击可能被切换动画吞掉：补点一次
                    reclicked = True
                    self._log.info("考勤页未加载，补点「智能考勤」")
                    try:
                        device.click(ATTENDANCE_ENTRY, timeout=4)
                    except ElementTimeoutError:
                        pass
                continue
            if index == 0:
                break
            device.click(REFRESH_BUTTON)   # 不在范围内 → 刷新位置

        if self._debug:
            self._log.success("调试模式：已验证到打卡窗口，跳过实际打卡")
            return

        confirm = device.click_until(PUNCH_BUTTON, PUNCH_CONFIRM, schedule=(1.5, 3.0, 5.0))
        confirm.click()
        if not device.wait_gone(PUNCH_CONFIRM, timeout=15):
            raise DeviceError("点击打卡后确认按钮未消失：打卡可能未成功，请人工核对")
        self._log.success("打卡成功")

    def _logout(self, device: AndroidDevice) -> None:
        """退出当前账号。

        实测：App 切换动画期间点击和上滑都可能无效，因此每一步都带验证：
        - 我的 -> 设置：以"设置"出现为准，无效就再点；
        - 露出退出登录：先直接找（多数情况动画结束后直接可见），不行再上滑；
        - 点退出登录：以"确定"弹窗出现为准，没弹就再点。
        """
        self._check_stop()
        # 我的 tab -> 出现「设置」入口（点击被吞则重试）
        device.click_until(MINE_TAB, SETTINGS_ITEM, schedule=(2.5, 4.0))
        # 进入设置页
        device.click(SETTINGS_ITEM, timeout=8)
        self._reveal_logout(device)
        self._tap_logout_confirmed(device)

    def _reveal_logout(self, device: AndroidDevice) -> None:
        """露出「退出登录」：等动画结束（快照对比的动态延时）后直接上滑。"""
        for attempt in range(1, MAX_SWIPE_ATTEMPTS + 1):
            self._check_stop()
            device.wait_ui_stable(timeout=2.5, interval=0.25)
            device.swipe(*SCROLL_UP)
            try:
                device.find(LOGOUT_ITEM, timeout=1.2, poll=0.3)
                self._log.info("第 %d 次上滑后露出「退出登录」", attempt)
                return
            except ElementTimeoutError:
                continue
        raise DeviceError("设置页未找到「退出登录」按钮：请人工确认 App 界面")

    def _tap_logout_confirmed(self, device: AndroidDevice) -> None:
        # 点击可能被吞：以「确定」弹窗出现为准，没弹就再点
        device.click_until(LOGOUT_ITEM, CONFIRM_BUTTON, schedule=(1.5, 2.5, 3.5))
        device.click(CONFIRM_BUTTON, timeout=6)
        if not device.wait_gone(LOGOUT_ITEM, timeout=10):
            raise DeviceError("确认退出后界面未返回：请人工检查 App 状态")
        self._log.info("已退出登录")

    def _dismiss_popup(self, device: AndroidDevice) -> None:
        """尽力关掉"登录失效"等确认弹窗；弹窗不在时静默跳过。"""
        try:
            if device.exists(CONFIRM_BUTTON):
                device.click(CONFIRM_BUTTON)
        except DeviceError as e:
            self._log.debug("关闭弹窗时出错（忽略）: %s", e)

    # ---------- 工具 ----------

    def _check_stop(self) -> None:
        if self._stop_check():
            raise StopRequested()

    def _emit_account(self, phone: str, state: str, message: str) -> None:
        self._on_account(phone, state, message)

    def _emit_run(self, state: str, message: str) -> None:
        self._on_run(state, message)
