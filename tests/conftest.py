"""公共测试夹具与假设备。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deli_eplus.config import Config  # noqa: E402


@pytest.fixture
def config_path(tmp_path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def config(config_path) -> Config:
    cfg = Config(path=config_path)
    cfg.set_emulator("C:/Program Files/Netease/MuMu", "0", "127.0.0.1:16384")
    return cfg
