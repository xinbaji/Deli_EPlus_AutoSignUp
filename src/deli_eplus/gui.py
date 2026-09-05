"""图形界面入口：python -m deli_eplus.gui（打包 exe 的启动点）。"""

import sys


def main() -> int:
    from .log import setup as setup_log

    setup_log()
    from .webui import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
