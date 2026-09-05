"""远程版本检查与自更新（纯 urllib，不依赖 git）。

下载源两种，检测与下载都走所选源：
- github：api.github.com + github.com（默认）
- mirror：gh-proxy.com 反代（国内可达）

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

_API = {
    "github": f"https://api.github.com/repos/{REPO}/releases/latest",
    "mirror": f"https://gh-proxy.com/https://api.github.com/repos/{REPO}/releases/latest",
}
_DOWNLOAD = "https://github.com/{repo}/releases/download/{tag}/{asset}"


def normalize_source(source: str) -> str:
    return "mirror" if source == "mirror" else "github"


def latest_release(source: str = "github", timeout: float = 15) -> Optional[dict]:
    """查询最新 release。返回 {"tag","notes","asset_url"}；还没有 release 时返回 None。

    抛出 RuntimeError 表示网络/代理失败（调用方转成用户可读提示）。
    """
    source = normalize_source(source)
    url = _API[source]
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"连接更新源失败：{e}") from e

    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    asset_url = _DOWNLOAD.format(repo=REPO, tag=tag, asset=ASSET_NAME)
    if source == "mirror":
        asset_url = f"https://gh-proxy.com/{asset_url}"
    notes = re.sub(r"\r\n", "\n", str(data.get("body") or ""))
    return {"tag": tag.lstrip("v"), "notes": notes, "asset_url": asset_url}


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.10.2-beta' -> (1, 10, 2)；非数字段忽略。"""
    numbers = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in numbers[:3]) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def download(url: str, dest: Path, progress: Optional[Callable[[int], None]] = None,
             timeout: float = 30) -> Path:
    """流式下载到 dest，每收到一块回调百分比（0-100）。"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as f:
                while True:
                    if progress is not None and total:
                        percent = min(100, int(done * 100 / total))
                        progress(percent)
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
            if progress is not None:
                progress(100)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


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
