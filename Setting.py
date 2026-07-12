"""
配置中间层：连接 GUI 和 deliSignup
- 首次启动从 config.json 读取，不存在则使用默认值
- 支持运行时动态更新（GUI 写入后立即生效）
- 兼容原有 Setting.xxx 类属性访问方式
"""

import json
import os
import sys

# PyInstaller 打包后 sys.frozen 为 True，此时应使用 EXE 所在目录而非临时解压目录
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "serial": "127.0.0.1:16384",
    "emulator_path": "",
    "emulator_num": "0",
    "location": {"latitude": 45, "longitude": 45},
    "users": {},
    "debugmode": False
}


def load_config():
    """从 config.json 加载配置，不存在则创建默认配置"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(cfg)
            return merged
        except (json.JSONDecodeError, IOError):
            pass
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    """保存配置到 config.json"""
    os.makedirs(os.path.dirname(CONFIG_PATH) if os.path.dirname(CONFIG_PATH) else ".", exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def reload_config():
    """强制重新加载配置文件并同步到模块全局变量和 Setting 类属性"""
    cfg = load_config()
    _this_module = sys.modules[__name__]
    for key, value in cfg.items():
        # 同时设置模块级变量和类属性
        setattr(_this_module, key, value)
        setattr(Setting, key, value)


class Setting:
    """兼容原有接口，类属性由 reload_config() 动态设置"""

    @classmethod
    def reload(cls):
        reload_config()


# 初次加载
reload_config()
