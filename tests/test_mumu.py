"""MuMuDevice：路径检查、进程启动、MuMuManager 定位输出解析（mock 子进程）。"""

from __future__ import annotations

import subprocess
import types

import pytest

from deli_eplus.device.exceptions import DeviceError, LocationError
from deli_eplus.device.mumu import MuMuDevice


@pytest.fixture
def mumu_dir(tmp_path):
    """造一个假的 MuMu 目录，含两个关键 exe。"""
    (tmp_path / "MuMuNxMain.exe").write_bytes(b"")
    (tmp_path / "MuMuManager.exe").write_bytes(b"")
    return tmp_path


@pytest.fixture
def device(mumu_dir):
    return MuMuDevice("127.0.0.1:16384", str(mumu_dir), "0")


def test_missing_paths_reported(tmp_path):
    """检测语义：目录里只要有 MuMuNxMain.exe 即为合法。"""
    device = MuMuDevice("s", str(tmp_path), "0")
    problems = device.check_install()
    assert any("MuMuNxMain.exe" in p for p in problems)

    (tmp_path / "MuMuNxMain.exe").write_bytes(b"")
    assert MuMuDevice("s", str(tmp_path), "0").check_install() == []


def test_start_emulator_missing_exe_clear_error(tmp_path):
    device = MuMuDevice("s", str(tmp_path), "0")
    with pytest.raises(DeviceError) as exc:
        device.start_emulator(timeout=1)
    assert "未找到" in str(exc.value)


def test_start_emulator_launches_process_and_connects(device, mumu_dir, monkeypatch):

    def fake_popen(cmd, cwd=None, **kwargs):
        launched["cmd"] = cmd
        return "proc"

    launched = {}
    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.Popen", fake_popen)
    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.run",
                        lambda cmd, **kw: types.SimpleNamespace(
                            stdout=b'{"is_process_started": false, "is_android_started": true}',
                            stderr=b""))
    monkeypatch.setattr(device, "connect", lambda timeout=180: None)
    device.start_emulator(timeout=1)
    assert launched["cmd"][0].endswith("MuMuManager.exe")
    assert "launch" in launched["cmd"]
    assert device.started_by_us is True  # info: 进程未运行 → 由本程序拉起


def test_set_location_success_json(device, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0, stdout='{"errcode": 0, "msg": "success"}\n', stderr=""
        )

    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.run", fake_run)
    device.set_location(31.2, 121.4)  # 不抛即成功


def test_set_location_errcode_nonzero_raises(device, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 1, stdout='{"errcode": 30, "msg": "instance not running"}\n', stderr=""
        )

    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.run", fake_run)
    with pytest.raises(LocationError) as exc:
        device.set_location(31.2, 121.4)
    assert "instance not running" in str(exc.value)


def test_set_location_spacing_variant_json(device, monkeypatch):
    """旧版输出 errcode 后可能没有空格，也必须识别成功。"""
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"errcode":0}\n', stderr="")

    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.run", fake_run)
    device.set_location(1.0, 2.0)


def test_set_location_unparseable_output_with_returncode(device, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 3, stdout="some garbage", stderr="boom")

    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.run", fake_run)
    with pytest.raises(LocationError) as exc:
        device.set_location(1.0, 2.0)
    assert "3" in str(exc.value)


def test_set_location_manager_missing(tmp_path):
    device = MuMuDevice("s", str(tmp_path), "0")
    with pytest.raises(LocationError) as exc:
        device.set_location(1.0, 2.0)
    assert "MuMuManager" in str(exc.value)


def test_set_location_timeout(device, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 15)

    monkeypatch.setattr("deli_eplus.device.mumu.subprocess.run", fake_run)
    with pytest.raises(LocationError):
        device.set_location(1.0, 2.0)


def test_parse_json_object_multiline():
    """MuMuManager info 是多行美化 JSON，必须整段解析。"""
    multiline = '{\n  "adb_port": 16384,\n  "is_android_started": true\n}'
    data = MuMuDevice._parse_json_object(multiline)
    assert data == {"adb_port": 16384, "is_android_started": True}


def test_parse_manager_output_variants():
    assert MuMuDevice._parse_manager_output('{"errcode": 0}') == {"errcode": 0}
    assert MuMuDevice._parse_manager_output('log line\n{"errcode": 5, "msg": "x"}') == {
        "errcode": 5, "msg": "x"
    }
    assert MuMuDevice._parse_manager_output("no json here") is None
