"""调试工具：dump 当前设备界面层级到 tools/xml/，用于排查选择器。

用法：.venv/Scripts/python tools/dump_ui.py [serial]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> int:
    serial = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:16384"

    import uiautomator2 as u2

    device = u2.connect(serial)
    xml = device.dump_hierarchy()

    out_dir = Path(__file__).parent / "xml"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"ui_hierarchy_{time.strftime('%Y%m%d_%H%M%S')}.xml"
    out_file.write_text(xml, encoding="utf-8")
    print(f"已保存: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
