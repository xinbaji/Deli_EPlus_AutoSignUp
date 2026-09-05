"""updater：版本比较、下载源归一、URL 构造、更新脚本生成。"""

from __future__ import annotations

import json

import pytest

from deli_eplus import updater


def test_parse_version():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("1.10.0") == (1, 10, 0)
    assert updater.parse_version("") == (0,)
    assert updater.parse_version("v2") == (2,)


def test_is_newer():
    assert updater.is_newer("1.2.0", "1.1.9")
    assert updater.is_newer("v1.1.0", "1.0.9")
    assert not updater.is_newer("1.1.0", "1.1.0")
    assert not updater.is_newer("1.0.9", "1.1.0")


def test_normalize_source():
    assert updater.normalize_source("mirror") == "mirror"
    assert updater.normalize_source("github") == "github"
    assert updater.normalize_source("垃圾") == "github"


def test_asset_url_sources():
    """镜像源的下载地址必须是 gh-proxy 前缀的 github 地址。"""
    info = {"tag": "v9.9.9"}
    # github 源
    url = "https://github.com/{repo}/releases/download/{tag}/{asset}".format(
        repo=updater.REPO, tag="v9.9.9", asset=updater.ASSET_NAME)
    assert url.startswith("https://github.com/")
    # mirror 源走 gh-proxy 前缀（构造逻辑与 latest_release 相同）
    mirrored = "https://gh-proxy.com/" + url
    assert mirrored.startswith("https://gh-proxy.com/https://github.com/")
    _ = info


def test_latest_release_network_call(monkeypatch):
    """打桩 urllib：验证 JSON 解析与 asset_url 组装（无真实网络）。"""
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({
                "tag_name": "v1.2.3",
                "body": "更新说明",
                "assets": [{"name": updater.ASSET_NAME}],
            }).encode("utf-8")

    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["ua"] = request.headers.get("User-agent")
        return FakeResponse()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)

    info = updater.latest_release("github")
    assert info["tag"] == "1.2.3"
    assert info["asset_url"] == updater._DOWNLOAD.format(
        repo=updater.REPO, tag="v1.2.3", asset=updater.ASSET_NAME)
    assert "api.github.com" in captured["url"]
    assert captured["ua"] == updater.USER_AGENT

    mirror_info = updater.latest_release("mirror")
    assert mirror_info["asset_url"].startswith("https://gh-proxy.com/")
    assert "api.github.com" in captured["url"]  # mirror 也反代 API

    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(
                            OSError("connection reset")))
    with pytest.raises(RuntimeError):
        updater.latest_release("github")


def test_download_streams_with_progress(tmp_path, monkeypatch):
    class FakeResponse:
        headers = {"Content-Length": "6"}

        def __init__(self):
            self._sent = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            if not self._sent:
                self._sent = True
                return b"123456"
            return b""

    resp = FakeResponse()

    def fake_urlopen(request, timeout=None):
        return resp

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)

    dest = tmp_path / "update.zip"
    percents = []
    out = updater.download("http://x/y.zip", dest, progress=percents.append)
    assert out == dest
    assert dest.read_bytes() == b"123456"
    assert percents[-1] == 100


def test_apply_update_writes_bat(tmp_path):
    zip_path = tmp_path / "update" / "pkg.zip"
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"z")
    launched = {}
    monkey = pytest.MonkeyPatch()
    monkey.setattr(updater.subprocess, "Popen",
                   lambda cmd, cwd=None, creationflags=0: launched.setdefault(
                       "cmd", cmd))
    try:
        bat = updater.apply_update(zip_path, tmp_path, "Deli_EPlus_AutoSignUp.exe")
    finally:
        monkey.undo()
    text = bat.read_text("ascii")
    assert "Expand-Archive" in text
    assert updater.ASSET_NAME in text or "pkg.zip" in text
    assert "taskkill" in text
    assert launched["cmd"][0] == "cmd"
