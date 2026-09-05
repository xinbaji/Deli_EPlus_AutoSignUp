"""updater：版本比较、多源回退、URL 构造、下载、更新脚本生成。"""

from __future__ import annotations

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


class _FakeResponse:
    def __init__(self, payload: bytes = b"", headers: dict | None = None,
                 chunks: list[bytes] | None = None):
        self.headers = headers or {}
        self._chunks = chunks if chunks is not None else (
            [self._payload] if self._payload else [])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        return self._chunks.pop(0) if self._chunks else b""


def test_latest_release_github(monkeypatch):
    """github 源命中直连 API；下载候选是完整回退链（直连在前）。"""
    captured = {}

    def fake_fetch_json(url, timeout):
        captured["url"] = url
        return {"tag_name": "v1.2.3", "body": "更新说明"}

    monkeypatch.setattr(updater, "_fetch_json", fake_fetch_json)
    info = updater.latest_release("github")

    assert info["tag"] == "1.2.3"
    assert info["asset_urls"][0] == updater._DOWNLOAD_TEMPLATE.format(
        repo=updater.REPO, tag="v1.2.3", asset=updater.ASSET_NAME)
    assert "api.github.com" in captured["url"]
    # 回退链：直连在前，gh-proxy 其次
    assert info["asset_urls"][1].startswith("https://gh-proxy.com/")


def test_latest_release_mirror_prefers_proxy_api(monkeypatch):
    captured = {}

    def fake_fetch_json(url, timeout):
        captured["url"] = url
        return {"tag_name": "v1.2.3", "body": ""}

    monkeypatch.setattr(updater, "_fetch_json", fake_fetch_json)
    updater.latest_release("mirror")
    assert captured["url"].startswith("https://gh-proxy.com/")


def test_latest_release_falls_back_when_first_source_down(monkeypatch):
    """首选源失败 → 自动尝试下一个源。"""
    tried = []

    def fake_fetch_json(url, timeout):
        tried.append(url)
        if url.startswith("https://api.github.com"):
            raise OSError("connection reset")
        return {"tag_name": "v1.2.4", "body": ""}

    monkeypatch.setattr(updater, "_fetch_json", fake_fetch_json)
    info = updater.latest_release("github")
    assert len(tried) >= 2
    assert info["tag"] == "1.2.4"


def test_latest_release_all_sources_down(monkeypatch):
    def fake_fetch_json(url, timeout):
        raise OSError("timeout")

    monkeypatch.setattr(updater, "_fetch_json", fake_fetch_json)
    with pytest.raises(RuntimeError):
        updater.latest_release("github")


def test_latest_release_no_release_yet(monkeypatch):
    monkeypatch.setattr(updater, "_fetch_json",
                        lambda url, timeout: {"tag_name": ""})
    assert updater.latest_release("github") is None


def test_download_falls_back_to_next_url(tmp_path, monkeypatch):
    """第一个地址超时失败 → 自动切下一个，文件完整落盘。"""
    dest = tmp_path / "update.zip"

    def fake_urlopen(request, timeout=None):
        if request.full_url.startswith("https://github.com/"):
            raise OSError("timeout")   # 直连失败
        return _FakeResponse(headers={"Content-Length": "6"},
                             chunks=[b"123456"])

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)

    percents = []
    out = updater.download(
        ["https://github.com/x.zip", "https://gh-proxy.com/https://github.com/x.zip"],
        dest, progress=percents.append)
    assert out == dest
    assert dest.read_bytes() == b"123456"
    assert percents[-1] == 100


def test_download_all_fail_cleans_partial_file(tmp_path, monkeypatch):
    dest = tmp_path / "update.zip"

    def fake_urlopen(request, timeout=None):
        raise OSError("all down")

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError):
        updater.download(["https://a", "https://b"], dest)
    assert not dest.exists()


def test_apply_update_writes_bat(tmp_path, monkeypatch):
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
    assert "taskkill" in text
    assert launched["cmd"][0] == "cmd"
