"""config.py 的加载/保存/备份/导入导出测试。"""

from __future__ import annotations

import json
import threading

import pytest

from deli_eplus.config import Config, ConfigError, normalize, valid_phone


def test_first_load_creates_default_file(config: Config, config_path):
    assert config_path.exists()
    data = json.loads(config_path.read_text("utf-8"))
    assert data["users"] == {}
    assert data["emulator_num"] == "0"


def test_load_merges_saved_values(config: Config):
    config.add_user("13800001111", "pw1")
    config.save()
    again = Config(path=config.path)
    assert again.users == {"13800001111": "pw1"}
    assert again.emulator_path == "C:/Program Files/Netease/MuMu"


def test_corrupted_file_backed_up_not_overwritten(config: Config):
    config.add_user("13800002222", "pw2")
    config.save()
    # 模拟写入中途损坏：文件内容变成非法 JSON（数据已不可读）
    config.path.write_text("{broken json!!", encoding="utf-8")

    loaded = Config(path=config.path)

    # 损坏文件被改名备份留证，而不是被默认配置静默覆写
    backups = list(config.path.parent.glob("config.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text("utf-8") == "{broken json!!"
    # 应用用默认配置正常启动，并把默认值落盘
    assert loaded.users == {}
    assert json.loads(config.path.read_text("utf-8"))["users"] == {}
    # 再次加载不会重复备份
    Config(path=config.path)
    assert len(list(config.path.parent.glob("config.json.bak-*"))) == 1


def test_save_is_atomic_no_tmp_leftover(config: Config):
    config.add_user("13800003333", "pw3")
    config.save()
    assert not list(config.path.parent.glob("*.tmp"))


def test_emulator_num_coerced_to_str(config: Config):
    config.path.write_text(json.dumps({"emulator_num": 3}), encoding="utf-8")
    loaded = Config(path=config.path)
    assert loaded.emulator_num == "3"


def test_location_type_coercion(config: Config):
    config.path.write_text(
        json.dumps({"location": {"latitude": "31.5", "longitude": "bad"}}),
        encoding="utf-8",
    )
    loaded = Config(path=config.path)
    assert loaded.location["latitude"] == 31.5
    assert loaded.location["longitude"] == 45.0  # 坏值回退默认


def test_users_drops_empty_entries():
    data = normalize({"users": {"13800004444": "pw", "bad": "", "": "x"}})
    assert data["users"] == {"13800004444": "pw"}


def test_set_location_validates_range(config: Config):
    with pytest.raises(ConfigError):
        config.set_location(999, 0)
    config.set_location(-31.2, 121.4)
    assert config.location == {"latitude": -31.2, "longitude": 121.4}


def test_add_user_validates(config: Config):
    with pytest.raises(ConfigError):
        config.add_user("12345", "pw")
    with pytest.raises(ConfigError):
        config.add_user("13800005555", "")
    config.add_user("13800005555", "pw5")


def test_valid_phone():
    assert valid_phone("13800001111")
    assert not valid_phone("23800001111")
    assert not valid_phone("1380000111")


def test_import_replaces_and_validates(config: Config, tmp_path):
    source = tmp_path / "import.json"
    source.write_text(
        json.dumps({"users": {"13900006666": "pw66"}, "emulator_num": 2}),
        encoding="utf-8",
    )
    config.import_from(source)
    assert config.users == {"13900006666": "pw66"}
    assert config.emulator_num == "2"

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"users": {}}), encoding="utf-8")
    with pytest.raises(ConfigError):
        config.import_from(bad)


def test_export_roundtrip(config: Config, tmp_path):
    config.add_user("13700007777", "pw77")
    target = tmp_path / "out.json"
    config.export_to(target)
    other = Config(path=tmp_path / "other.json")
    other.import_from(target)
    assert other.users == config.users


def test_concurrent_saves_keep_file_valid(config: Config):
    errors = []

    def writer(index: int) -> None:
        try:
            for round_ in range(20):
                config.add_user(f"136{index:01d}{round_:02d}00000", "pw")
                config.save()
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    reloaded = Config(path=config.path)
    assert len(reloaded.users) == 80
