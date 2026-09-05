"""得力E+ 自动签到工具。

分层结构：
- device/  设备与模拟器操作（可独立复用，不依赖业务）
- core/    签到业务流程（唯一实现，GUI 与 CLI 共用）
- webui.py 图形界面（pywebview + WebView2，前端在 web/）
"""

APP_NAME = "得力E+ 自动签到"
VERSION = "1.2.0"
AUTHOR = "xinbaji"
REPO_URL = "https://github.com/xinbaji/Deli_EPlus_AutoSignUp"

__version__ = VERSION
