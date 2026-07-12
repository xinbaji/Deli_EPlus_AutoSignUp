"""
得力 E+ 自动签到 GUI
基于 tkinter，Win11 风格，系统默认标题栏，左侧垂直导航栏
四选项卡（主页 / 用户管理 / 设置 / 日志）
"""
import ctypes
import sys
import os

# ---------- Windows DPI 感知（必须在创建任何 tk 窗口前调用） ----------
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except AttributeError:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import traceback
import datetime

# PyInstaller 打包后使用 EXE 所在目录，开发环境使用脚本所在目录
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from Setting import DEFAULT_CONFIG, CONFIG_PATH, load_config, save_config, reload_config
from Log import Log
from deliSignup import Deli


# ---------- 字体（整体放大） ----------
def _get_fonts():
    if sys.platform == "win32":
        return {
            "UI_FONT":       ("Microsoft YaHei UI", 12),
            "UI_FONT_SM":    ("Microsoft YaHei UI", 11),
            "UI_FONT_XS":    ("Microsoft YaHei UI", 10),
            "UI_FONT_BOLD":  ("Microsoft YaHei UI", 16, "bold"),
            "UI_FONT_TITLE": ("Microsoft YaHei UI", 15, "bold"),
            "UI_FONT_SECTION": ("Microsoft YaHei UI", 13, "bold"),
            "UI_FONT_NAV":   ("Microsoft YaHei UI", 12),
            "UI_FONT_NAV_ACTIVE": ("Microsoft YaHei UI", 12, "bold"),
            "MONO_FONT":     ("Cascadia Code", 10),
            "BUTTON_FONT":   ("Microsoft YaHei UI", 11),
            "SIDEBAR_TITLE": ("Microsoft YaHei UI", 20, "bold"),
            "SIDEBAR_SUB":   ("Microsoft YaHei UI", 14),
            "CTRL_FONT":     ("Microsoft YaHei UI", 13),
        }
    return {
        "UI_FONT":       ("Segoe UI", 12),
        "UI_FONT_SM":    ("Segoe UI", 11),
        "UI_FONT_XS":    ("Segoe UI", 10),
        "UI_FONT_BOLD":  ("Segoe UI", 16, "bold"),
        "UI_FONT_TITLE": ("Segoe UI", 15, "bold"),
        "UI_FONT_SECTION": ("Segoe UI", 13, "bold"),
        "UI_FONT_NAV":   ("Segoe UI", 12),
        "UI_FONT_NAV_ACTIVE": ("Segoe UI", 12, "bold"),
        "MONO_FONT":     ("Consolas", 10),
        "BUTTON_FONT":   ("Segoe UI", 11),
        "SIDEBAR_TITLE": ("Segoe UI", 20, "bold"),
        "SIDEBAR_SUB":   ("Segoe UI", 14),
        "CTRL_FONT":     ("Segoe UI", 13),
    }

_FONTS = _get_fonts()
UI_FONT       = _FONTS["UI_FONT"]
UI_FONT_SM    = _FONTS["UI_FONT_SM"]
UI_FONT_XS    = _FONTS["UI_FONT_XS"]
UI_FONT_BOLD  = _FONTS["UI_FONT_BOLD"]
UI_FONT_TITLE = _FONTS["UI_FONT_TITLE"]
UI_FONT_SECTION = _FONTS["UI_FONT_SECTION"]
UI_FONT_NAV   = _FONTS["UI_FONT_NAV"]
UI_FONT_NAV_ACTIVE = _FONTS["UI_FONT_NAV_ACTIVE"]
MONO_FONT     = _FONTS["MONO_FONT"]
BUTTON_FONT   = _FONTS["BUTTON_FONT"]
SIDEBAR_TITLE = _FONTS["SIDEBAR_TITLE"]
SIDEBAR_SUB   = _FONTS["SIDEBAR_SUB"]
CTRL_FONT     = _FONTS["CTRL_FONT"]


# ---------- Win11 配色 ----------
class Win11Colors:
    BG = "#f3f3f3"
    CARD_BG = "#ffffff"
    SIDEBAR_BG = "#e8e8e8"
    ACCENT = "#0067c0"
    ACCENT_HOVER = "#0056a3"
    ACCENT_LIGHT = "#e6f0fa"
    TEXT_PRIMARY = "#1a1a1a"
    TEXT_SECONDARY = "#5c5c5c"
    TEXT_HINT = "#a0a0a0"
    BORDER = "#d1d1d1"
    SUCCESS = "#10893e"
    ERROR = "#c42b1c"
    WARNING = "#ff8c00"
    SEPARATOR = "#e0e0e0"
    INPUT_BG = "#ffffff"
    INPUT_BORDER = "#d1d1d1"
    INPUT_FOCUS = "#0067c0"
    BTN_PRIMARY_TEXT = "#ffffff"
    NAV_BG = "#e8e8e8"
    NAV_HOVER_BG = "#dcdcdc"
    NAV_ACTIVE_BG = "#f0f6ff"
    PROGRESS_BG = "#e0e0e0"
    STEP_BG = "#f0f6ff"
    SAVE_IDLE = "#a0a0a0"
    SAVE_OK = "#10893e"
    SAVE_DIRTY = "#ff8c00"





