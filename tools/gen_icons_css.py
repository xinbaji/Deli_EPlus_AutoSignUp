"""重新生成 web/icons.css（Bootstrap Icons 子集）。

用法：.venv/Scripts/python tools/gen_icons_css.py
改 ICONS 列表后运行即可，无需任何构建步骤。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLYPHS = json.loads((ROOT / "assets/fonts/bootstrap-icons.json").read_text("utf-8"))

ICONS = [
    "house-door", "people", "gear", "lightning-charge-fill",
    "moon-stars", "sun", "play-fill", "stop-fill", "folder2-open",
    "clock-history", "exclamation-triangle-fill", "box-arrow-up",
    "box-arrow-down", "plus-lg", "eye", "eye-slash", "pencil", "trash3",
    "sliders", "pc-display", "geo-alt", "bug-fill", "info-circle",
    "check-circle-fill", "x-circle-fill", "arrow-right-short",
    "hourglass-split", "search",
]


def main() -> None:
    missing = [n for n in ICONS if n not in GLYPHS]
    assert not missing, f"missing glyphs: {missing}"
    lines = [
        "/* 由 tools/gen_icons_css.py 生成：Bootstrap Icons 子集字形",
        "   字体文件随应用分发（web/fonts/bootstrap-icons.ttf） */",
        "@font-face {",
        "  font-family: 'bootstrap-icons';",
        "  src: url('fonts/bootstrap-icons.ttf') format('truetype');",
        "  font-weight: normal; font-style: normal; font-display: block;",
        "}",
        ".bi { font-family: 'bootstrap-icons'; font-style: normal;",
        "      line-height: 1; display: inline-block; vertical-align: -0.125em; }",
    ]
    for name in ICONS:
        code = int(GLYPHS[name])
        lines.append(f".bi-{name}::before {{ content: '\\{code:X}'; }}")
    out = ROOT / "src/deli_eplus/web/icons.css"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{out}: {len(ICONS)} icons")


if __name__ == "__main__":
    main()
