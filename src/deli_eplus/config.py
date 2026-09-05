"""配置管理：config.json 的加载、保存、导入与导出。

约定：
- 数据永远存在 exe 旁边的 config.json（开发期在仓库根目录），不写进任何 .py；
- 加载时文件损坏会先备份成 config.json.bak-<时间戳> 再落回默认值，绝不覆写原文件；
- 保存使用 临时文件 + os.replace 原子写，避免写一半崩溃导致配置损坏；
- 所有字段读取时做类型规整，坏值回退默认，绝不抛异常打断启动。
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "serial": "127.0.0.1:16384",
    "theme": "light",
    "download_source": "github",
    "emulator_path": "",
    "emulator_num": "0",
    "location": {"latitude": 45.0, "longitude": 45.0},
    "users": {},
}

_PHONE_RE = re.compile(r"^1\d{10}$")


class ConfigError(ValueError):
    """配置值不合法（用于提交给本模块保存/导入的数据）。"""


def base_dir() -> Path:
    """exe 所在目录（打包后）或仓库根目录（开发期）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def config_file() -> Path:
    return base_dir() / "config.json"


def valid_phone(phone: str) -> bool:
    return bool(_PHONE_RE.match(phone))


def mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 8 else phone


def normalize(raw: Any) -> dict[str, Any]:
    """把任意来源的数据规整为受控结构；坏值回退默认。"""
    data = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(raw, dict):
        return data

    data["serial"] = str(raw.get("serial") or data["serial"]).strip()
    data["emulator_path"] = str(raw.get("emulator_path") or "").strip()
    data["emulator_num"] = str(raw.get("emulator_num", data["emulator_num"])).strip() or "0"
    data["theme"] = "dark" if raw.get("theme") == "dark" else "light"
    data["download_source"] = ("mirror" if raw.get("download_source") == "mirror"
                               else "github")

    loc = raw.get("location")
    if isinstance(loc, dict):
        for key in ("latitude", "longitude"):
            try:
                data["location"][key] = float(loc.get(key, data["location"][key]))
            except (TypeError, ValueError):
                pass

    users = raw.get("users")
    if isinstance(users, dict):
        cleaned: dict[str, str] = {}
        for phone, password in users.items():
            phone_s = str(phone).strip()
            pwd_s = str(password).strip()
            if phone_s and pwd_s:
                cleaned[phone_s] = pwd_s
        data["users"] = cleaned
    return data


class Config:
    """线程安全的运行配置，内存持有 + 显式 save()。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else config_file()
        self._lock = threading.RLock()
        self._data: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    # ---------- 加载 / 保存 ----------

    def load(self) -> None:
        with self._lock:
            raw: Any = None
            if self.path.exists():
                try:
                    raw = json.loads(self.path.read_text("utf-8"))
                except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                    self._backup_corrupted()
                    logger.warning("config.json 无法解析（%s），已备份并改用默认配置", e)
                    raw = None
            self._data = normalize(raw)
            if not self.path.exists():
                self.save()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, self.path)

    def _backup_corrupted(self) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.bak-{stamp}")
        try:
            os.replace(self.path, backup)
            logger.warning("原文件已备份为 %s", backup.name)
        except OSError as e:
            logger.error("备份损坏的 config.json 失败: %s", e)

    # ---------- 读取 ----------

    @property
    def serial(self) -> str:
        return self._data["serial"]

    @property
    def emulator_path(self) -> str:
        return self._data["emulator_path"]

    @property
    def emulator_num(self) -> str:
        return self._data["emulator_num"]

    @property
    def location(self) -> dict[str, float]:
        return dict(self._data["location"])

    @property
    def theme(self) -> str:
        return self._data["theme"]

    @property
    def download_source(self) -> str:
        return self._data["download_source"]

    @property
    def users(self) -> dict[str, str]:
        return dict(self._data["users"])

    # ---------- 修改 ----------

    def set_emulator(self, path: str, num: str, serial: str) -> None:
        with self._lock:
            self._data["emulator_path"] = path.strip()
            self._data["emulator_num"] = str(num).strip() or "0"
            self._data["serial"] = serial.strip() or DEFAULT_CONFIG["serial"]

    def set_location(self, latitude: float, longitude: float) -> None:
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError) as e:
            raise ConfigError("经纬度必须是数字") from e
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ConfigError("纬度范围 -90~90，经度范围 -180~180")
        with self._lock:
            self._data["location"] = {"latitude": lat, "longitude": lon}

    def set_theme(self, dark: bool) -> None:
        with self._lock:
            self._data["theme"] = "dark" if dark else "light"
        self.save()

    def set_download_source(self, source: str) -> None:
        if source not in ("github", "mirror"):
            raise ConfigError("下载源只能是 github 或 mirror")
        with self._lock:
            self._data["download_source"] = source
        self.save()

    def set_users(self, users: dict[str, str]) -> None:
        cleaned = normalize({"users": users})["users"]
        if not cleaned and users:
            raise ConfigError("账号格式不正确")
        with self._lock:
            self._data["users"] = cleaned

    def add_user(self, phone: str, password: str) -> None:
        phone = phone.strip()
        password = password.strip()
        if not valid_phone(phone):
            raise ConfigError("手机号格式不正确（11 位，1 开头）")
        if not password:
            raise ConfigError("密码不能为空")
        with self._lock:
            self._data["users"][phone] = password

    def remove_user(self, phone: str) -> None:
        with self._lock:
            self._data["users"].pop(phone, None)

    # ---------- 导入 / 导出 ----------

    def export_to(self, target: str | Path) -> None:
        with self._lock:
            payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        Path(target).write_text(payload, encoding="utf-8")

    def import_from(self, source: str | Path) -> None:
        """用指定文件整体替换当前配置（覆盖前先在内存中规整校验）。"""
        text = Path(source).read_text("utf-8")
        data = normalize(json.loads(text))
        if not data["users"]:
            raise ConfigError("导入文件中没有账号")
        with self._lock:
            self._data = data
        self.save()
