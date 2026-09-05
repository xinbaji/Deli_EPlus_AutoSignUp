"""远程版本检查与自更新（纯 urllib，不依赖 git）。

下载源（实测择优 + 自动回退，检测与下载都走所选优先源，失败自动切下一个）：
- github（默认）：api.github.com + github.com 直连，API 稳定
- mirror：gh-proxy.com 反代（实测最快的镜像），下载常比直连快 2 倍

更新流程：检查（后台线程）→ 有新版显示「立即更新」→ 下载便携 zip
（带进度）→ 写 update.bat 等本程序退出后解压覆盖并重启。
config.json / logs 不在 zip 内，更新不会动用户数据。
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable, Optional

REPO = "xinbaji/Deli_EPlus_AutoSignUp"
ASSET_NAME = "Deli_EPlus_AutoSignUp_portable.zip"
USER_AGENT = "deli-eplus-autoupdate"
TIMEOUT_API = 12
TIMEOUT_DOWNLOAD = 30

# 候选源（顺序即默认回退顺序）：前缀 + 固定 API 地址
_API_PREFIXES = [
    ("github", ""),                                    # 直连 api.github.com
    ("mirror", "https://gh-proxy.com/"),
    ("ghproxy.net", "https://ghproxy.net/"),
    ("ghproxy.cn", "https://ghproxy.cn/"),
]
_API_BASE = f"https://api.github.com/repos/{REPO}/releases/latest"
_DOWNLOAD_TEMPLATE = "https://github.com/{repo}/releases/download/{tag}/{asset}"
_MIRROR_PREFIXES = ["", "https://gh-proxy.com/", "https://ghproxy.net/",
                    "https://ghproxy.cn/"]


def normalize_source(source: str) -> str:
    return "mirror" if source == "mirror" else "github"


def _ordered(prefixes: list[str], preferred: str) -> list[str]:
    """把用户选的源排到最前，其余作为自动回退。"""
    preferred_prefix = "https://gh-proxy.com/" if preferred == "mirror" else ""
    ordered = [p for p in prefixes if p == preferred_prefix]
    ordered += [p for p in prefixes if p != preferred_prefix]
    return ordered


def _fetch_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def latest_release(preferred: str = "github", timeout: float = TIMEOUT_API) -> Optional[dict]:
    """查询最新 release。返回 {"tag","notes","asset_urls"}；无 release 返回 None。

    按 preferred 优先的顺序尝试所有源，全部失败抛 RuntimeError。
    """
    preferred = normalize_source(preferred)
    last_error: Optional[Exception] = None
    for prefix in _ordered([p for _, p in _API_PREFIXES], preferred):
        try:
            data = _fetch_json(prefix + _API_BASE, timeout)
        except Exception as e:
            last_error = e
            continue
        tag = str(data.get("tag_name") or "").strip()
        if not tag:
            return None
        # 下载候选 = 全部前缀回退链（直连 + 各镜像），与 API 走哪条无关
        asset_urls = [
            prefix + _DOWNLOAD_TEMPLATE.format(repo=REPO, tag=tag, asset=ASSET_NAME)
            for prefix in _MIRROR_PREFIXES
        ]
        notes = re.sub(r"\r\n", "\n", str(data.get("body") or ""))
        return {"tag": tag.lstrip("v"), "notes": notes, "asset_urls": asset_urls}
    raise RuntimeError(f"连接更新源失败：{last_error!r}")


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.10.2-beta' -> (1, 10, 2)；非数字段忽略。"""
    numbers = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in numbers[:3]) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def download(urls: list[str], dest: Path,
             progress: Optional[Callable[[int], None]] = None) -> Path:
    """按候选地址顺序流式下载到 dest，失败自动换下一个源。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Optional[Exception] = None
    for url in urls:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT_DOWNLOAD) as response:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                with open(dest, "wb") as f:
                    while True:
                        if progress is not None and total:
                            progress(min(100, int(done * 100 / total)))
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
            if progress is not None:
                progress(100)
            return dest
        except Exception as e:
            last_error = e
            dest.unlink(missing_ok=True)
            continue
    raise RuntimeError(f"所有下载源均失败：{last_error!r}")


def apply_update(zip_path: Path, app_dir: Path, exe_name: str) -> Path:
    """写 update.bat：等本程序退出 → 解压覆盖 → 删包 → 重启 → 自删。

    返回 bat 路径；调用方启动它后自行退出程序。
    """
    zip_path = zip_path.resolve()
    app_dir = app_dir.resolve()
    bat = app_dir / "update.bat"
    script = f"""@echo off
rem auto-update script (generated)
timeout /t 2 /nobreak >nul
taskkill /IM {exe_name} /F >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force '{zip_path}' '{app_dir}'"
if exist "{zip_path}" del "{zip_path}"
start "" "{app_dir / exe_name}"
del "%~f0"
"""
    bat.write_text(script, encoding="ascii", errors="ignore")
    subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(app_dir),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return bat
