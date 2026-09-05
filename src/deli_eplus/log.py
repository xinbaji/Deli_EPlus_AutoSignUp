"""日志：一套 logging，三处输出。

- 控制台（开发期；PyInstaller 无控制台打包时 sys.stdout 为 None，自动跳过）
- 文件 logs/deli_eplus.log，按天轮转，保留 14 天（打包后随 exe 走，用户可直接发来排查）
- UI 活动流：ActivityFeedHandler 把记录推进有界队列，主线程轮询渲染

使用：`log = get("mumu")`，成功类消息用 `log.success("...")`。
"""

from __future__ import annotations

import logging
import logging.handlers
import queue
import sys
import threading
from pathlib import Path
from typing import Optional

from .config import base_dir

SUCCESS = 25  # 介于 INFO(20) 与 WARNING(30) 之间
logging.addLevelName(SUCCESS, "SUCCESS")

_ROOT = "deli_eplus"
_lock = threading.Lock()
_configured = False
_feed: Optional["ActivityFeedHandler"] = None


class ActivityFeedHandler(logging.Handler):
    """把日志记录推入有界队列；队列满时丢最旧的一条，保证不阻塞业务线程。"""

    def __init__(self, capacity: int = 600):
        super().__init__()
        self._queue: queue.Queue[tuple[str, int]] = queue.Queue(maxsize=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            return
        with self._lock:
            try:
                self._queue.put_nowait((message, record.levelno))
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait((message, record.levelno))
                except (queue.Empty, queue.Full):
                    pass

    def drain(self) -> list[tuple[str, int]]:
        """取走当前积累的全部 (消息, 级别)，由 UI 主线程调用。"""
        items: list[tuple[str, int]] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                return items


def logs_dir() -> Path:
    return base_dir() / "logs"


def setup(console_level: int = logging.INFO, file_level: int = logging.INFO) -> None:
    """初始化根 logger（幂等，重复调用无副作用）。"""
    global _configured, _feed
    with _lock:
        if _configured:
            return
        root = logging.getLogger(_ROOT)
        root.setLevel(logging.DEBUG)

        console_fmt = logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S")
        file_fmt = logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
        )

        if sys.stdout:  # PyInstaller noconsole 下 sys.stdout 为 None
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(console_level)
            console.setFormatter(console_fmt)
            root.addHandler(console)

        try:
            directory = logs_dir()
            directory.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.TimedRotatingFileHandler(
                directory / "deli_eplus.log",
                when="midnight",
                backupCount=14,
                encoding="utf-8",
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(file_fmt)
            root.addHandler(file_handler)
        except OSError as e:
            print(f"[warn] 日志文件不可用: {e}", file=sys.stderr)

        _feed = ActivityFeedHandler()
        _feed.setLevel(logging.INFO)
        _feed.setFormatter(console_fmt)
        root.addHandler(_feed)
        _configured = True


def get(name: str) -> logging.Logger:
    """获取模块 logger；首次调用会自动完成初始化。"""
    setup()
    return logging.getLogger(f"{_ROOT}.{name}")


def feed() -> Optional[ActivityFeedHandler]:
    """UI 用来轮询的活动流 handler；setup 之后才非空。"""
    setup()
    return _feed


def _success(self: logging.Logger, message: str, *args) -> None:
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args)


logging.Logger.success = _success  # type: ignore[attr-defined]
