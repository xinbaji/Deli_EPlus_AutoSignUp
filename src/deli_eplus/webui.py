"""pywebview 图形界面：窗口、JS API 桥、事件推送、签到流程接线。

线程模型：
- webview.start() 阻塞在主线程（GUI 事件循环）；
- js_api 方法由 pywebview 调度到工作线程执行（config 自带锁，安全）；
- SignupFlow 跑在独立线程，进度通过 window.evaluate_js 推给前端；
- 日志活动流由专用线程轮询 log.feed() 批量推送；
- 关窗事件里置停止令牌并等流程线程退出（上限 10 秒）。
"""

from __future__ import annotations

import json
import os
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

import webview

from . import APP_NAME, AUTHOR, REPO_URL, VERSION
from .config import Config, ConfigError
from .core import SignupFlow
from .device import DeviceError
from .device.exceptions import StopRequested
from .log import feed as log_feed
from .log import get as get_logger
from .log import setup as setup_log

CLOSE_TIMEOUT = 10.0
FEED_POLL = 0.15


def web_dir() -> Path:
    """前端资源目录：打包后在 _MEIPASS/deli_eplus/web，开发期在包目录下。"""
    meipass = getattr(__import__("sys"), "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "deli_eplus" / "web"
    return Path(__file__).resolve().parent / "web"


class Api:
    """暴露给前端 JS 的接口（window.pywebview.api.*）。

    约定：所有方法返回 dict，至少含 ok 字段；错误消息面向用户可读。
    window 引用在窗口创建后注入（仅用于文件对话框等 GUI 能力）。
    """

    def __init__(self, config: Config):
        self._cfg = config
        self._window: Optional[webview.Window] = None
        self._log = get_logger("webui")
        self._stop_token = _StopToken()
        self._worker: Optional[threading.Thread] = None
        self._flow: Optional[SignupFlow] = None
        self._running = False
        self._last_feed: list[tuple[str, int]] = []
        self._last_detail = ""

    # ---------- 内部 ----------

    def _push(self, event_type: str, data: dict[str, Any]) -> None:
        payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        try:
            if self._window is not None:
                self._window.evaluate_js(f"window.__pushEvent && window.__pushEvent({payload})")
        except Exception:  # 窗口关闭中，推送失败可忽略
            pass

    def _brief(self) -> dict[str, Any]:
        return {
            "emulator_path": self._cfg.emulator_path,
            "emulator_num": self._cfg.emulator_num,
            "serial": self._cfg.serial,
            "latitude": self._cfg.location.get("latitude", 45.0),
            "longitude": self._cfg.location.get("longitude", 45.0),
            "users": self._cfg.users,
        }

    @staticmethod
    def _err(e: Exception) -> dict[str, Any]:
        return {"ok": False, "error": str(e)}

    # ---------- 初始化 / 配置 ----------

    def get_initial(self) -> dict[str, Any]:
        return {
            "app": {"name": APP_NAME, "version": VERSION,
                    "author": AUTHOR, "repo": REPO_URL},
            "theme": self._cfg.theme,
            "download_source": self._cfg.download_source,
            **self._brief(),
        }

    def get_config_brief(self) -> dict[str, Any]:
        return self._brief()

    def set_theme(self, dark: bool) -> dict[str, Any]:
        self._cfg.set_theme(bool(dark))
        return {"ok": True}

    def save_emulator(self, path: str, num: str, serial: str) -> dict[str, Any]:
        try:
            self._cfg.set_emulator(path or "", num, serial)
            self._cfg.save()
            return {"ok": True}
        except ConfigError as e:
            return self._err(e)

    def save_location(self, lat: str, lon: str) -> dict[str, Any]:
        try:
            self._cfg.set_location(float(lat), float(lon))
            self._cfg.save()
            return {"ok": True}
        except (TypeError, ValueError):
            return self._err(ConfigError("经纬度必须是数字"))
        except ConfigError as e:
            return self._err(e)

    # ---------- 账号 ----------

    def add_account(self, phone: str, password: str) -> dict[str, Any]:
        try:
            self._cfg.add_user(phone, password)
            self._cfg.save()
        except ConfigError as e:
            return self._err(e)
        return {"ok": True, "users": self._cfg.users}

    def update_account(self, old_phone: str, phone: str, password: str) -> dict[str, Any]:
        try:
            if phone != old_phone:
                if phone in self._cfg.users:
                    return self._err(ConfigError("该手机号已存在"))
                self._cfg.remove_user(old_phone)
            self._cfg.add_user(phone, password)
            self._cfg.save()
        except ConfigError as e:
            return self._err(e)
        return {"ok": True, "users": self._cfg.users}

    def remove_account(self, phone: str) -> dict[str, Any]:
        self._cfg.remove_user(phone)
        self._cfg.save()
        return {"ok": True, "users": self._cfg.users}

    # ---------- 导入导出 / 系统 ----------

    def export_config(self) -> dict[str, Any]:
        target = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename="deli_eplus_config.json",
            file_types=("JSON 配置 (*.json)", "所有文件 (*.*)"),
        )
        if not target:
            return {"ok": False, "cancelled": True}
        target = target if isinstance(target, str) else target[0]
        try:
            self._cfg.export_to(target)
        except OSError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": target}

    def import_config(self) -> dict[str, Any]:
        source = self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("JSON 配置 (*.json)", "所有文件 (*.*)"),
        )
        if not source:
            return {"ok": False, "cancelled": True}
        source = source[0] if isinstance(source, (list, tuple)) else source
        try:
            self._cfg.import_from(source)
        except (OSError, ConfigError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "users": self._cfg.users}

    def browse_folder(self) -> str:
        chosen = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if chosen and isinstance(chosen, (list, tuple)):
            return str(chosen[0])
        return ""

    def open_logs(self) -> None:
        from .log import logs_dir

        logs_dir().mkdir(parents=True, exist_ok=True)
        os.startfile(str(logs_dir()))  # noqa: S606

    def open_repo(self) -> None:
        webbrowser.open(REPO_URL)

    # ---------- 自动更新 ----------

    def _update_source(self) -> str:
        return self._cfg.download_source

    def set_update_source(self, source: str) -> dict[str, Any]:
        try:
            self._cfg.set_download_source(source)
        except ConfigError as e:
            return self._err(e)
        return {"ok": True}

    def check_update(self) -> dict[str, Any]:
        """同步检查最新版本（前端按钮点击时调用）。"""
        from . import updater

        try:
            info = updater.latest_release(self._update_source())
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        if info is None:
            return {"ok": True, "status": "latest"}
        newer = updater.is_newer(info["tag"], VERSION)
        return {
            "ok": True,
            "status": "available" if newer else "latest",
            "tag": info["tag"],
            "notes": info["notes"],
        }

    def auto_check_update(self) -> None:
        """启动后台线程检查更新，有新版以事件推给前端。"""

        def work() -> None:
            result = self.check_update()
            if result.get("ok") and result.get("status") == "available":
                self._push("update", {"status": "available", "tag": result["tag"]})

        threading.Thread(target=work, daemon=True, name="update-check").start()

    def download_update(self) -> dict[str, Any]:
        from .config import base_dir

        update_dir = base_dir() / "update"

        def work() -> None:
            from . import updater

            try:
                info = updater.latest_release(self._update_source())
            except RuntimeError as e:
                self._push("update", {"status": "error", "message": str(e)})
                return
            if info is None or not updater.is_newer(info["tag"], VERSION):
                self._push("update", {"status": "latest"})
                return
            dest = update_dir / updater.ASSET_NAME
            self._log.info("下载更新 %s …", info["tag"])
            try:
                updater.download(
                    info["asset_url"], dest,
                    progress=lambda pct: self._push(
                        "update", {"status": "progress", "percent": pct}),
                )
            except Exception as e:
                self._push("update", {"status": "error", "message": f"下载失败：{e}"})
                return
            self._push("update", {"status": "downloaded", "path": str(dest),
                                  "tag": info["tag"]})

        threading.Thread(target=work, daemon=True, name="update-download").start()
        return {"ok": True, "dir": str(update_dir)}

    def apply_update(self) -> dict[str, Any]:
        """写 update.bat 并启动它（等本程序退出后自动解压覆盖并重启）。"""
        import sys as _sys

        from . import updater

        if not getattr(_sys, "frozen", False):
            return {"ok": False, "error": "开发模式不支持应用内更新，请 git pull"}
        app_dir = Path(_sys.executable).resolve().parent
        zip_path = app_dir / "update" / updater.ASSET_NAME
        if not zip_path.is_file():
            return {"ok": False, "error": "更新包不存在，请先下载"}
        updater.apply_update(zip_path, app_dir, Path(_sys.executable).name)
        if self._window is not None:
            self._window.destroy()
        return {"ok": True}

    # ---------- 检测 ----------

    def detect_emulator(self) -> dict[str, Any]:
        if not self._cfg.emulator_path:
            return self._err(ConfigError("请先填写并保存 MuMu 安装目录"))
        from .device import MuMuDevice

        def work() -> None:
            device = MuMuDevice(self._cfg.serial, self._cfg.emulator_path,
                                self._cfg.emulator_num)
            problems = device.check_install()
            if problems:
                self._push("detect", {"target": "emu", "ok": False,
                                      "message": "；".join(problems)})
                return
            ok = device.wait_adb_ready(timeout=8)
            self._push("detect", {
                "target": "emu", "ok": ok,
                "message": "路径正确，ADB 可连接" if ok
                else "路径正确，但模拟器未运行或 ADB 未就绪",
            })

        threading.Thread(target=work, daemon=True, name="detect-emu").start()
        return {"ok": True}

    def test_location(self, lat: str, lon: str) -> dict[str, Any]:
        try:
            latitude, longitude = float(lat), float(lon)
        except (TypeError, ValueError):
            return self._err(ConfigError("经纬度必须是数字"))
        if not self._cfg.emulator_path:
            return self._err(ConfigError("请先配置模拟器路径"))
        from .device import MuMuDevice

        def work() -> None:
            try:
                device = MuMuDevice(self._cfg.serial, self._cfg.emulator_path,
                                    self._cfg.emulator_num)
                device.set_location(latitude, longitude)
                self._push("detect", {"target": "loc", "ok": True,
                                      "message": f"已下发 ({latitude}, {longitude})"})
            except DeviceError as e:
                self._push("detect", {"target": "loc", "ok": False, "message": str(e)})

        threading.Thread(target=work, daemon=True, name="test-loc").start()
        return {"ok": True}

    # ---------- 签到 ----------

    def start_signup(self, debug: bool) -> dict[str, Any]:
        if self._running:
            return {"ok": False, "error": "已有签到正在进行"}
        problems = []
        if not self._cfg.emulator_path:
            problems.append("未配置模拟器路径（设置页）")
        if not self._cfg.users:
            problems.append("还没有账号（账号页）")
        if problems:
            return {"ok": False, "error": "；".join(problems)}

        self._stop_token = _StopToken()
        self._running = True
        debug_flag = bool(debug)

        def on_account(phone: str, state: str, message: str) -> None:
            self._push("account", {"phone": phone, "state": state,
                                   "message": message,
                                   "doneAt": time.strftime("%H:%M:%S") if state == "done" else ""})

        def on_run(state: str, message: str) -> None:
            if state == "started":
                self._push("run", {"state": "started", "debug": debug_flag})
            elif state == "finished":
                self._push("run", {"state": "finished", "message": message,
                                   "has_failure": "失败" in (message or "")})
            elif state == "aborted":
                self._push("run", {"state": "aborted", "message": message,
                                   "detail": self._last_detail})

        def work() -> None:
            try:
                flow = SignupFlow(
                    serial=self._cfg.serial,
                    emulator_path=self._cfg.emulator_path,
                    emulator_num=self._cfg.emulator_num,
                    users=self._cfg.users,
                    location=self._cfg.location,
                    debug=debug_flag,
                    on_account=on_account,
                    on_run=on_run,
                    stop_check=self._stop_token.stopped,
                )
                self._flow = flow
                flow.run()
            finally:
                self._running = False

        self._worker = threading.Thread(target=work, name="signup-flow", daemon=True)
        self._worker.start()
        return {"ok": True}

    def stop_signup(self) -> dict[str, Any]:
        if self._running:
            self._stop_token.stop()
            self._push("run", {"state": "stopping"})
        return {"ok": True}


