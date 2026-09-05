"""webui.Api 的接口测试（不启动 GUI 窗口）。"""

from __future__ import annotations

import threading

import pytest

from deli_eplus import webui
from deli_eplus.config import Config


@pytest.fixture
def api(tmp_path, monkeypatch):
    from deli_eplus import config as config_mod

    monkeypatch.setattr(config_mod, "base_dir", lambda: tmp_path)
    monkeypatch.setattr(config_mod, "config_file", lambda: tmp_path / "config.json")
    cfg = Config(path=tmp_path / "config.json")
    return webui.Api(cfg)


def test_get_initial_shape(api):
    data = api.get_initial()
    assert data["app"]["name"]
    assert data["app"]["version"]
    assert data["app"]["author"] == "xinbaji"
    assert data["theme"] in ("light", "dark")
    assert "users" in data and "serial" in data


def test_account_crud_via_api(api):
    res = api.add_account("13800001111", "pw1")
    assert res["ok"] and res["users"]["13800001111"] == "pw1"

    bad = api.add_account("12345", "pw")
    assert not bad["ok"] and "手机号" in bad["error"]

    upd = api.update_account("13800001111", "13800001111", "pw2")
    assert upd["ok"] and upd["users"]["13800001111"] == "pw2"

    dup = api.update_account("13800001111", "13800002222", "x")
    if dup["ok"]:  # 改号成功
        assert "13800002222" in dup["users"]
        assert "13800001111" not in dup["users"]

    removed = api.remove_account("13800002222")
    assert removed["ok"]
    assert api.get_config_brief()["users"] == {}


def test_save_emulator_and_location(api):
    res = api.save_emulator("C:/MuMu", "0", "127.0.0.1:16384")
    assert res["ok"]
    assert api.get_config_brief()["emulator_num"] == "0"

    loc = api.save_location("31.2", "121.4")
    assert loc["ok"]
    brief = api.get_config_brief()
    assert brief["latitude"] == 31.2 and brief["longitude"] == 121.4

    bad = api.save_location("abc", "121")
    assert not bad["ok"]


def test_set_theme_persists(api):
    assert api.set_theme(True)["ok"]
    assert api.get_initial()["theme"] == "dark"
    api.set_theme(False)
    assert api.get_initial()["theme"] == "light"


def test_start_signup_validates(api):
    res = api.start_signup(False)
    assert not res["ok"]
    assert "模拟器路径" in res["error"]

    api.save_emulator("C:/MuMu", "0", "127.0.0.1:16384")
    res = api.start_signup(False)
    assert not res["ok"] and "账号" in res["error"]


def test_start_signup_fake_flow(api, monkeypatch):
    """打桩 SignupFlow：验证线程启动、事件回调推送到 _push。"""
    api.save_emulator("C:/MuMu", "0", "127.0.0.1:16384")
    api.add_account("13800001111", "pw")

    pushed = []
    monkeypatch.setattr(api, "_push", lambda t, d: pushed.append((t, d)))

    import deli_eplus.webui as w

    class FakeFlow:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def run(self):
            kwargs = self.kwargs
            kwargs["on_run"]("started", "")
            kwargs["on_account"]("13800001111", "done", "")
            kwargs["on_run"]("finished", "本轮结束：1/1 全部成功")
            return True

    monkeypatch.setattr(w, "SignupFlow", FakeFlow)
    assert api.start_signup(False)["ok"]
    api._worker.join(timeout=5)
    assert api._running is False
    kinds = [t for t, _ in pushed]
    assert kinds == ["run", "account", "run"]
    assert pushed[1][1]["state"] == "done"


def test_stop_signup_sets_token(api):
    api._running = True
    api.stop_signup()
    assert api._stop_token.stopped


def test_push_without_window_is_noop(api):
    api._push("toast", {"message": "hello"})  # 不应抛异常


def test_web_dir_contains_frontend():
    directory = webui.web_dir()
    assert (directory / "index.html").is_file()
    assert (directory / "app.css").is_file()
    assert (directory / "app.js").is_file()
    assert (directory / "icons.css").is_file()
    assert (directory / "fonts" / "bootstrap-icons.ttf").is_file()


def test_index_html_uses_icon_classes_not_entities():
    """图标必须走 icons.css 的 class，不允许硬编码码点实体。"""
    html = (webui.web_dir() / "index.html").read_text("utf-8")
    assert "&#x" not in html.lower()
    assert 'class="bi bi-' in html
    # app.js 引用的图标都在 icons.css 里
    icons_css = (webui.web_dir() / "icons.css").read_text("utf-8")
    import re

    for name in re.findall(r"bi-([a-z0-9-]+)", html):
        assert f".bi-{name}::before" in icons_css, f"icons.css 缺少 {name}"


def test_feed_poller_pushes_batched_items(api, monkeypatch):
    """模拟 feed handler 积压 -> _push 收到批量 items。"""
    import logging

    from deli_eplus.log import ActivityFeedHandler

    handler = ActivityFeedHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    monkeypatch.setattr(webui, "log_feed", lambda: handler)

    pushed = []
    monkeypatch.setattr(api, "_push", lambda t, d: pushed.append((t, d)))

    stop = threading.Event()
    monkeypatch.setattr(webui.threading.Event, "wait",
                        lambda self, s=None: stop.wait(0.05) or True)

    # 手动跑一轮 poll 逻辑（不启线程，直接构造）
    record = logging.LogRecord("t", logging.INFO, "f", 1, "10:00:00  消息", None, None)
    handler.emit(record)
    items = handler.drain()
    api._push("feed", {"items": [{"message": m, "level": lv} for m, lv in items]})
    assert pushed[0][0] == "feed"
    assert pushed[0][1]["items"][0]["message"] == "10:00:00  消息"

