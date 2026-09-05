"""MuMu 模拟器专属能力：启动模拟器进程、设置虚拟定位（MuMuManager）。

通用的 adb/uiautomator 操作全部继承自 AndroidDevice，本类只补 MuMu 专属部分，
因此换其他模拟器（雷电、夜神…）时只需要照着写一个对应子类。
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

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

    def _emu_process_running(self) -> bool:
        """MuMu 主进程是否已在运行（运行中则退出时不代关）。"""
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {MAIN_NAME}"],
                capture_output=True, text=True, timeout=10,
            ).stdout.lower()
            return "mumunxmain" in out
        except (OSError, subprocess.TimeoutExpired):
            return False

    def start_emulator(self, timeout: float = 180) -> None:
        """启动 MuMu 实例并阻塞等待 ADB 可连接（不再"火后不管"）。"""
        self._check_stop()
        for exe in (self.emulator_exe, self.manager_exe):
            if not exe.is_file():
                raise DeviceError(
                    f"未找到 {exe.name}，请检查设置中的模拟器路径：{self.emulator_path}"
                )
        self.started_by_us = not self._emu_process_running()
        try:
            subprocess.Popen(
                [str(self.emulator_exe), "-v", self.instance],
                cwd=str(self.emulator_path),
            )
        except OSError as e:
            raise DeviceError(f"启动模拟器进程失败: {e}") from e

        self._log.info("模拟器启动命令已发出（实例 %s），等待 ADB 连接…", self.instance)
        try:
            self.connect(timeout=timeout)
        except DeviceError as e:
            raise DeviceError(
                f"模拟器启动后 {timeout:g} 秒内仍无法连接：请确认 MuMu 能正常打开"
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
        """返回问题清单；空列表表示路径与关键文件齐全。"""
        problems: list[str] = []
        if not self.emulator_path.is_dir():
            problems.append(f"目录不存在: {self.emulator_path}")
            return problems
        for exe in (self.emulator_exe, self.manager_exe):
            if not exe.is_file():
                problems.append(f"缺少 {exe.name}")
        return problems

    def wait_adb_ready(self, timeout: float = 10) -> bool:
        """短连接检测设备是否可达（供设置页"一键检测"）。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.connect(timeout=2)
                return True
            except DeviceError:
                continue
        return False
