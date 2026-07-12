"""
导出模拟器当前页面 UI 层级为 XML 文件
使用 uiautomator2 连接模拟器，将当前界面的元素树导出为 XML
"""

import os
import sys
import json
from datetime import datetime

import uiautomator2 as u2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "Deli_EPlus_AutoSignUp"))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
DEFAULT_OUTPUT_DIR = SCRIPT_DIR


def load_serial():
    """从 config.json 读取模拟器 serial"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("serial", "127.0.0.1:16384")
        except (json.JSONDecodeError, IOError):
            pass
    return "127.0.0.1:16384"


def dump_ui_hierarchy(output_path: str = None, serial: str = None) -> str:
    """连接模拟器并导出当前页面 UI 层级为 XML 文件

    Args:
        output_path: XML 输出路径，为 None 则自动生成到脚本目录
        serial: 模拟器 serial，为 None 则从 config.json 读取

    Returns:
        导出的 XML 文件路径
    """
    if serial is None:
        serial = load_serial()
    print(f"[INFO] 使用 serial: {serial}")
    
    # 生成输出路径
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(DEFAULT_OUTPUT_DIR,"xml", f"ui_hierarchy_{timestamp}.xml")

    # 连接设备
    print(f"[INFO] 正在连接模拟器...")
    device = u2.connect(serial)
    print(f"[INFO] 设备信息: {device.info}")

    # 导出 UI 层级
    xml_content = device.dump_hierarchy()
    print(f"[INFO] UI 层级获取成功，XML 长度: {len(xml_content)} 字符")

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"[INFO] UI 层级已导出到: {output_path}")
    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="导出模拟器当前页面 UI 层级为 XML 文件"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="XML 输出路径（默认: ui_hierarchy_YYYYMMDD_HHMMSS.xml）"
    )
    parser.add_argument(
        "-s", "--serial",
        default=None,
        help="模拟器 serial（默认从 config.json 读取）"
    )
    args = parser.parse_args()

    try:
        output_file = dump_ui_hierarchy(
            output_path=args.output,
            serial=args.serial
        )
        print(f"\n✅ 导出完成: {output_file}")
    except Exception as e:
        print(f"\n❌ 导出失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
