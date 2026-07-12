import logging
from typing import Callable


class Log:
    """日志模块：支持控制台输出 + GUI 回调（不写入本地文件）"""

    _gui_callbacks: list[Callable[[str], None]] = []

    @classmethod
    def add_gui_callback(cls, callback: Callable[[str], None]):
        """注册 GUI 日志回调，用于在 GUI 文本框中实时显示日志"""
        if callback not in cls._gui_callbacks:
            cls._gui_callbacks.append(callback)

    @classmethod
    def remove_gui_callback(cls, callback: Callable[[str], None]):
        """移除 GUI 日志回调"""
        if callback in cls._gui_callbacks:
            cls._gui_callbacks.remove(callback)

    class _GuiHandler(logging.Handler):
        """自定义 Handler，将日志推送到 GUI"""
        def emit(self, record):
            try:
                msg = self.format(record)
                for cb in Log._gui_callbacks:
                    try:
                        cb(msg + "\n")
                    except Exception:
                        pass
            except Exception:
                pass

    def __init__(self, log_name, mode: str = "i") -> None:
        log_level = logging.DEBUG if mode == "d" else logging.INFO

        self.logger = logging.getLogger(log_name)
        # 防止重复添加 handler
        if self.logger.handlers:
            self.logger.handlers.clear()

        self.logger.setLevel(level=log_level)

        formatter = logging.Formatter(
            "%(asctime)s - %(funcName)s - %(levelname)s - %(message)s"
        )

        # 控制台 Handler
        console = logging.StreamHandler()
        console.setLevel(log_level)
        console.setFormatter(formatter)
        self.logger.addHandler(console)

        # GUI Handler（始终添加，有回调时才实际输出）
        gui_handler = self._GuiHandler()
        gui_handler.setLevel(log_level)
        gui_handler.setFormatter(formatter)
        self.logger.addHandler(gui_handler)
