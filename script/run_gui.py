"""PyInstaller 打包入口：打包后的 exe 从这里进入 GUI。"""

import sys

from deli_eplus.gui import main

if __name__ == "__main__":
    sys.exit(main())