class _StopToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def stop(self) -> None:
        self._event.set()

    @property
    def stopped(self) -> bool:
        return self._event.is_set()


def run_app() -> int:
    setup_log()
    log = get_logger("webui")
    config = Config()
    api = Api(config)

    window = webview.create_window(
        APP_NAME,
        url=str(web_dir() / "index.html"),
        js_api=api,
        width=1120, height=760,
        min_size=(1000, 680),
        background_color="#f5f5f5",
    )
    api._window = window  # noqa: SLF001

    # 日志活动流轮询线程：批量推给前端
    feed_stop = threading.Event()

    def feed_poller() -> None:
        handler = log_feed()
        while not feed_stop.is_set():
            if handler is not None:
                items = handler.drain()
                if items:
                    api._last_feed.extend(items)  # noqa: SLF001
                    api._last_feed = api._last_feed[-400:]  # noqa: SLF001
                    # 中止时错误卡片需要动态流尾部做技术详情
                    api._last_detail = "\n".join(m for m, _ in api._last_feed[-25:])  # noqa: SLF001
                    api._push("feed", {"items": [
                        {"message": m, "level": lv} for m, lv in items]})
            feed_stop.wait(FEED_POLL)

    def on_closed() -> None:
        feed_stop.set()
        api._stop_token.stop()  # noqa: SLF001
        worker = api._worker  # noqa: SLF001
        if worker is not None and worker.is_alive():
            worker.join(timeout=CLOSE_TIMEOUT)
        # 关闭程序时，顺道关掉由本程序启动的模拟器实例（用户自己开的不动）
        flow = api._flow  # noqa: SLF001
        if flow is not None and flow.device is not None:
            flow.device.shutdown_instance()

    window.events.closed += on_closed
    threading.Thread(target=feed_poller, daemon=True, name="feed-poller").start()
    api.auto_check_update()
    log.info("界面启动（v%s）", VERSION)
    webview.start()
    return 0


_ = StopRequested  # 重导出便于排查（流程内抛出，UI 层不捕获）
