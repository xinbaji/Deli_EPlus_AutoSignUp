"""MuMu 模拟器专属能力：启动模拟器进程、设置虚拟定位（MuMuManager）。

通用的 adb/uiautomator 操作全部继承自 AndroidDevice，本类只补 MuMu 专属部分，
因此换其他模拟器（雷电、夜神…）时只需要照着写一个对应子类。
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Optional
from pathlib import Path

from .base import AndroidDevice
from .exceptions import DeviceError, LocationError

MANAGER_NAME = "MuMuManager.exe"
MAIN_NAME = "MuMuNxMain.exe"


class MuMuDevice(AndroidDevice):
    def __init__(
        self,
        serial: str,
        emulator_path: str | Path,
        instance: str = "0",
        *,
        logger=None,
    ):
        super().__init__(serial, logger=logger)
        self.emulator_path = Path(emulator_path)
        self.instance = str(instance)
        self.manager_exe = self.emulator_path / MANAGER_NAME
        self.emulator_exe = self.emulator_path / MAIN_NAME
        self.started_by_us = False   # 模拟器是否由本程序拉起（决定退出时是否关闭它）

    # ---------- 模拟器进程 ----------


    def _manager(self, args: list[str], timeout: float = 30) -> str:
        """执行 MuMuManager 子命令，返回合并输出（GBK 解码）。"""
        result = subprocess.run(
            [str(self.manager_exe), *args],
            capture_output=True, timeout=timeout,
        )
        stdout = (result.stdout or b"").decode("gbk", errors="ignore")
        stderr = (result.stderr or b"").decode("gbk", errors="ignore")
        return stdout + stderr

    def get_instance_info(self) -> Optional[dict]:
        """官方 `info -v <index>`：实例信息 JSON（含 is_android_started 等）。"""
        return self._parse_json_object(
            self._manager(["info", "-v", self.instance]))

    def launch_instance(self) -> None:
        """官方 `control -v <index> launch`：启动实例（已在运行时安全）。"""
        self._manager(["control", "-v", self.instance, "launch"], timeout=60)

    def start_emulator(self, timeout: float = 240) -> None:
        """启动 MuMu 实例并动态等待安卓完全就绪（官方 info 字段驱动）。

        等待链：control launch（重复调用安全）→ info.is_android_started
        → ADB/uiautomator 连接。每一步都有进度日志，无固定 sleep。
        """
        self._check_stop()
        for exe in (self.emulator_exe, self.manager_exe):
            if not exe.is_file():
                raise DeviceError(
                    f"未找到 {exe.name}，请检查设置中的模拟器路径：{self.emulator_path}"
                )
        started_at = time.monotonic()
        info = self.get_instance_info() or {}
        self.started_by_us = not info.get("is_process_started", False)

        self._log.info("启动模拟器（官方 control launch，实例 %s）…", self.instance)
        self.launch_instance()

        # 动态等待安卓启动完成（官方字段 is_android_started）
        deadline = started_at + timeout
        while True:
            self._check_stop()
            info = self.get_instance_info()
            if info and info.get("is_android_started"):
                self._log.info("模拟器安卓已启动（%.1f 秒）",
                               time.monotonic() - started_at)
                break
            if time.monotonic() >= deadline:
                raise DeviceError(
                    f"模拟器 {timeout:g} 秒内未完成安卓启动：请确认 MuMu 能正常打开"
                )
            state = str(info.get("player_state") or "启动中") if info else "等待信息"
            self._log.info("等待模拟器安卓启动…（%.0fs，状态: %s）",
                           time.monotonic() - started_at, state)
            time.sleep(2)

        try:
            self.connect(timeout=max(30, deadline - time.monotonic()))
        except DeviceError as e:
            raise DeviceError(
                f"模拟器已启动但 ADB 连接失败：{e}"
            ) from e

    def shutdown_instance(self, timeout: float = 20) -> None:
        """关闭本程序拉起的模拟器实例（用户自己开的不管）。"""
        if not self.started_by_us:
            self._log.info("模拟器非本程序启动，退出时不关闭")
            return
        self._log.info("关闭本程序启动的模拟器实例 %s…", self.instance)
        try:
            subprocess.run(
                [str(self.manager_exe), "control", "-v", self.instance, "shutdown"],
                capture_output=True, text=True, timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            self._log.warning("关闭模拟器实例失败（忽略）: %s", e)
        finally:
            self.started_by_us = False

    # ---------- 虚拟定位 ----------

    def set_location(self, latitude: float, longitude: float, timeout: float = 15) -> None:
        self._check_stop()
        if not self.manager_exe.is_file():
            raise LocationError(
                f"未找到 {MANAGER_NAME}，请检查设置中的模拟器路径：{self.emulator_path}"
            )
        command = [
            str(self.manager_exe),
            "control", "-v", self.instance,
            "tool", "location",
            "-lon", str(longitude),
            "-lat", str(latitude),
        ]
        self._log.info("执行定位命令: %s", " ".join(command))
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as e:
            raise LocationError(f"无法执行 {MANAGER_NAME}: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise LocationError(
                f"设置虚拟位置超时（{timeout:g} 秒），请确认模拟器未卡死"
            ) from e

        output = (result.stdout or "") + (result.stderr or "")
        payload = self._parse_manager_output(output)

        if payload is None:
            # 极老版本 MuMuManager 无 JSON 输出，只能靠返回码
            if result.returncode == 0:
                self._log.info("虚拟位置已设置（旧版无 JSON 输出）: %s, %s", latitude, longitude)
                return
            raise LocationError(
                f"设置虚拟位置失败（返回码 {result.returncode}）: {output.strip()[:200]}"
            )

        if payload.get("errcode") == 0:
            self._log.info("虚拟位置已设置: 纬度 %s, 经度 %s", latitude, longitude)
            return
        raise LocationError(
            f"设置虚拟位置失败: {payload.get('msg') or output.strip()[:200]}"
        )

    @staticmethod
    def _parse_json_object(text: str) -> Optional[dict]:
        """从输出里解析第一个 JSON 对象（逐行尝试）。"""
        for line in text.splitlines():
            line = line.strip()
            if "{" not in line:
                continue
            try:
                data = json.loads(line[line.index("{"): line.rindex("}") + 1])
            except (ValueError, IndexError):
                continue
            if isinstance(data, dict):
                return data
        return None

    @staticmethod
    def _parse_manager_output(text: str) -> Optional[dict]:
        """MuMuManager 输出里找包含 errcode 的 JSON 对象（逐行尝试）。"""
        for line in text.splitlines():
            line = line.strip()
            if "{" not in line:
                continue
            try:
                data = json.loads(line[line.index("{"): line.rindex("}") + 1])
            except (ValueError, IndexError):
                continue
            if isinstance(data, dict) and "errcode" in data:
                return data
        return None

    # ---------- 状态检查（供设置页"一键检测"） ----------

    def check_install(self) -> list[str]:
        """路径合法性检测：目录存在且包含 MuMuNxMain.exe 即视为有效。"""
        if not self.emulator_exe.is_file():
            if not self.emulator_path.is_dir():
                return [f"目录不存在: {self.emulator_path}"]
            return [f"目录里没有 {MAIN_NAME}：{self.emulator_path}"]
        return []
