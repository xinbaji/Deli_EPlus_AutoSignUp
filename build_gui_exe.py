"""
GUI 打包为 EXE 脚本
使用 PyInstaller 将 gui.py 打包为独立的 Windows 可执行文件
默认：单文件、隐藏控制台、压缩格式

用法:
    python build_gui_exe.py
"""

import os
import sys
import shutil
import subprocess

# ---------- 路径配置 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "Deli_EPlus_AutoSignUp"))
GUI_SCRIPT = os.path.join(PROJECT_DIR, "gui.py")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "dist")       # 输出到 debug/dist
EXE_NAME = "Deli_EPlus_AutoSignUp"

# 入口脚本所在目录内需要随 exe 一起分发的文件/目录
DATA_FILES = [
    # (源路径, 目标目录名)
    (os.path.join(PROJECT_DIR, "emulator"), "emulator"),
    (os.path.join(PROJECT_DIR, "Setting.py"), "."),
    (os.path.join(PROJECT_DIR, "Log.py"), "."),
    (os.path.join(PROJECT_DIR, "deliSignup.py"), "."),
]

# PyInstaller 隐藏导入
HIDDEN_IMPORTS = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    "uiautomator2",
    "uiautomator2.ext",
    "uiautomator2.xpath",
    "uiautomator2.watch",
    "uiautomator2.session",
    "uiautomator2._archived",
    "uiautomator2.image",
    "uiautomator2.screenrecord",
    "uiautomator2.screenshot",
    "adbutils",
    "adbutils._adb",
    "adbutils._device",
    "adbutils.shell",
    "lxml",
    "lxml.etree",
    "lxml._elementpath",
    "requests",
    "urllib3",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "json",
    "datetime",
    "threading",
    "queue",
    "traceback",
    "ctypes",
    "subprocess",
    "logging",
    "http.server",
    "xml",
    "xml.etree",
    "xml.etree.ElementTree",
    "retry",
    "decorator",
    "progress",
    "apkutils2",
    "cigam",
]

COLLECT_ALL = [
    "uiautomator2",
    "adbutils",
]


def check_prerequisites():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__} 已安装")
    except ImportError:
        print("[ERROR] PyInstaller 未安装，请先执行: pip install pyinstaller")
        sys.exit(1)

    if not os.path.isfile(GUI_SCRIPT):
        print(f"[ERROR] 未找到 GUI 入口脚本: {GUI_SCRIPT}")
        sys.exit(1)

    print(f"[OK] 项目目录: {PROJECT_DIR}")
    print(f"[OK] GUI 入口: {GUI_SCRIPT}")


def clean_build():
    """清理之前的构建缓存"""
    paths_to_clean = [
        os.path.join(SCRIPT_DIR, "build"),
        os.path.join(SCRIPT_DIR, "__pycache__"),
    ]
    for p in paths_to_clean:
        if os.path.exists(p):
            print(f"[CLEAN] 删除 {p}")
            shutil.rmtree(p, ignore_errors=True)

    for f in os.listdir(SCRIPT_DIR):
        if f.endswith(".spec"):
            fp = os.path.join(SCRIPT_DIR, f)
            print(f"[CLEAN] 删除 {fp}")
            os.remove(fp)


def build_exe():
    """调用 PyInstaller 打包"""

    check_prerequisites()
    clean_build()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---------- 构建 PyInstaller 命令 ----------
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--distpath", OUTPUT_DIR,
        "--workpath", os.path.join(SCRIPT_DIR, "build"),
        "--specpath", SCRIPT_DIR,
        "--name", EXE_NAME,
        "--onefile",            # 单文件模式
        "--windowed",           # 隐藏控制台
        "--clean",              # 清理 PyInstaller 缓存
        "--noconfirm",          # 不询问确认，直接覆盖
    ]

    # 图标（如果存在）
    icon_path = os.path.join(PROJECT_DIR, "icon.ico")
    if os.path.isfile(icon_path):
        cmd += ["--icon", icon_path]
        print(f"[INFO] 使用图标: {icon_path}")

    # 添加数据文件
    for src, dst in DATA_FILES:
        if os.path.exists(src):
            sep = ";" if sys.platform == "win32" else ":"
            cmd += ["--add-data", f"{src}{sep}{dst}"]
            print(f"[INFO] 添加数据: {src} -> {dst}")

    # 隐藏导入
    for imp in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", imp]

    # collect-all
    for pkg in COLLECT_ALL:
        cmd += ["--collect-all", pkg]

    # 入口脚本
    cmd.append(GUI_SCRIPT)

    # ---------- 执行 ----------
    print(f"\n{'=' * 60}")
    print("开始打包...")
    print(f"模式: 单文件 | 控制台: 隐藏 | 压缩: 开启")
    print(f"输出: {OUTPUT_DIR}")
    print(f"{'=' * 60}\n")

    result = subprocess.run(cmd, cwd=SCRIPT_DIR)

    if result.returncode == 0:
        exe_path = os.path.join(OUTPUT_DIR, f"{EXE_NAME}.exe")
        print(f"\n{'=' * 60}")
        print("打包成功！")
        print(f"输出文件: {exe_path}")
        if os.path.isfile(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"文件大小: {size_mb:.1f} MB")
        print(f"{'=' * 60}")
    else:
        print("\n[ERROR] 打包失败！请检查上方错误信息。")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build_exe()