# ---------- 动画工具 ----------
def _lerp_color(c1, c2, t):
    """在两个 HEX 颜色之间线性插值"""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _animate(widget, attr, start, end, duration_ms=200, steps=20, after_cb=None):
    """通用属性动画（颜色或数值）"""
    def _step(i=0):
        if not widget.winfo_exists():
            return
        t = i / steps
        # ease-in-out
        t = t * t * (3 - 2 * t)
        if isinstance(start, int):
            val = int(start + (end - start) * t)
        else:
            val = _lerp_color(start, end, t)
        widget.config(**{attr: val})
        if i < steps:
            widget.after(duration_ms // steps, _step, i + 1)
        elif after_cb:
            after_cb()
    _step(0)


# ---------- 组件 ----------
class Win11Entry(tk.Frame):
    def __init__(self, parent, placeholder="", width=30, show=None, password_toggle=False, **kwargs):
        super().__init__(parent, bg=Win11Colors.CARD_BG)
        self._placeholder = placeholder
        self._has_placeholder = bool(placeholder)
        self._placeholder_active = False
        self._show_char = show
        self._password_visible = False
        self._password_toggle = password_toggle
        self._toggle_btn = None

        entry_kwargs = {
            "width": width, "font": UI_FONT,
            "bg": Win11Colors.INPUT_BG, "fg": Win11Colors.TEXT_PRIMARY,
            "insertbackground": Win11Colors.TEXT_PRIMARY,
            "relief": "flat", "bd": 0, "highlightthickness": 1,
            "highlightbackground": Win11Colors.INPUT_BORDER,
            "highlightcolor": Win11Colors.INPUT_FOCUS,
        }
        entry_kwargs.update(kwargs)
        if show is not None:
            entry_kwargs["show"] = show

        # 如果是密码框且需要切换按钮，用内层 frame 容纳 entry + 按钮
        if password_toggle:
            self._entry_frame = tk.Frame(self, bg=Win11Colors.CARD_BG)
            self._entry_frame.pack(fill="x")
            self.entry = tk.Entry(self._entry_frame, **entry_kwargs)
            self.entry.pack(side="left", fill="x", expand=True, ipady=6)

            self._toggle_btn = tk.Label(
                self._entry_frame,
                text="\U0001f441",  # 👁
                font=("Segoe UI Symbol", 12) if sys.platform == "win32" else ("Segoe UI", 12),
                bg=Win11Colors.INPUT_BG, fg=Win11Colors.TEXT_HINT,
                cursor="hand2", width=2, anchor="center",
            )
            self._toggle_btn.pack(side="right", ipady=5, padx=(0, 4))
            self._toggle_btn.bind("<Button-1>", lambda e: self._toggle_password())
            self._toggle_btn.bind("<Enter>", lambda e: self._toggle_btn.config(fg=Win11Colors.TEXT_PRIMARY))
            self._toggle_btn.bind("<Leave>", lambda e: self._toggle_btn.config(fg=Win11Colors.TEXT_HINT))
        else:
            self.entry = tk.Entry(self, **entry_kwargs)
            self.entry.pack(fill="x", ipady=6)

        if placeholder:
            self._show_placeholder()
            self.entry.bind("<FocusIn>", self._on_focus_in)
            self.entry.bind("<FocusOut>", self._on_focus_out)

    def _toggle_password(self):
        self._password_visible = not self._password_visible
        if self._password_visible:
            self.entry.config(show="")
            self._toggle_btn.config(text="\U0001f576", fg=Win11Colors.ACCENT)  # 🕶
        else:
            self.entry.config(show=self._show_char or "*")
            self._toggle_btn.config(text="\U0001f441", fg=Win11Colors.TEXT_HINT)  # 👁

    def _show_placeholder(self):
        if not self.entry.get():
            self.entry.config(fg=Win11Colors.TEXT_HINT)
            self.entry.insert(0, self._placeholder)
            self._placeholder_active = True

    def _on_focus_in(self, event):
        if self._placeholder_active:
            self.entry.delete(0, "end")
            self.entry.config(fg=Win11Colors.TEXT_PRIMARY)
            self._placeholder_active = False

    def _on_focus_out(self, event):
        if self._has_placeholder and not self.entry.get():
            self._show_placeholder()

    def get(self):
        if self._placeholder_active:
            return ""
        return self.entry.get()

    def set(self, value):
        self._placeholder_active = False
        self.entry.delete(0, "end")
        if value:
            self.entry.config(fg=Win11Colors.TEXT_PRIMARY)
            self.entry.insert(0, value)
        elif self._has_placeholder:
            self._show_placeholder()


class Win11Button(tk.Button):
    def __init__(self, parent, text, command=None, style="primary", **kwargs):
        if style == "primary":
            bg, fg, hover_bg = Win11Colors.ACCENT, Win11Colors.BTN_PRIMARY_TEXT, Win11Colors.ACCENT_HOVER
        elif style == "danger":
            bg, fg, hover_bg = Win11Colors.ERROR, "#ffffff", "#a01e16"
        elif style == "outline":
            bg, fg, hover_bg = Win11Colors.CARD_BG, Win11Colors.ACCENT, Win11Colors.ACCENT_LIGHT
        else:
            bg, fg, hover_bg = Win11Colors.CARD_BG, Win11Colors.TEXT_PRIMARY, "#e8e8e8"

        super().__init__(
            parent, text=text, command=command, font=BUTTON_FONT,
            bg=bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
            relief="flat", bd=0, padx=20, pady=6, cursor="hand2", **kwargs,
        )
        self._default_bg = bg
        self._hover_bg = hover_bg
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self.config(bg=self._hover_bg)

    def _on_leave(self, event):
        self.config(bg=self._default_bg)


class NavButton(tk.Frame):
    """导航按钮 - 图标和文字垂直居中对齐，固定列宽"""

    ICON_W = 32   # 图标列宽度（像素）
    PAD_L = 8     # 左边距
    PAD_R = 12    # 右边距

    def __init__(self, parent, text, icon_char, command, **kwargs):
        super().__init__(parent, bg=Win11Colors.NAV_BG, cursor="hand2",
                         height=46, **kwargs)
        self._command = command
        self._active = False

        self.pack_propagate(False)
        self.grid_propagate(False)

        # 左侧指示条
        self._indicator = tk.Frame(self, bg=Win11Colors.NAV_BG, width=4)
        self._indicator.pack(side="left", fill="y")

        # 图标+文字的内层容器
        self._inner_bg = Win11Colors.NAV_BG
        self._inner = tk.Frame(self, bg=self._inner_bg)
        self._inner.pack(side="left", fill="both", expand=True, padx=(self.PAD_L, self.PAD_R))

        # 图标标签 - 固定像素宽度确保对齐，width=2 保证等宽字符列
        icon_font = ("Segoe UI Symbol", 14) if sys.platform == "win32" else ("Segoe UI", 14)
        self._icon_label = tk.Label(
            self._inner,
            text=icon_char,
            font=icon_font,
            bg=self._inner_bg, fg=Win11Colors.TEXT_PRIMARY,
            width=3, anchor="w",
        )
        self._icon_label.pack(side="left", pady=10)

        # 文字标签 - 固定左边距确保文字列对齐
        self._text_label = tk.Label(
            self._inner,
            text=text,
            font=UI_FONT_NAV,
            bg=self._inner_bg, fg=Win11Colors.TEXT_PRIMARY,
            anchor="w",
        )
        self._text_label.pack(side="left", fill="both", expand=True, pady=10, padx=(6, 0))

        # 事件绑定
        for w in (self, self._inner, self._icon_label, self._text_label, self._indicator):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        if not self._active:
            bg = Win11Colors.NAV_HOVER_BG
            self._inner.config(bg=bg)
            self._icon_label.config(bg=bg)
            self._text_label.config(bg=bg)

    def _on_leave(self, event):
        if not self._active:
            bg = Win11Colors.NAV_BG
            self._inner.config(bg=bg)
            self._icon_label.config(bg=bg)
            self._text_label.config(bg=bg)

    def _on_click(self, event):
        self._command()

    def set_active(self, active):
        self._active = active
        if active:
            bg = Win11Colors.NAV_ACTIVE_BG
            self._inner.config(bg=bg)
            self._icon_label.config(bg=bg, fg=Win11Colors.ACCENT)
            self._text_label.config(bg=bg, fg=Win11Colors.ACCENT, font=UI_FONT_NAV_ACTIVE)
            self._indicator.config(bg=Win11Colors.ACCENT)
        else:
            bg = Win11Colors.NAV_BG
            self._inner.config(bg=bg)
            self._icon_label.config(bg=bg, fg=Win11Colors.TEXT_PRIMARY)
            self._text_label.config(bg=bg, fg=Win11Colors.TEXT_PRIMARY, font=UI_FONT_NAV)
            self._indicator.config(bg=Win11Colors.NAV_BG)


class ScrollableFrame(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, bg=Win11Colors.BG, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=Win11Colors.BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self._window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮
        self._bind_mousewheel()

    def _bind_mousewheel(self):
        self.canvas.bind("<Enter>", self._on_enter_canvas)
        self.canvas.bind("<Leave>", self._on_leave_canvas)

    def _on_enter_canvas(self, event):
        if sys.platform == "win32":
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel_win)
        else:
            self.canvas.bind_all("<Button-4>", self._on_mousewheel_lin)
            self.canvas.bind_all("<Button-5>", self._on_mousewheel_lin)

    def _on_leave_canvas(self, event):
        if sys.platform == "win32":
            self.canvas.unbind_all("<MouseWheel>")
        else:
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel_win(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_lin(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._window, width=event.width)


# ---------- 主应用 ----------
class DeliSignupApp:
    SIDEBAR_WIDTH = 230       # 侧边栏加宽
    WIN_W = 1100              # 窗口宽度（加大）
    WIN_H = 780               # 窗口高度（加大）

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("得力 E+ 自动签到")
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}")
        self.root.minsize(900, 650)
        self.root.configure(bg=Win11Colors.BG)
        self._center_window()

        # 签到状态
        self._sign_thread = None
        self._log_queue = queue.Queue()
        self._log_buffer = []  # 日志缓冲区，确保消息不丢失
        self._deli_instance = None
        self._user_rows = []
        self._current_page = None
        self._sign_started = False

        reload_config()
        Log.add_gui_callback(self._on_log)

        self._build_ui()
        self._poll_log_queue()

        # 设置关闭协议
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - self.WIN_W) // 2
        y = (sh - self.WIN_H) // 2
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}+{x}+{y}")

    # ==================== 构建 UI ====================
    def _build_ui(self):
        # ---- 主体容器 ----
        body = tk.Frame(self.root, bg=Win11Colors.BG)
        body.pack(fill="both", expand=True)

        # ---- 左侧侧边栏 ----
        self._build_sidebar(body)

        # ---- 分隔线 ----
        tk.Frame(body, bg=Win11Colors.SEPARATOR, width=1).pack(side="left", fill="y")

        # ---- 右侧内容区 ----
        self.content_frame = tk.Frame(body, bg=Win11Colors.BG)
        self.content_frame.pack(side="left", fill="both", expand=True)

        self._show_page("home")

    def _build_sidebar(self, parent):
        """左侧侧边栏：标题 → 状态 → 分隔线 → 导航"""
        sidebar = tk.Frame(parent, bg=Win11Colors.NAV_BG, width=self.SIDEBAR_WIDTH)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # ---- 应用标题（大字体） ----
        title_lbl = tk.Label(
            sidebar,
            text="得力 E+",
            font=SIDEBAR_TITLE,
            bg=Win11Colors.NAV_BG, fg=Win11Colors.ACCENT,
        )
        title_lbl.pack(anchor="w", padx=22, pady=(24, 0))

        subtitle_lbl = tk.Label(
            sidebar,
            text="自动签到",
            font=SIDEBAR_SUB,
            bg=Win11Colors.NAV_BG, fg=Win11Colors.TEXT_PRIMARY,
        )
        subtitle_lbl.pack(anchor="w", padx=22, pady=(0, 6))

        # ---- 状态指示器 ----
        self.status_label = tk.Label(
            sidebar,
            text="● 就绪",
            font=UI_FONT_SM,
            bg=Win11Colors.NAV_BG, fg=Win11Colors.TEXT_SECONDARY,
        )
        self.status_label.pack(anchor="w", padx=22, pady=(2, 10))

        # ---- 分隔线 ----
        sep_frame = tk.Frame(sidebar, bg=Win11Colors.NAV_BG)
        sep_frame.pack(fill="x", padx=14, pady=(4, 10))
        sep_canvas = tk.Canvas(sep_frame, bg=Win11Colors.NAV_BG, height=1,
                               highlightthickness=0, bd=0)
        sep_canvas.pack(fill="x")
        sep_canvas.create_line(0, 0, 400, 0, fill=Win11Colors.SEPARATOR, width=1)

        # ---- 导航按钮 ----
        # 图标：每个按钮左边用统一宽度的 Unicode 字符
        # 使用几何符号确保视觉宽度一致
        self.nav_buttons = {}
        tabs = [
            ("home",     "主页",      "\U0001f3e0"),  # 🏠
            ("users",    "用户管理",  "\U0001f465"),  # 👥
            ("settings", "设置",      "\u2699\ufe0f"),  # ⚙️
            ("log",      "日志",      "\U0001f4c4"),  # 📄
        ]

        for key, label, icon in tabs:
            btn = NavButton(
                sidebar,
                text=label,
                icon_char=icon,
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[key] = btn

        # ---- 底部弹性空间 ----
        spacer = tk.Frame(sidebar, bg=Win11Colors.NAV_BG)
        spacer.pack(fill="both", expand=True)

    # ==================== 窗口操作 ====================
    def _on_close(self):
        if self._sign_thread and self._sign_thread.is_alive():
            if self._deli_instance:
                self._deli_instance.stop()
        self.root.destroy()

    # ==================== 页面切换 ====================
    def _show_page(self, page_key):
        self._current_page = page_key
        for w in self.content_frame.winfo_children():
            w.destroy()

        for key, btn in self.nav_buttons.items():
            btn.set_active(key == page_key)

        if page_key == "home":
            self._build_home_page()
        elif page_key == "users":
            self._build_users_page()
        elif page_key == "settings":
            self._build_settings_page()
        elif page_key == "log":
            self._build_log_page()

    # ==================== 主页（签到 + 进度） ====================
    def _build_home_page(self):
        page = tk.Frame(self.content_frame, bg=Win11Colors.BG)
        page.pack(fill="both", expand=True)

        # ---- 签到控制区（含按钮） ----
        card = tk.Frame(page, bg=Win11Colors.CARD_BG, bd=0,
                        highlightthickness=1, highlightbackground=Win11Colors.BORDER)
        card.pack(fill="x", padx=20, pady=(20, 12))

        card_inner = tk.Frame(card, bg=Win11Colors.CARD_BG)
        card_inner.pack(fill="x", padx=20, pady=18)

        # 标题行
        title_row = tk.Frame(card_inner, bg=Win11Colors.CARD_BG)
        title_row.pack(fill="x")

        tk.Label(
            title_row, text="签到控制台",
            font=UI_FONT_BOLD,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_PRIMARY,
        ).pack(side="left")

        # 状态徽章
        self.sign_status_badge = tk.Label(
            title_row,
            text="等待开始",
            font=UI_FONT_SM,
            bg=Win11Colors.STEP_BG, fg=Win11Colors.ACCENT,
            padx=12, pady=2,
        )
        self.sign_status_badge.pack(side="right")

        # 用户预览
        self._update_user_preview(card_inner)

        # 调试模式提示条
        cfg = load_config()
        if cfg.get("debugmode", True):
            debug_banner = tk.Frame(card_inner, bg="#fff4e5",
                                    highlightthickness=1, highlightbackground=Win11Colors.WARNING,
                                    bd=0)
            debug_banner.pack(fill="x", pady=(12, 0))
            tk.Label(
                debug_banner,
                text="⚠ 调试模式已开启：签到将不会进行实际打卡",
                font=UI_FONT_SM,
                bg="#fff4e5", fg="#b25e00",
                anchor="w", justify="left",
            ).pack(fill="x", padx=14, pady=10)

        # 按钮行（在卡片内部）
        btn_row = tk.Frame(card_inner, bg=Win11Colors.CARD_BG)
        btn_row.pack(fill="x", pady=(12, 0))

        self.start_btn = Win11Button(btn_row, text="▶  开始签到", command=self._start_sign, style="primary")
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = Win11Button(btn_row, text="■  停止签到", command=self._stop_sign, style="danger")
        self.stop_btn.pack(side="left")
        self.stop_btn.config(state="disabled")

        # ---- 步骤进度区 ----
        step_card = tk.Frame(page, bg=Win11Colors.CARD_BG, bd=0,
                             highlightthickness=1, highlightbackground=Win11Colors.BORDER)
        step_card.pack(fill="x", padx=20, pady=(0, 16))

        step_inner = tk.Frame(step_card, bg=Win11Colors.CARD_BG)
        step_inner.pack(fill="x", padx=20, pady=16)

        # 步骤标题
        tk.Label(
            step_inner,
            text="执行进度",
            font=UI_FONT_SECTION,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 8))

        # 当前操作 + 步骤数字（同一行）
        action_row = tk.Frame(step_inner, bg=Win11Colors.CARD_BG)
        action_row.pack(fill="x", pady=(0, 8))

        self.current_action_label = tk.Label(
            action_row,
            text="等待开始签到...",
            font=UI_FONT,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_SECONDARY,
            anchor="w", justify="left",
        )
        self.current_action_label.pack(side="left")

        self.step_number_label = tk.Label(
            action_row,
            text="",
            font=("Microsoft YaHei UI", 14, "bold") if sys.platform == "win32" else ("Segoe UI", 14, "bold"),
            bg=Win11Colors.CARD_BG, fg=Win11Colors.ACCENT,
        )
        self.step_number_label.pack(side="right", padx=(12, 0))

        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            step_inner,
            variable=self.progress_var,
            mode="determinate",
            length=400,
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))

        # 百分比文字
        self.progress_pct_label = tk.Label(
            step_inner,
            text="0%",
            font=UI_FONT_XS,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_HINT,
        )
        self.progress_pct_label.pack(anchor="e")

        # ---- 错误信息区（初始隐藏）----
        self._build_error_block(page)

        # ---- 底部弹性空间 ----
        spacer = tk.Frame(page, bg=Win11Colors.BG)
        spacer.pack(fill="both", expand=True)

    def _update_user_preview(self, parent):
        cfg = load_config()
        users = cfg.get("users", {})
        if users:
            count = len(users)
            names = "\u3001".join(list(users.keys())[:3])
            if count > 3:
                names += f" 等{count}人"
            txt = f"待签到用户: {names}"
        else:
            txt = "未配置用户，请前往「用户管理」添加"
        if hasattr(self, '_user_preview_label') and self._user_preview_label.winfo_exists():
            self._user_preview_label.config(text=txt)
        else:
            self._user_preview_label = tk.Label(
                parent, text=txt, font=UI_FONT_SM,
                bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_SECONDARY,
            )
            self._user_preview_label.pack(anchor="w", pady=(8, 0))

    # ==================== 错误信息块 ====================
    def _build_error_block(self, parent):
        """在主页构建错误信息展示块（初始隐藏）"""
        self.error_card = tk.Frame(parent, bg=Win11Colors.CARD_BG, bd=0,
                                   highlightthickness=1, highlightbackground=Win11Colors.BORDER)

        error_inner = tk.Frame(self.error_card, bg=Win11Colors.CARD_BG)
        error_inner.pack(fill="x", padx=20, pady=16)

        # 标题：错误信息
        tk.Label(
            error_inner,
            text="错误信息",
            font=UI_FONT_SECTION,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.ERROR,
        ).pack(anchor="w", pady=(0, 8))

        # 错误描述（大字体）
        self.error_desc_label = tk.Label(
            error_inner,
            text="",
            font=("Microsoft YaHei UI", 13, "bold") if sys.platform == "win32" else ("Segoe UI", 13, "bold"),
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_PRIMARY,
            anchor="w", justify="left", wraplength=700,
        )
        self.error_desc_label.pack(fill="x", pady=(0, 6))

        # 解决方案（小字体）
        self.error_solution_label = tk.Label(
            error_inner,
            text="",
            font=UI_FONT_XS,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_SECONDARY,
            anchor="w", justify="left", wraplength=700,
        )
        self.error_solution_label.pack(fill="x", pady=(0, 10))

        # 底部行：错误栈按钮（右下角）
        btn_row = tk.Frame(error_inner, bg=Win11Colors.CARD_BG)
        btn_row.pack(fill="x")
        self.error_stack_btn = Win11Button(
            btn_row, text="显示错误栈",
            command=self._show_error_stack, style="outline"
        )
        self.error_stack_btn.pack(side="right")

        # 存储当前错误的 traceback
        self._error_traceback = ""

    def _show_error_block(self, error_msg, traceback_str=""):
        """显示错误信息块"""
        # 分析错误类型，给出中文描述和解决方案
        desc, solution = self._analyze_error(error_msg)
        self.error_desc_label.config(text=desc)
        self.error_solution_label.config(text=solution)
        self._error_traceback = traceback_str

        # 显示错误块
        self.error_card.pack(fill="x", padx=20, pady=(0, 16), before=self.error_card.master.winfo_children()[-1])

        # 如果没有 traceback，隐藏按钮
        if traceback_str:
            self.error_stack_btn.pack(side="right")
        else:
            self.error_stack_btn.pack_forget()

    def _hide_error_block(self):
        """隐藏错误信息块"""
        if hasattr(self, 'error_card') and self.error_card.winfo_exists():
            self.error_card.pack_forget()
        self._error_traceback = ""

    def _analyze_error(self, error_msg):
        """分析错误类型，返回 (中文描述, 解决方案)"""
        msg_lower = error_msg.lower() if error_msg else ""

        if "timeout" in msg_lower or "超时" in error_msg:
            return (
                f"签到超时：{error_msg}",
                "可能原因：网络连接不稳定、模拟器响应缓慢、或定位经纬度不准确。\n"
                "建议：检查模拟器网络连接，确认定位坐标在打卡范围内后重试。"
            )
        elif "连接" in error_msg or "connect" in msg_lower or "adb" in msg_lower:
            return (
                f"连接失败：{error_msg}",
                "可能原因：模拟器未启动、ADB 端口被占用、或模拟器路径配置错误。\n"
                "建议：确认 MuMu 模拟器已启动，检查 ADB 序列号是否正确，重启模拟器后重试。"
            )
        elif "定位" in error_msg or "location" in msg_lower or "虚拟位置" in error_msg:
            return (
                f"定位设置失败：{error_msg}",
                "可能原因：MuMuManager.exe 未找到、模拟器版本不支持虚拟定位、或权限不足。\n"
                "建议：确认 MuMu 模拟器路径正确，尝试以管理员权限运行程序。"
            )
        elif "shell output invalid" in msg_lower:
            return (
                f"应用启动异常：{error_msg}",
                "可能原因：模拟器 ADB Shell 返回格式异常，常见于 MuMu 模拟器。\n"
                "程序将持续重试启动，限时 90 秒。\n"
                "如持续失败，建议重启模拟器后重试。"
            )
        elif "应用" in error_msg or "app" in msg_lower or "start" in msg_lower:
            return (
                f"应用启动失败：{error_msg}",
                "可能原因：得力 E+ 应用未安装、应用包名变更、或模拟器存储空间不足。\n"
                "建议：确认模拟器中已安装得力 E+ 应用，检查应用是否可正常打开。"
            )
        elif "登录" in error_msg or "login" in msg_lower or "账号" in error_msg:
            return (
                f"登录失败：{error_msg}",
                "可能原因：账号或密码错误、应用界面变更导致元素定位失败。\n"
                "建议：检查账号密码是否正确，确认应用版本是否兼容，必要时更新元素定位。"
            )
        elif "中断" in error_msg or "interrupt" in msg_lower:
            return (
                "签到流程被用户中断",
                "已手动停止签到，如需重新签到请点击「开始签到」按钮。"
            )
        else:
            return (
                f"发生未知错误：{error_msg}",
                "请查看错误栈了解详细信息，或检查日志页面获取更多线索。"
            )

    def _show_error_stack(self):
        """弹出错误栈窗口"""
        if not self._error_traceback:
            messagebox.showinfo("提示", "暂无错误栈信息")
            return

        stack_win = tk.Toplevel(self.root)
        stack_win.title("错误栈详情")
        stack_win.geometry("750x450")
        stack_win.configure(bg=Win11Colors.BG)
        stack_win.transient(self.root)

        # 居中
        stack_win.update_idletasks()
        sw = stack_win.winfo_screenwidth()
        sh = stack_win.winfo_screenheight()
        w, h = 750, 450
        x, y = (sw - w) // 2, (sh - h) // 2
        stack_win.geometry(f"{w}x{h}+{x}+{y}")

        # 工具栏
        toolbar = tk.Frame(stack_win, bg=Win11Colors.BG)
        toolbar.pack(fill="x", padx=16, pady=(12, 6))

        tk.Label(
            toolbar, text="Python 错误栈",
            font=UI_FONT_SECTION,
            bg=Win11Colors.BG, fg=Win11Colors.TEXT_PRIMARY,
        ).pack(side="left")

        # 复制按钮
        def _copy_stack():
            stack_win.clipboard_clear()
            stack_win.clipboard_append(self._error_traceback)
            messagebox.showinfo("提示", "错误栈已复制到剪贴板", parent=stack_win)

        Win11Button(toolbar, text="复制", command=_copy_stack, style="secondary").pack(side="right")

        # 文本框
        text_frame = tk.Frame(stack_win, bg=Win11Colors.BG)
        text_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        text_widget = tk.Text(
            text_frame,
            font=MONO_FONT,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_PRIMARY,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=Win11Colors.BORDER,
            wrap="word",
        )
        text_widget.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        text_widget.config(yscrollcommand=scrollbar.set)

        text_widget.insert("1.0", self._error_traceback)
        text_widget.config(state="disabled")

        stack_win.focus_set()

    # ==================== 签到逻辑 ====================
    def _start_sign(self):
        cfg = load_config()
        if not cfg.get("users"):
            messagebox.showwarning("提示", "请先在「用户管理」中添加签到用户")
            self._show_page("users")
            return
        if not cfg.get("emulator_path"):
            messagebox.showwarning("提示", "请先在「设置」中配置 MuMu 模拟器路径")
            self._show_page("settings")
            return

        self._sign_started = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="● 签到中", fg=Win11Colors.ACCENT)
        self.sign_status_badge.config(text="运行中", bg=Win11Colors.ACCENT_LIGHT, fg=Win11Colors.ACCENT)

        # 隐藏之前的错误信息
        self._hide_error_block()

        # 重置进度
        self._update_step(0, 0, "正在初始化...", "")
        self.progress_var.set(0)
        self.progress_pct_label.config(text="0%")

        self._sign_thread = threading.Thread(target=self._run_signup, daemon=True)
        self._sign_thread.start()

    def _update_step(self, current, total, action_text, stage_text=""):
        """在主线程更新步骤进度"""
        def _do():
            if hasattr(self, 'step_number_label') and self.step_number_label.winfo_exists():
                if total > 0:
                    self.step_number_label.config(text=f"步骤 {current}/{total}")
                else:
                    self.step_number_label.config(text="")
            if hasattr(self, 'current_action_label') and self.current_action_label.winfo_exists():
                display_text = action_text
                if stage_text:
                    display_text = f"{stage_text} - {action_text}"
                self.current_action_label.config(text=display_text)
            if hasattr(self, 'progress_var') and total > 0:
                pct = (current / total) * 100
                self.progress_var.set(pct)
                if hasattr(self, 'progress_pct_label') and self.progress_pct_label.winfo_exists():
                    self.progress_pct_label.config(text=f"{int(pct)}%")
        self.root.after(0, _do)

    def _run_signup(self):
        """在子线程中运行签到流程，按细化阶段更新进度"""
        try:
            self._deli_instance = Deli()
            # 从配置读取 debugmode
            cfg = load_config()
            self._deli_instance.debugmode = cfg.get("debugmode", True)
            users = cfg.get("users", {})
            user_count = len(users)

            # 细化阶段：每个用户签到拆分为多个子阶段
            # 初始化(1) + 连接模拟器(1) + 启动模拟器(1) + 启动应用(1) + 启动页面(1)
            # + 每个用户: 输入账号(1) + 输入密码(1) + 点击登录(1) + 设置位置(1) + 同意(1) + 考勤(1) + 打卡(1) + 退出(1)
            stages_per_user = 8
            base_stages = 5  # 初始化 + 连接 + 启动模拟器 + 启动应用 + 启动页面
            total_stages = base_stages + user_count * stages_per_user
            self._update_step(1, total_stages, "重新加载配置文件...", "初始化配置")

            import time
            time.sleep(0.05)

            # --- 阶段 2: 初始化模拟器 ---
            self._update_step(2, total_stages, "正在初始化模拟器连接...", "连接模拟器")
            self._deli_instance.emulator = self._deli_instance.select_emulator()()

            # --- 阶段 3: 启动模拟器 ---
            self._update_step(3, total_stages, "正在启动模拟器...", "启动模拟器")
            self._deli_instance.emulator.start_emulator()

            # --- 阶段 4: 启动应用 ---
            self._update_step(4, total_stages, "正在启动得力 E+ 应用...", "启动应用")
            self._deli_instance.emulator.start_app(self._deli_instance.deli_package_name)

            # --- 阶段 5: 处理启动页面 ---
            self._update_step(5, total_stages, "处理应用启动页面...", "启动页面")
            self._deli_instance._check_stop()
            while True:
                self._deli_instance._check_stop()
                if self._deli_instance.emulator.wait(
                    "//android.widget.TextView[@text='跳过']", timeout=0.5
                ).exists():
                    self._deli_instance.emulator.wait(
                        "//android.widget.TextView[@text='跳过']", timeout=0.5
                    ).click()
                    self._deli_instance.check_login_invaild()
                if self._deli_instance.emulator.wait(
                    "//android.widget.TextView[@text='我的']", timeout=0.3
                ).exists():
                    self._deli_instance.check_login_invaild()
                    self._deli_instance.emulator.wait("//android.widget.TextView[@text='我的']").click()
                    self._deli_instance.check_login_invaild()
                    self._deli_instance.emulator.wait("//android.widget.TextView[@text='设置']").click()
                    self._deli_instance.check_login_invaild()
                    self._deli_instance.emulator.wait("//android.widget.TextView[@text='退出登录']").click()
                    self._deli_instance.emulator.wait("//android.widget.TextView[@text='确定']").click()
                if self._deli_instance.emulator.wait(
                    "//android.widget.TextView[@text='登录']", timeout=0.3
                ).exists():
                    break

            # --- 逐个用户签到（细化子阶段） ---
            for idx, user in enumerate(users.items()):
                self._deli_instance._check_stop()
                username, password = user[0], user[1]
                base_num = base_stages + idx * stages_per_user

                # 子阶段 1: 输入账号
                self._update_step(base_num + 1, total_stages,
                                  f"输入账号: {username}", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance.emulator.wait(
                    "//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_phone']"
                ).click()
                self._deli_instance.emulator.wait(
                    "//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_phone']"
                ).send_keys(username)

                # 子阶段 2: 输入密码
                self._update_step(base_num + 2, total_stages,
                                  "输入密码...", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance.emulator.wait("//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_password']").click()
                self._deli_instance.emulator.wait("//android.widget.EditText[@resource-id='com.delicloud.app.smartoffice:id/et_password']").send_keys(password)

                # 子阶段 3: 点击登录
                self._update_step(base_num + 3, total_stages,
                                  "点击登录按钮...", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='登录']").click()

                # 子阶段 4: 设置虚拟位置
                self._update_step(base_num + 4, total_stages,
                                  "设置虚拟定位...", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance.emulator.set_vitual_location()

                # 子阶段 5: 同意并继续
                self._update_step(base_num + 5, total_stages,
                                  "同意协议并继续...", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='同意并继续']").click()

                # 子阶段 6: 进入智能考勤
                self._update_step(base_num + 6, total_stages,
                                  "进入智能考勤...", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='智能考勤']").click()

                # 子阶段 7: 执行打卡
                self._update_step(base_num + 7, total_stages,
                                  "等待打卡范围检测...", f"用户签到 ({idx+1}/{user_count})")
                start_time = time.time()
                flag_success = False
                while True:
                    self._deli_instance._check_stop()
                    if time.time() - start_time > 90:
                        raise TimeoutError("签到超时")
                    if self._deli_instance.emulator.wait(
                        "//android.widget.TextView[@text='已在打卡范围内']", timeout=0.3
                    ).exists():
                        if not self._deli_instance.debugmode:
                            self._update_step(base_num + 7, total_stages,
                                              "执行打卡...", f"用户签到 ({idx+1}/{user_count})")
                            self._deli_instance.emulator.wait(
                                "//android.widget.TextView[@text='打卡']", timeout=0.3
                            ).click()
                            while not flag_success:
                                self._deli_instance._check_stop()
                                for i in ['打卡成功', '签到成功', '签退成功', '迟到', '早退']:
                                    if self._deli_instance.emulator.wait(
                                        "//android.widget.TextView[@text='" + i + "']", timeout=0.1
                                    ).exists():
                                        self._deli_instance.emulator.wait(
                                            "//android.widget.ImageView[@resource-id='com.delicloud.app.smartoffice:id/iv_close']",
                                            timeout=0.3,
                                        ).click()
                                        flag_success = True
                                        self._update_step(base_num + 7, total_stages,
                                                          f"打卡结果: {i}", f"用户签到 ({idx+1}/{user_count})")
                                    break
                        else:
                            self._update_step(base_num + 7, total_stages,
                                              "调试模式：跳过实际打卡", f"用户签到 ({idx+1}/{user_count})")
                        break
                    elif self._deli_instance.emulator.wait(
                        "//android.widget.TextView[@text='不在打卡范围内']", timeout=0.3
                    ).exists():
                        self._update_step(base_num + 7, total_stages,
                                          "不在打卡范围内，刷新位置...", f"用户签到 ({idx+1}/{user_count})")
                        self._deli_instance.emulator.wait(
                            "//android.widget.TextView[@text='刷新']", timeout=0.1
                        ).click()

                # 子阶段 8: 退出登录
                self._update_step(base_num + 8, total_stages,
                                  "退出当前账号...", f"用户签到 ({idx+1}/{user_count})")
                self._deli_instance._check_stop()
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='我的']").click()
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='设置']").click()
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='退出登录']").click()
                self._deli_instance.emulator.wait("//android.widget.TextView[@text='确定']").click()

            self._update_step(total_stages, total_stages, "所有用户签到完成", "完成")
            self.root.after(0, lambda: self._on_sign_finished(True))

        except InterruptedError:
            self.root.after(0, lambda: self._on_sign_finished(False))
        except Exception as e:
            tb_str = traceback.format_exc()
            self.root.after(0, lambda tb=tb_str: self._on_sign_finished(False, str(e), tb))

    def _on_sign_finished(self, success, error_msg="", traceback_str=""):
        self._sign_started = False
        try:
            self.start_btn.config(state="normal")
        except Exception:
            pass
        try:
            self.stop_btn.config(state="disabled")
        except Exception:
            pass

        if success:
            self.status_label.config(text="● 完成", fg=Win11Colors.SUCCESS)
            self.sign_status_badge.config(text="已完成", bg="#e8f5e9", fg=Win11Colors.SUCCESS)
            self._update_step(0, 0, "所有用户签到完成 ✓", "")
            self.progress_var.set(100)
            self.progress_pct_label.config(text="100%")
            self._hide_error_block()
        elif error_msg:
            self.status_label.config(text="● 错误", fg=Win11Colors.ERROR)
            self.sign_status_badge.config(text="出错", bg="#fce4e4", fg=Win11Colors.ERROR)
            self._update_step(0, 0, f"签到出错: {error_msg}", "")
            # 显示错误信息块
            self._show_error_block(error_msg, traceback_str)
        else:
            self.status_label.config(text="● 中断", fg=Win11Colors.WARNING)
            self.sign_status_badge.config(text="已停止", bg="#fff3e0", fg=Win11Colors.WARNING)
            self._update_step(0, 0, "签到已停止", "")
            self._hide_error_block()

        self._deli_instance = None

    def _stop_sign(self):
        if self._deli_instance:
            self._deli_instance.stop()
        self.status_label.config(text="● 停止中", fg=Win11Colors.WARNING)
        self.sign_status_badge.config(text="停止中", bg="#fff3e0", fg=Win11Colors.WARNING)

    # ==================== 用户管理页 ====================
    def _build_users_page(self):
        page = tk.Frame(self.content_frame, bg=Win11Colors.BG)
        page.pack(fill="both", expand=True)

        scroll = ScrollableFrame(page)
        scroll.pack(fill="both", expand=True)
        container = scroll.scrollable_frame

        # 标题行（含保存状态）
        title_row = tk.Frame(container, bg=Win11Colors.BG)
        title_row.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(
            title_row, text="用户管理", font=UI_FONT_SECTION,
            bg=Win11Colors.BG, fg=Win11Colors.TEXT_PRIMARY,
        ).pack(side="left")

        # 保存状态指示器
        self._save_status_frame = tk.Frame(title_row, bg=Win11Colors.BG)
        self._save_status_frame.pack(side="left", padx=(12, 0))

        self._save_status_icon = tk.Label(
            self._save_status_frame,
            text="\u2714",  # ✔
            font=("Segoe UI Symbol", 10) if sys.platform == "win32" else ("Segoe UI", 10),
            bg=Win11Colors.BG, fg=Win11Colors.SAVE_IDLE,
        )
        self._save_status_icon.pack(side="left")

        self._save_status_text = tk.Label(
            self._save_status_frame,
            text="已保存",
            font=UI_FONT_XS,
            bg=Win11Colors.BG, fg=Win11Colors.SAVE_IDLE,
        )
        self._save_status_text.pack(side="left", padx=(4, 0))

        self._save_unsaved = False

        user_card = tk.Frame(container, bg=Win11Colors.CARD_BG, bd=0,
                             highlightthickness=1, highlightbackground=Win11Colors.BORDER)
        user_card.pack(fill="x", padx=20, pady=(0, 16))
        user_inner = tk.Frame(user_card, bg=Win11Colors.CARD_BG)
        user_inner.pack(fill="x", padx=18, pady=16)

        self.user_table_frame = tk.Frame(user_inner, bg=Win11Colors.CARD_BG)
        self.user_table_frame.pack(fill="x")
        self._build_user_table()

        add_frame = tk.Frame(user_inner, bg=Win11Colors.CARD_BG)
        add_frame.pack(fill="x", pady=(10, 0))
        Win11Button(add_frame, text="＋ 添加用户", command=lambda: self._add_user_row(), style="outline").pack(side="left")

        save_frame = tk.Frame(container, bg=Win11Colors.BG)
        save_frame.pack(fill="x", padx=20, pady=(0, 24))
        Win11Button(save_frame, text="保存用户", command=self._save_users, style="primary").pack(side="right")

    # ==================== 设置页 ====================
    def _build_settings_page(self):
        page = tk.Frame(self.content_frame, bg=Win11Colors.BG)
        page.pack(fill="both", expand=True)

        scroll = ScrollableFrame(page)
        scroll.pack(fill="both", expand=True)
        container = scroll.scrollable_frame

        cfg = load_config()

        # 模拟器设置
        self._section_label(container, "模拟器设置")
        sim_card = tk.Frame(container, bg=Win11Colors.CARD_BG, bd=0,
                            highlightthickness=1, highlightbackground=Win11Colors.BORDER)
        sim_card.pack(fill="x", padx=20, pady=(0, 16))
        sim_inner = tk.Frame(sim_card, bg=Win11Colors.CARD_BG)
        sim_inner.pack(fill="x", padx=18, pady=16)

        self._field_label(sim_inner, "MuMu 模拟器路径")
        path_frame = tk.Frame(sim_inner, bg=Win11Colors.CARD_BG)
        path_frame.pack(fill="x", pady=(4, 12))
        self.emulator_path_entry = Win11Entry(
            path_frame, placeholder="例: C:\\Program Files\\NetEase\\MuMu\\nx_main", width=38)
        self.emulator_path_entry.pack(side="left", fill="x", expand=True)
        self.emulator_path_entry.set(cfg.get("emulator_path", ""))
        self.emulator_path_entry.entry.bind("<KeyRelease>", self._on_setting_changed)
        self.emulator_path_entry.entry.bind("<FocusOut>", self._on_setting_changed)
        Win11Button(path_frame, text="浏览", command=self._browse_emulator, style="secondary").pack(
            side="left", padx=(8, 0))

        self._field_label(sim_inner, "ADB 序列号")
        self.serial_entry = Win11Entry(sim_inner, placeholder="127.0.0.1:16384", width=38)
        self.serial_entry.pack(fill="x", pady=(4, 12))
        self.serial_entry.set(cfg.get("serial", "127.0.0.1:16384"))
        self.serial_entry.entry.bind("<KeyRelease>", self._on_setting_changed)
        self.serial_entry.entry.bind("<FocusOut>", self._on_setting_changed)

        # 模拟器编号 + 调试模式开关（同一行）
        num_row = tk.Frame(sim_inner, bg=Win11Colors.CARD_BG)
        num_row.pack(fill="x", pady=(0, 12))

        # 左：模拟器编号
        num_col = tk.Frame(num_row, bg=Win11Colors.CARD_BG)
        num_col.pack(side="left", fill="x", expand=True)
        self._field_label(num_col, "模拟器编号")
        self.emulator_num_entry = Win11Entry(num_col, placeholder="0", width=20)
        self.emulator_num_entry.pack(fill="x", pady=(4, 0))
        self.emulator_num_entry.set(str(cfg.get("emulator_num", "0")))
        self.emulator_num_entry.entry.bind("<KeyRelease>", self._on_setting_changed)
        self.emulator_num_entry.entry.bind("<FocusOut>", self._on_setting_changed)

        # 右：调试模式开关
        debug_col = tk.Frame(num_row, bg=Win11Colors.CARD_BG)
        debug_col.pack(side="left", padx=(40, 0))

        self._field_label(debug_col, "调试模式")
        self.debug_var = tk.BooleanVar(value=cfg.get("debugmode", True))
        self.debug_toggle = tk.Checkbutton(
            debug_col,
            text="启用调试模式（不实际打卡）",
            variable=self.debug_var,
            font=UI_FONT,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_SECONDARY,
            selectcolor=Win11Colors.CARD_BG,
            activebackground=Win11Colors.CARD_BG,
            activeforeground=Win11Colors.TEXT_PRIMARY,
            cursor="hand2",
            relief="flat",
        )
        self.debug_toggle.pack(anchor="w", pady=(6, 0))
        self.debug_var.trace_add("write", self._on_setting_changed)

        # 虚拟定位
        self._section_label(container, "虚拟定位")
        loc_card = tk.Frame(container, bg=Win11Colors.CARD_BG, bd=0,
                            highlightthickness=1, highlightbackground=Win11Colors.BORDER)
        loc_card.pack(fill="x", padx=20, pady=(0, 16))
        loc_inner = tk.Frame(loc_card, bg=Win11Colors.CARD_BG)
        loc_inner.pack(fill="x", padx=18, pady=16)

        loc = cfg.get("location", {"latitude": 111, "longitude": 111})

        # 使用左右两列布局，确保标签和输入框对齐
        loc_grid = tk.Frame(loc_inner, bg=Win11Colors.CARD_BG)
        loc_grid.pack(fill="x")

        # 左列：纬度
        lat_col = tk.Frame(loc_grid, bg=Win11Colors.CARD_BG)
        lat_col.pack(side="left", fill="x", expand=True)

        self._field_label(lat_col, "纬度 (Latitude)")
        self.lat_entry = Win11Entry(lat_col, placeholder="111", width=20)
        self.lat_entry.pack(fill="x", pady=(4, 0))
        self.lat_entry.set(str(loc.get("latitude", 111)))
        self.lat_entry.entry.bind("<KeyRelease>", self._on_setting_changed)
        self.lat_entry.entry.bind("<FocusOut>", self._on_setting_changed)

        # 右列：经度
        lng_col = tk.Frame(loc_grid, bg=Win11Colors.CARD_BG)
        lng_col.pack(side="left", fill="x", expand=True, padx=(20, 0))

        self._field_label(lng_col, "经度 (Longitude)")
        self.lng_entry = Win11Entry(lng_col, placeholder="111", width=20)
        self.lng_entry.pack(fill="x", pady=(4, 0))
        self.lng_entry.set(str(loc.get("longitude", 111)))
        self.lng_entry.entry.bind("<KeyRelease>", self._on_setting_changed)
        self.lng_entry.entry.bind("<FocusOut>", self._on_setting_changed)

        # 设置验证提示 + 保存按钮行
        save_frame = tk.Frame(container, bg=Win11Colors.BG)
        save_frame.pack(fill="x", padx=20, pady=(0, 24))

        self.settings_error_label = tk.Label(
            save_frame,
            text="",
            font=UI_FONT_XS,
            bg=Win11Colors.BG, fg=Win11Colors.ERROR,
            anchor="w", justify="left",
        )
        self.settings_error_label.pack(side="left", fill="x", expand=True)

        Win11Button(save_frame, text="保存设置", command=self._save_settings, style="primary").pack(side="right")

    def _section_label(self, parent, text):
        tk.Label(
            parent, text=text, font=UI_FONT_SECTION,
            bg=Win11Colors.BG, fg=Win11Colors.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 8))

    def _field_label(self, parent, text, side="top", padx=0):
        tk.Label(
            parent, text=text, font=UI_FONT_SM,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_SECONDARY,
        ).pack(anchor="w", side=side, padx=padx)

    def _browse_emulator(self):
        path = filedialog.askdirectory(title="选择 MuMu 模拟器安装目录")
        if path:
            self.emulator_path_entry.set(path)
            self._on_setting_changed()

    def _on_setting_changed(self, *args):
        """设置项变化时实时验证并自动保存"""
        errors = self._validate_settings(show=False)
        if not errors:
            # 无错误，自动保存
            self._auto_save_settings()

    def _validate_settings(self, show=True):
        """验证所有设置项，返回错误列表。show=True 时更新界面提示"""
        errors = []

        # 模拟器路径
        emu_path = self.emulator_path_entry.get()
        if emu_path:
            # 检查目录是否存在
            if not os.path.isdir(emu_path):
                errors.append(f"模拟器路径不存在: {emu_path}")
            else:
                # 检查关键文件
                missing = []
                for fname in ["MuMuManager.exe", "MuMuNxMain.exe", "adb.exe"]:
                    fp = os.path.join(emu_path, fname)
                    if not os.path.isfile(fp):
                        missing.append(fname)
                if missing:
                    errors.append(f"模拟器路径缺少文件: {', '.join(missing)}")

        # ADB 序列号格式
        serial = self.serial_entry.get()
        if serial and not serial.strip():
            errors.append("ADB 序列号不能为空白")
        elif serial:
            # 简单格式检查：host:port 或纯数字/字母
            if ":" in serial:
                parts = serial.split(":")
                if len(parts) != 2:
                    errors.append(f"ADB 序列号格式错误（应为 host:port）: {serial}")

        # 模拟器编号
        emu_num = self.emulator_num_entry.get()
        if emu_num:
            try:
                int(emu_num)
            except ValueError:
                errors.append("模拟器编号必须为整数")

        # 经纬度
        try:
            lat = float(self.lat_entry.get())
        except ValueError:
            errors.append("纬度必须为有效数字")
        else:
            if lat < -90 or lat > 90:
                errors.append(f"纬度超出范围: {lat}（应在 -90 ~ 90 之间）")

        try:
            lng = float(self.lng_entry.get())
        except ValueError:
            errors.append("经度必须为有效数字")
        else:
            if lng < -180 or lng > 180:
                errors.append(f"经度超出范围: {lng}（应在 -180 ~ 180 之间）")

        # 更新界面
        if show and hasattr(self, 'settings_error_label') and self.settings_error_label.winfo_exists():
            if errors:
                self.settings_error_label.config(text="\u26a0 " + "；".join(errors))
            else:
                self.settings_error_label.config(text="")

        return errors

    def _auto_save_settings(self):
        """无感自动保存设置（不弹窗，不重建页面）"""
        # 若配置文件不存在则从默认配置创建，否则加载已有配置
        if os.path.exists(CONFIG_PATH):
            cfg = load_config()
        else:
            cfg = dict(DEFAULT_CONFIG)

        emu_path = self.emulator_path_entry.get()
        serial = self.serial_entry.get()
        emu_num = self.emulator_num_entry.get()
        if emu_path:
            cfg["emulator_path"] = emu_path
        if serial:
            cfg["serial"] = serial
        if emu_num:
            cfg["emulator_num"] = emu_num

        cfg["debugmode"] = self.debug_var.get()

        try:
            lat = float(self.lat_entry.get())
            lng = float(self.lng_entry.get())
            cfg["location"] = {"latitude": lat, "longitude": lng}
        except ValueError:
            return  # 数值无效时不保存

        save_config(cfg)
        reload_config()

    # ==================== 用户表格 ====================
    def _build_user_table(self):
        for w in self.user_table_frame.winfo_children():
            w.destroy()
        self._user_rows.clear()

        cfg = load_config()
        users = cfg.get("users", {})
        if users:
            for username, password in users.items():
                self._add_user_row(username, password)
        else:
            self._add_user_row()

        # 初始状态为已保存
        self._set_save_status(False)

    def _add_user_row(self, username="", password=""):
        row_idx = len(self._user_rows)
        row_frame = tk.Frame(self.user_table_frame, bg=Win11Colors.CARD_BG)
        row_frame.pack(fill="x", pady=3)

        tk.Label(
            row_frame, text=f"{row_idx + 1}.", font=UI_FONT_SM, width=3,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_SECONDARY,
        ).pack(side="left", pady=5)

        user_entry = Win11Entry(row_frame, placeholder="手机号/账号", width=22)
        user_entry.pack(side="left", padx=(0, 8))
        user_entry.set(username)
        user_entry.entry.bind("<KeyRelease>", lambda e: self._on_user_input_change())

        pass_entry = Win11Entry(row_frame, placeholder="密码", width=22, show="*", password_toggle=True)
        pass_entry.pack(side="left", padx=(0, 8))
        pass_entry.set(password)
        pass_entry.entry.bind("<KeyRelease>", lambda e: self._on_user_input_change())

        # 删除按钮（在每行右侧）
        del_btn = tk.Button(
            row_frame, text="删除",
            font=UI_FONT_SM,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.ERROR,
            activebackground="#fce4e4", activeforeground=Win11Colors.ERROR,
            relief="flat", bd=0, padx=10, pady=3, cursor="hand2",
            command=lambda r=row_frame: self._delete_user_row(r),
        )
        del_btn.pack(side="right", padx=(4, 0))

        self._user_rows.append({"frame": row_frame, "user": user_entry, "pass": pass_entry})

    def _on_user_input_change(self):
        """用户输入变化时标记未保存"""
        self._set_save_status(True)

    def _set_save_status(self, dirty):
        """更新保存状态指示器"""
        self._save_unsaved = dirty
        if hasattr(self, '_save_status_icon') and self._save_status_icon.winfo_exists():
            if dirty:
                self._save_status_icon.config(text="\u26a0", fg=Win11Colors.SAVE_DIRTY)  # ⚠
                self._save_status_text.config(text="未保存", fg=Win11Colors.SAVE_DIRTY)
            else:
                self._save_status_icon.config(text="\u2714", fg=Win11Colors.SAVE_OK)  # ✔
                self._save_status_text.config(text="已保存", fg=Win11Colors.SAVE_OK)

    def _delete_user_row(self, row_frame):
        for i, row in enumerate(self._user_rows):
            if row["frame"] == row_frame:
                row["frame"].destroy()
                self._user_rows.pop(i)
                break
        self._refresh_user_numbers()
        self._on_user_input_change()  # 标记未保存

    def _refresh_user_numbers(self):
        for i, row in enumerate(self._user_rows):
            for child in row["frame"].winfo_children():
                if isinstance(child, tk.Label):
                    child.config(text=f"{i + 1}.")
                    break

    def _save_users(self):
        # 若配置文件不存在则从默认配置创建（保留设置页可能已输入的内容），否则加载已有配置
        if os.path.exists(CONFIG_PATH):
            cfg = load_config()
        else:
            cfg = dict(DEFAULT_CONFIG)

        users = {}
        for row in self._user_rows:
            u = row["user"].get()
            p = row["pass"].get()
            if u:
                users[u] = p
        cfg["users"] = users
        save_config(cfg)
        reload_config()
        self._set_save_status(False)  # 标记已保存

        # 重建页面以刷新状态
        for w in self.content_frame.winfo_children():
            w.destroy()
        self._build_users_page()

    def _save_settings(self):
        """手动保存设置（先验证再保存）"""
        errors = self._validate_settings(show=True)
        if errors:
            return

        self._auto_save_settings()
        messagebox.showinfo("成功", "设置已保存")

        for w in self.content_frame.winfo_children():
            w.destroy()
        self._build_settings_page()

    # ==================== 日志页 ====================
    def _build_log_page(self):
        page = tk.Frame(self.content_frame, bg=Win11Colors.BG)
        page.pack(fill="both", expand=True)

        toolbar = tk.Frame(page, bg=Win11Colors.BG)
        toolbar.pack(fill="x", padx=20, pady=(20, 6))

        tk.Label(
            toolbar, text="运行日志",
            font=UI_FONT_SECTION,
            bg=Win11Colors.BG, fg=Win11Colors.TEXT_PRIMARY,
        ).pack(side="left")

        # 右侧按钮组
        btn_group = tk.Frame(toolbar, bg=Win11Colors.BG)
        btn_group.pack(side="right")
        Win11Button(btn_group, text="清空", command=self._clear_log, style="secondary").pack(side="right", padx=(8, 0))
        Win11Button(btn_group, text="导出", command=self._export_log, style="secondary").pack(side="right")

        log_frame = tk.Frame(page, bg=Win11Colors.BG)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(4, 20))

        self.log_text = tk.Text(
            log_frame,
            font=MONO_FONT,
            bg=Win11Colors.CARD_BG, fg=Win11Colors.TEXT_PRIMARY,
            insertbackground=Win11Colors.TEXT_PRIMARY,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=Win11Colors.BORDER,
            wrap="word", state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

        # 日志页创建后，将缓冲区的内容一次性写入
        self._flush_log_buffer()

    def _flush_log_buffer(self):
        """将缓冲区中的日志写入文本框"""
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state="normal")
            for msg in self._log_buffer:
                self.log_text.insert("end", msg)
                self.log_text.see("end")
            self.log_text.config(state="disabled")
            self._log_buffer.clear()

    def _clear_log(self):
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.config(state="disabled")

    def _export_log(self):
        """将日志内容导出到 log 文件夹，以第一行日志的时间命名"""
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists():
            return

        content = self.log_text.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showwarning("提示", "日志为空，无法导出")
            return

        # 提取第一行日志中的时间戳作为文件名
        first_line = content.split("\n")[0].strip()
        # 尝试从第一行提取时间：格式如 "2026-07-12 17:20:12,595"
        filename = None
        try:
            # 查找 YYYY-MM-DD HH:MM:SS 格式
            parts = first_line.split(" - ")[0].strip()
            # 将空格和逗号替换为下划线
            ts = parts.replace(" ", "_").replace(",", "_").replace(":", "-")
            if ts:
                filename = f"{ts}.txt"
        except Exception:
            pass

        if not filename:
            # fallback: 使用当前时间
            filename = datetime.datetime.now().strftime("log_%Y%m%d_%H%M%S.txt")

        # 确保 log 目录存在
        log_dir = os.path.join(SCRIPT_DIR, "log")
        os.makedirs(log_dir, exist_ok=True)

        filepath = os.path.join(log_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("导出成功", f"日志已导出到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", f"无法写入文件:\n{str(e)}")

    # ==================== 日志处理 ====================
    def _on_log(self, msg):
        """收到日志回调，放入队列"""
        self._log_queue.put(msg)

    def _poll_log_queue(self):
        """轮询日志队列并刷新到 GUI 文本框"""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        # 刷新更快：50ms
        self.root.after(50, self._poll_log_queue)

    def _append_log(self, msg):
        """追加日志到文本框（如不存在则缓冲）"""
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        else:
            # 日志页未创建，暂存到缓冲区
            self._log_buffer.append(msg)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = DeliSignupApp()
    app.run()
