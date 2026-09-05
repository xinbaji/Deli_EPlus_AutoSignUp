"""CLI 入口：参数、缺配置时的友好报错。"""

from __future__ import annotations

import json

import pytest

from deli_eplus import cli
from deli_eplus import log as applog


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """把 config 与日志目录定位到临时目录。"""
    from deli_eplus import config as config_mod
    from deli_eplus import log as log_mod

    monkeypatch.setattr(config_mod, "base_dir", lambda: tmp_path)
    monkeypatch.setattr(config_mod, "config_file", lambda: tmp_path / "config.json")
    monkeypatch.setattr(log_mod, "logs_dir", lambda: tmp_path / "logs")
    applog.setup()
    applog.feed().drain()
    return tmp_path


def drain_messages() -> list[str]:
    return [message for message, _ in applog.feed().drain()]


def test_missing_emulator_path_reports_clearly(isolated_config):
    code = cli.main([])
    assert code == 1
    assert any("模拟器路径" in m for m in drain_messages())


def test_missing_users_reports_clearly(isolated_config):
    (isolated_config / "config.json").write_text(
        json.dumps({"emulator_path": "C:/MuMu"}), encoding="utf-8"
    )
    code = cli.main([])
    assert code == 1
    assert any("账号" in m for m in drain_messages())


def test_invalid_emulator_path_fails_without_traceback(isolated_config):
    """路径不是 MuMu 目录 → 设备错误以友好形式输出，无 traceback。"""
    (isolated_config / "config.json").write_text(
        json.dumps({"emulator_path": "C:/Other", "users": {"13800001111": "pw"}}),
        encoding="utf-8",
    )
    code = cli.main(["--debug"])
    assert code == 1
    messages = drain_messages()
    assert any("MuMu" in m for m in messages)


def test_version_flag(isolated_config, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
