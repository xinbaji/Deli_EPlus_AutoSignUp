"""一键打包：PyInstaller onedir → 便携 zip（发 release 用）。

用法（在任意目录均可）：
    .venv/Scripts/python script/build.py

产物：
    dist/Deli_EPlus_AutoSignUp/                  目录版（解压即用，启动最快）
    dist/Deli_EPlus_AutoSignUp_portable.zip      便携包（上传 GitHub release）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

# 非 UTF-8 控制台（如 CI 的 cp1252）下 print 中文不再报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Deli_EPlus_AutoSignUp"
SPEC = ROOT / "script" / "Deli_EPlus.spec"
VERSION = "1.2.0"


def run_pyinstaller() -> Path:
    dist_dir = ROOT / "dist" / APP_NAME
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
    ]
    print(">>", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = dist_dir / f"{APP_NAME}.exe"
    if not exe.is_file():
        raise SystemExit("构建失败：未找到产物 exe")
    return dist_dir


def make_portable_zip(dist_dir: Path) -> Path:
    zip_path = ROOT / "dist" / f"{APP_NAME}_portable.zip"
    if zip_path.exists():
        zip_path.unlink()
    print(f">> 打包便携 zip: {zip_path.name}")
    t0 = time.time()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file in sorted(dist_dir.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(dist_dir.parent))
    print(f"   压缩完成（{time.time() - t0:.0f}s）")
    return zip_path


def report(dist_dir: Path, zip_path: Path) -> None:
    total = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file())
    print(f"\n目录版: {total / 1024 / 1024:.1f} MB  ({dist_dir})")
    print(f"便携包: {zip_path.stat().st_size / 1024 / 1024:.1f} MB  ({zip_path})")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 GUI 目录版 + 便携 zip")
    parser.parse_args()

    dist_dir = run_pyinstaller()
    zip_path = make_portable_zip(dist_dir)
    report(dist_dir, zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
