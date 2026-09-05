"""python -m deli_eplus 默认进入命令行签到；图形界面用 python -m deli_eplus.gui。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
