"""
打包脚本：将 gui.py 打包为单文件无控制台的 Windows EXE
用法：
    python buildexe.py                # 默认打包
    python buildexe.py --name xxx     # 自定义 exe 名称
    python buildexe.py --icon xxx.ico # 自定义图标
依赖：
    pip install pyinstaller
"""
import argparse
import os
import shutil
import sys

# ---------- 配置 ----------
ENTRY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.py")
DEFAULT_NAME = "Deli_EPlus_AutoSignUp"
WORK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")

# 动态导入或不易被 PyInstaller 静态分析捕获的模块
HIDDEN_IMPORTS = [
    "uiautomator2",
    "adbutils",
    "lxml",
    "PIL",
]


def parse_args():
    parser = argparse.ArgumentParser(description="打包 Deli E+ 自动签到为单文件无控制台 EXE")
    parser.add_argument("--name", default=DEFAULT_NAME, help="exe 名称（不含 .exe），默认 %(default)s")
    parser.add_argument("--icon", default=None, help="exe 图标 (.ico)，默认不使用图标")
    parser.add_argument("--clean", action="store_true", help="打包前清理 build/dist 目录")
    parser.add_argument("--no-confirm", action="store_true", help="覆盖已存在的 exe 时无需确认")
    return parser.parse_args()


def build(args):
    # 清理旧产物
    if args.clean:
        for d in (WORK_DIR, DIST_DIR):
            if os.path.isdir(d):
                shutil.rmtree(d)
                print(f"[清理] {d}")

    pyi_args = [
        "--onefile",                 # 单文件
        "--noconsole",               # 无控制台窗口
        "--noconfirm",
        "--name", args.name,
        "--workpath", WORK_DIR,
        "--distpath", DIST_DIR,
        "--specpath", WORK_DIR,
    ]
    # 自动打包 uiautomator2 的 assets 资源（u2.jar 等），否则运行时找不到
    try:
        import uiautomator2 as _u2
        _u2_dir = os.path.dirname(_u2.__file__)
        _assets_src = os.path.join(_u2_dir, "assets")
        if os.path.isdir(_assets_src):
            sep = ";" if sys.platform == "win32" else ":"
            pyi_args += ["--add-data", f"{_assets_src}{sep}uiautomator2/assets"]
            print(f"[资源] 加入 uiautomator2/assets: {_assets_src}")
    except ImportError:
        print("[警告] 未找到 uiautomator2，跳过 assets 资源打包")

    if args.icon:
        pyi_args += ["--icon", args.icon]
    for mod in HIDDEN_IMPORTS:
        pyi_args += ["--hidden-import", mod]
    pyi_args.append(ENTRY_SCRIPT)

    print("[执行] PyInstaller " + " ".join(pyi_args))
    import PyInstaller.__main__

    try:
        PyInstaller.__main__.run(pyi_args)
    except PermissionError as e:
        print(f"\n[错误] 无法覆盖 {e.filename}")
        print("       可能原因：exe 正在运行、被杀毒软件占用或无写入权限。")
        print("       请先关闭正在运行的 Deli_EPlus_AutoSignUp.exe 后重试。")
        sys.exit(1)

    exe_path = os.path.join(DIST_DIR, args.name + ".exe")
    if os.path.isfile(exe_path):
        print(f"\n[完成] 打包成功：{exe_path}")
        print(f"       大小：{os.path.getsize(exe_path) / 1024 / 1024:.1f} MB")
    else:
        print("\n[失败] 未找到输出文件，请查看上方报错信息")
        sys.exit(1)


if __name__ == "__main__":
    args = parse_args()
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[错误] 未安装 pyinstaller，请先执行：pip install pyinstaller")
        sys.exit(1)
    build(args)
