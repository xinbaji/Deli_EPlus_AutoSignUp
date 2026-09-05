# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：onedir + 无控制台，只打包 GUI。

要点：
- uiautomator2 / adbutils 在代码里是延迟导入，Analysis 静态分析看不见，
  必须用 collect_submodules 显式列入 hiddenimports；
- 旧 spec 曾把源码 .py 再塞一份 datas，纯属重复，已去掉；
- 字体资源放 assets/fonts，运行时经 sys._MEIPASS 读取。
"""
from PyInstaller.utils.hooks import collect_submodules
import os

# spec 内的相对路径以 spec 文件所在目录为基准
ROOT = os.path.dirname(SPECPATH)          # 仓库根
ASSETS = os.path.join(ROOT, "assets")

datas = [
    (os.path.join(ROOT, "src", "deli_eplus", "web"), "deli_eplus/web"),
]

hiddenimports = (
    collect_submodules("uiautomator2")
    + collect_submodules("adbutils")
    + collect_submodules("deli_eplus")
    + collect_submodules("webview")
    + ["clr_loader", "pythonnet"]
)

# 体积裁剪：标准库里确定用不到的模块 + 不需要的 PIL 编解码器 + 误打入的打包工具
excludes = [
    "unittest", "pydoc_data", "test", "xmlrpc",
    "matplotlib", "numpy", "scipy", "pandas",
    "PIL._avif",          # AVIF 编解码，8MB，签到截图用不到
    "setuptools", "pkg_resources",
    "tkinter",            # 前端已换 pywebview，tk 全家不再需要
]


a = Analysis(
    [os.path.join(SPECPATH, "run_gui.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Deli_EPlus_AutoSignUp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Deli_EPlus_AutoSignUp",
)
