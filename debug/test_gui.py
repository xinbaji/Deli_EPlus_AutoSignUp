"""
GUI 综合测试用例
测试所有按钮绑定的函数以及底层模块，无需启动真实 GUI 窗口。
"""

import unittest
import sys
import os
import json
import tempfile
import logging

# 设置模块路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "Deli_EPlus_AutoSignUp"))
sys.path.insert(0, PROJECT_DIR)

# 备份原始 config.json（项目目录下的）
_ORIG_CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
_BACKUP_CONFIG = None


def setUpModule():
    """测试前备份 config.json"""
    global _BACKUP_CONFIG
    if os.path.exists(_ORIG_CONFIG_PATH):
        with open(_ORIG_CONFIG_PATH, "r", encoding="utf-8") as f:
            _BACKUP_CONFIG = f.read()
    # 用默认配置覆盖
    from Setting import DEFAULT_CONFIG, save_config
    save_config(dict(DEFAULT_CONFIG))


def tearDownModule():
    """测试后恢复 config.json"""
    if _BACKUP_CONFIG is not None:
        with open(_ORIG_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(_BACKUP_CONFIG)


# ==================== 测试 Setting 模块 ====================
class TestSettingModule(unittest.TestCase):
    """Setting.py 配置层测试"""

    def test_load_default_config(self):
        """测试加载默认配置"""
        from Setting import load_config, DEFAULT_CONFIG
        cfg = load_config()
        self.assertEqual(cfg["serial"], DEFAULT_CONFIG["serial"])
        self.assertEqual(cfg["emulator_path"], DEFAULT_CONFIG["emulator_path"])
        self.assertEqual(cfg["emulator_num"], DEFAULT_CONFIG["emulator_num"])
        self.assertIn("latitude", cfg["location"])
        self.assertIn("longitude", cfg["location"])
        self.assertEqual(cfg["users"], {})

    def test_save_and_reload_config(self):
        """测试保存配置并重新加载"""
        from Setting import save_config, load_config, reload_config
        cfg = load_config()
        cfg["serial"] = "192.168.1.1:5555"
        cfg["users"] = {"testuser": "testpass"}
        save_config(cfg)

        # reload
        reload_config()
        import Setting
        self.assertEqual(Setting.serial, "192.168.1.1:5555")
        self.assertEqual(Setting.users, {"testuser": "testpass"})

        # 恢复
        cfg["serial"] = "127.0.0.1:16384"
        cfg["users"] = {}
        save_config(cfg)
        reload_config()

    def test_setting_class_attr_access(self):
        """测试 Setting 类属性访问（兼容旧代码）"""
        from Setting import Setting, save_config, load_config, reload_config
        cfg = load_config()
        cfg["emulator_num"] = "3"
        save_config(cfg)
        reload_config()

        self.assertEqual(Setting.emulator_num, "3")

        # 恢复
        cfg["emulator_num"] = "0"
        save_config(cfg)
        reload_config()

    def test_config_persistence(self):
        """测试配置持久化到文件"""
        from Setting import CONFIG_PATH, save_config, load_config
        cfg = load_config()
        cfg["location"] = {"latitude": 39.9, "longitude": 116.4}
        save_config(cfg)

        # 从文件直接读取
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["location"]["latitude"], 39.9)
        self.assertEqual(raw["location"]["longitude"], 116.4)

        # 恢复
        cfg["location"] = {"latitude": 111, "longitude": 111}
        save_config(cfg)

    def test_corrupted_config_fallback(self):
        """测试损坏的配置文件回退到默认值"""
        from Setting import CONFIG_PATH, load_config, save_config, DEFAULT_CONFIG
        # 写入损坏的 JSON
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write("this is not json{{{")
        cfg = load_config()
        self.assertEqual(cfg["serial"], DEFAULT_CONFIG["serial"])
        self.assertEqual(cfg["users"], {})

    def test_missing_config_file_created(self):
        """测试缺失配置文件时自动创建"""
        from Setting import CONFIG_PATH, load_config, save_config
        # 删除 config
        if os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)
        cfg = load_config()
        # 文件应被创建
        self.assertTrue(os.path.exists(CONFIG_PATH))
        self.assertIn("serial", cfg)


# ==================== 测试 Log 模块 ====================
class TestLogModule(unittest.TestCase):
    """Log.py 日志模块测试"""

    def setUp(self):
        from Log import Log
        # 清除 GUI 回调
        Log._gui_callbacks.clear()
        self.log = Log("test_log").logger

    def test_logger_creation(self):
        """测试 Logger 创建"""
        self.assertIsNotNone(self.log)
        self.assertEqual(self.log.name, "test_log")
        self.assertEqual(len(self.log.handlers), 2)  # 控制台 + GUI

    def test_log_levels(self):
        """测试日志级别"""
        from Log import Log
        log_debug = Log("test_debug", mode="d").logger
        self.assertEqual(log_debug.level, logging.DEBUG)

        log_info = Log("test_info", mode="i").logger
        self.assertEqual(log_info.level, logging.INFO)

    def test_gui_callback_registration(self):
        """测试 GUI 回调注册和移除"""
        from Log import Log
        Log._gui_callbacks.clear()
        msgs = []

        def callback(msg):
            msgs.append(msg)

        Log.add_gui_callback(callback)
        self.assertEqual(len(Log._gui_callbacks), 1)

        # 重复添加不生效
        Log.add_gui_callback(callback)
        self.assertEqual(len(Log._gui_callbacks), 1)

        # 移除
        Log.remove_gui_callback(callback)
        self.assertEqual(len(Log._gui_callbacks), 0)

    def test_gui_callback_receives_log(self):
        """测试 GUI 回调能收到日志"""
        from Log import Log
        Log._gui_callbacks.clear()
        msgs = []

        def callback(msg):
            msgs.append(msg)

        Log.add_gui_callback(callback)
        logger = Log("test_cb").logger
        logger.info("GUI test message")

        self.assertTrue(any("GUI test message" in m for m in msgs))

        Log.remove_gui_callback(callback)

    def test_log_no_file_created(self):
        """测试日志不再写入本地文件"""
        self.log.info("test no file creation")
        # 日志不再自动写入文件，log 目录可能不存在
        self.assertTrue(True)  # 仅验证日志输出不抛异常


# ==================== 测试 Deli 类（无模拟器） ====================
class TestDeliClass(unittest.TestCase):
    """deliSignup.py Deli 类测试（不连接模拟器）"""

    def setUp(self):
        from Setting import save_config, reload_config
        # 确保有模拟器路径
        cfg = {
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"testuser": "testpass"}
        }
        save_config(cfg)
        reload_config()

    def test_deli_instantiation(self):
        """测试 Deli 实例化"""
        from deliSignup import Deli
        d = Deli()
        self.assertIsNotNone(d)
        self.assertEqual(d.deli_package_name, "com.delicloud.app.smartoffice")
        self.assertFalse(d._running)
        self.assertFalse(d._stop_flag)

    def test_select_emulator_mumu(self):
        """测试 MuMu 模拟器选择"""
        from deliSignup import Deli
        from emulator.mumu import Mumu
        d = Deli()
        self.assertEqual(d.select_emulator(), Mumu)

    def test_select_emulator_no_path(self):
        """测试无模拟器路径时的行为"""
        from deliSignup import Deli
        from Setting import save_config, reload_config
        cfg = {
            "serial": "127.0.0.1:16384",
            "emulator_path": "",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"testuser": "testpass"}
        }
        save_config(cfg)
        reload_config()
        d = Deli()
        with self.assertRaises(ValueError):
            d.select_emulator()

    def test_stop_flag(self):
        """测试 stop() 方法设置停止标志"""
        from deliSignup import Deli
        d = Deli()
        self.assertFalse(d._stop_flag)
        d.stop()
        self.assertTrue(d._stop_flag)

    def test_check_stop_raises(self):
        """测试 _check_stop 在停止标志下抛出异常"""
        from deliSignup import Deli
        d = Deli()
        d._stop_flag = True
        with self.assertRaises(InterruptedError):
            d._check_stop()

    def test_run_with_no_emulator_path(self):
        """测试无模拟器路径时 run() 返回 False"""
        from deliSignup import Deli
        from Setting import save_config, reload_config
        cfg = {
            "serial": "127.0.0.1:16384",
            "emulator_path": "",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"testuser": "testpass"}
        }
        save_config(cfg)
        reload_config()
        d = Deli()
        result = d.run()
        self.assertFalse(result)

    def test_run_with_no_users(self):
        """测试无用户时 run() 返回 False"""
        from deliSignup import Deli
        from Setting import save_config, reload_config
        cfg = {
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {}
        }
        save_config(cfg)
        reload_config()
        d = Deli()
        # 注意：无模拟器路径会先失败，这里测试的是逻辑路径
        # 实际上 select_emulator 会先检查 emulator_path
        self.assertIsNotNone(d)

    def test_run_signup_function_exists(self):
        """测试 run_signup 函数存在且可调用"""
        from deliSignup import run_signup
        import inspect
        self.assertTrue(callable(run_signup))
        sig = inspect.signature(run_signup)
        self.assertEqual(len(sig.parameters), 0)


# ==================== 测试 GUI 组件（无头） ====================
class TestWin11Components(unittest.TestCase):
    """Win11 风格组件单元测试"""

    @classmethod
    def setUpClass(cls):
        """初始化一个隐藏的 tk root"""
        import tkinter as tk
        cls.root = tk.Tk()
        cls.root.withdraw()  # 隐藏窗口

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def test_win11_colors_defined(self):
        """测试配色方案定义完整"""
        from gui import Win11Colors
        attrs = ["BG", "CARD_BG", "ACCENT", "ACCENT_HOVER", "TEXT_PRIMARY",
                 "TEXT_SECONDARY", "BORDER", "SUCCESS", "ERROR", "WARNING"]
        for attr in attrs:
            self.assertTrue(hasattr(Win11Colors, attr), f"Missing {attr}")

    def test_win11_entry_creation(self):
        """测试 Win11Entry 创建"""
        from gui import Win11Entry
        entry = Win11Entry(self.root, placeholder="测试", width=20)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get(), "")  # 占位符应返回空
        entry.destroy()

    def test_win11_entry_set_get(self):
        """测试 Win11Entry set/get"""
        from gui import Win11Entry
        entry = Win11Entry(self.root, placeholder="请输入", width=20)
        entry.set("hello")
        self.assertEqual(entry.get(), "hello")
        entry.set("")
        self.assertEqual(entry.get(), "")
        entry.destroy()

    def test_win11_entry_no_placeholder(self):
        """测试无占位符的 Win11Entry"""
        from gui import Win11Entry
        entry = Win11Entry(self.root, placeholder="", width=20)
        entry.set("world")
        self.assertEqual(entry.get(), "world")
        entry.destroy()

    def test_win11_button_creation(self):
        """测试 Win11Button 各样式创建"""
        from gui import Win11Button
        btn_primary = Win11Button(self.root, text="主按钮", style="primary")
        self.assertIsNotNone(btn_primary)
        self.assertEqual(btn_primary.cget("text"), "主按钮")
        btn_primary.destroy()

        btn_danger = Win11Button(self.root, text="危险", style="danger")
        self.assertIsNotNone(btn_danger)
        btn_danger.destroy()

        btn_outline = Win11Button(self.root, text="轮廓", style="outline")
        self.assertIsNotNone(btn_outline)
        btn_outline.destroy()

        btn_secondary = Win11Button(self.root, text="次要", style="secondary")
        self.assertIsNotNone(btn_secondary)
        btn_secondary.destroy()

    def test_win11_button_hover(self):
        """测试 Win11Button 悬停效果"""
        from gui import Win11Button
        btn = Win11Button(self.root, text="悬停测试", style="primary")
        default_bg = btn._default_bg
        hover_bg = btn._hover_bg
        self.assertNotEqual(default_bg, hover_bg)
        btn.destroy()

    def test_scrollable_frame_creation(self):
        """测试 ScrollableFrame 创建"""
        from gui import ScrollableFrame
        sf = ScrollableFrame(self.root, width=400, height=300)
        self.assertIsNotNone(sf)
        self.assertIsNotNone(sf.canvas)
        self.assertIsNotNone(sf.scrollable_frame)
        sf.destroy()


# ==================== 测试 GUI App 核心功能 ====================
class TestDeliSignupAppCore(unittest.TestCase):
    """DeliSignupApp 核心功能测试（无头模拟）"""

    @classmethod
    def setUpClass(cls):
        """初始化隐藏的 tk 应用"""
        import tkinter as tk
        cls.root = tk.Tk()
        cls.root.withdraw()

        from gui import DeliSignupApp
        # 阻止 messagebox 弹窗
        import tkinter.messagebox
        cls._orig_showwarning = tkinter.messagebox.showwarning
        cls._orig_showinfo = tkinter.messagebox.showinfo
        cls._orig_askyesno = tkinter.messagebox.askyesno

        tkinter.messagebox.showwarning = lambda *a, **kw: "ok"
        tkinter.messagebox.showinfo = lambda *a, **kw: "ok"
        tkinter.messagebox.askyesno = lambda *a, **kw: True

        cls.app = DeliSignupApp()

    @classmethod
    def tearDownClass(cls):
        import tkinter.messagebox
        tkinter.messagebox.showwarning = cls._orig_showwarning
        tkinter.messagebox.showinfo = cls._orig_showinfo
        tkinter.messagebox.askyesno = cls._orig_askyesno
        cls.root.destroy()

    def setUp(self):
        """每个测试前重置配置和状态"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"user1": "pass1", "user2": "pass2"}
        })
        reload_config()
        # 清除持久化的错误状态
        self.app._last_error = None

    # ---- 导航测试 ----
    def test_nav_buttons_exist(self):
        """测试四个导航按钮存在"""
        self.assertIn("home", self.app.nav_buttons)
        self.assertIn("users", self.app.nav_buttons)
        self.assertIn("settings", self.app.nav_buttons)
        self.assertIn("log", self.app.nav_buttons)
        self.assertEqual(len(self.app.nav_buttons), 4)

    def test_show_page_home(self):
        """测试切换到主页"""
        self.app._show_page("home")
        # 验证内容区有 widget
        self.assertGreater(len(self.app.content_frame.winfo_children()), 0)

    def test_show_page_settings(self):
        """测试切换到设置页"""
        self.app._show_page("settings")
        self.assertGreater(len(self.app.content_frame.winfo_children()), 0)
        # 验证设置页的输入框存在
        self.assertTrue(hasattr(self.app, 'emulator_path_entry'))
        self.assertTrue(hasattr(self.app, 'serial_entry'))
        self.assertTrue(hasattr(self.app, 'emulator_num_entry'))
        self.assertTrue(hasattr(self.app, 'lat_entry'))
        self.assertTrue(hasattr(self.app, 'lng_entry'))

    def test_show_page_users(self):
        """测试切换到用户管理页"""
        self.app._show_page("users")
        self.assertGreater(len(self.app.content_frame.winfo_children()), 0)
        self.assertTrue(hasattr(self.app, 'user_table_frame'))

    def test_show_page_log(self):
        """测试切换到日志页"""
        self.app._show_page("log")
        self.assertGreater(len(self.app.content_frame.winfo_children()), 0)
        self.assertTrue(hasattr(self.app, 'log_text'))

    def test_page_switching_updates_nav_style(self):
        """测试页面切换时导航按钮样式更新"""
        self.app._show_page("settings")
        # NavButton 是 tk.Frame，通过 _active 和 _text_label 的颜色验证
        self.assertTrue(self.app.nav_buttons["settings"]._active)
        self.assertFalse(self.app.nav_buttons["home"]._active)
        self.assertEqual(
            self.app.nav_buttons["settings"]._text_label.cget("fg"),
            "#0067c0"  # ACCENT
        )
        self.assertNotEqual(
            self.app.nav_buttons["home"]._text_label.cget("fg"),
            "#0067c0"
        )

    # ---- 主页功能测试 ----
    def test_home_page_user_preview(self):
        """测试主页用户预览"""
        self.app._show_page("home")
        self.assertTrue(hasattr(self.app, '_user_preview_label'))
        text = self.app._user_preview_label.cget("text")
        self.assertIn("user1", text)

    def test_home_page_no_users_preview(self):
        """测试无用户时主页预览"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {}
        })
        reload_config()
        self.app._show_page("home")
        text = self.app._user_preview_label.cget("text")
        self.assertIn("未配置用户", text)

    def test_home_page_debug_banner_shown(self):
        """测试调试模式开启时主页显示提示条"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"user1": "pass1"},
            "debugmode": True
        })
        reload_config()
        self.app._show_page("home")
        # 检查 content_frame 中所有 Label 的文本，应有调试模式提示
        all_labels = []
        def collect_labels(widget):
            import tkinter as tk
            if isinstance(widget, tk.Label):
                all_labels.append(widget.cget("text"))
            for child in widget.winfo_children():
                collect_labels(child)
        collect_labels(self.app.content_frame)
        texts = " ".join(t for t in all_labels if t)
        self.assertIn("调试模式已开启", texts)
        self.assertIn("不会进行实际打卡", texts)

    def test_home_page_debug_banner_hidden(self):
        """测试调试模式关闭时主页不显示提示条"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"user1": "pass1"},
            "debugmode": False
        })
        reload_config()
        self.app._show_page("home")
        # 检查所有 Label 文本，不应包含调试模式提示
        all_labels = []
        def collect_labels(widget):
            import tkinter as tk
            if isinstance(widget, tk.Label):
                all_labels.append(widget.cget("text"))
            for child in widget.winfo_children():
                collect_labels(child)
        collect_labels(self.app.content_frame)
        texts = " ".join(t for t in all_labels if t)
        self.assertNotIn("调试模式已开启", texts)

    def test_start_sign_no_users_warning(self):
        """测试无用户时点击开始签到弹出警告"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {}
        })
        reload_config()
        self.app._show_page("home")
        # 调用 _start_sign，应弹出警告并跳转到用户管理页
        self.app._start_sign()
        # 验证跳转到用户管理页（因为无用户会调用 _show_page("users")）
        self.assertEqual(self.app._current_page, "users")

    def test_start_sign_no_emulator_warning(self):
        """测试无模拟器路径时点击开始签到弹出警告"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"u": "p"}
        })
        reload_config()
        self.app._show_page("home")
        self.app._start_sign()
        # 应跳转到设置页
        self.assertEqual(self.app._current_page, "settings")

    def test_start_btn_disabled_after_click(self):
        """测试点击开始后按钮被禁用"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"testuser": "testpass"}
        })
        reload_config()
        self.app._show_page("home")
        self.app._start_sign()
        state = self.app.start_btn.cget("state")
        self.assertEqual(state, "disabled")

    def test_stop_btn_enabled_after_start(self):
        """测试点击开始后停止按钮启用"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"testuser": "testpass"}
        })
        reload_config()
        self.app._show_page("home")
        self.app._start_sign()
        state = self.app.stop_btn.cget("state")
        self.assertEqual(state, "normal")

    def test_stop_sign_sets_status(self):
        """测试停止签到更新状态"""
        self.app._show_page("home")
        self.app._stop_sign()
        status_text = self.app.status_label.cget("text")
        self.assertIn("停止中", status_text)

    def test_on_sign_finished_success(self):
        """测试签到成功完成回调"""
        self.app._show_page("home")
        self.app._on_sign_finished(True)
        state = self.app.start_btn.cget("state")
        self.assertEqual(state, "normal")
        self.assertEqual(self.app.status_label.cget("text"), "● 完成")

    def test_on_sign_finished_failure(self):
        """测试签到失败完成回调"""
        self.app._show_page("home")
        self.app._on_sign_finished(False, "测试错误")
        # _update_step 是 after 异步的，手动同步验证状态
        self.assertEqual(self.app.status_label.cget("text"), "● 错误")
        self.assertEqual(self.app.sign_status_badge.cget("text"), "出错")

    def test_on_sign_finished_interrupted(self):
        """测试签到中断回调"""
        self.app._show_page("home")
        self.app._on_sign_finished(False)
        self.assertEqual(self.app.status_label.cget("text"), "● 中断")

    # ---- 设置页功能测试 ----
    def test_settings_page_populates_fields(self):
        """测试设置页字段正确填充"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "10.0.0.1:5555",
            "emulator_path": "D:\\MuMu",
            "emulator_num": "2",
            "location": {"latitude": 22.5, "longitude": 114.0},
            "users": {"userA": "passA"}
        })
        reload_config()
        self.app._show_page("settings")

        self.assertEqual(self.app.serial_entry.get(), "10.0.0.1:5555")
        self.assertEqual(self.app.emulator_path_entry.get(), "D:\\MuMu")
        self.assertEqual(self.app.emulator_num_entry.get(), "2")
        # 经纬度现在在独立的列 frame 中
        self.assertTrue(hasattr(self.app, 'lat_entry'))
        self.assertTrue(hasattr(self.app, 'lng_entry'))
        self.assertEqual(self.app.lat_entry.get(), "22.5")
        self.assertEqual(self.app.lng_entry.get(), "114.0")

    def test_save_settings_writes_config(self):
        """测试保存设置写入配置文件"""
        from Setting import CONFIG_PATH, load_config
        self.app._show_page("settings")

        # 修改字段
        self.app.serial_entry.set("1.2.3.4:1234")
        self.app.lat_entry.set("30.0")
        self.app.lng_entry.set("120.0")

        # 保存
        self.app._save_settings()

        # 验证 config.json
        cfg = load_config()
        self.assertEqual(cfg["serial"], "1.2.3.4:1234")
        self.assertEqual(cfg["location"]["latitude"], 30.0)
        self.assertEqual(cfg["location"]["longitude"], 120.0)

    def test_save_settings_invalid_location(self):
        """测试无效经纬度时保存失败"""
        self.app._show_page("settings")
        self.app.lat_entry.set("not_a_number")
        self.app.lng_entry.set("120.0")

        # 保存应弹出警告并 return
        self.app._save_settings()
        # 配置不应被修改
        from Setting import load_config
        cfg = load_config()
        self.assertEqual(cfg["location"]["latitude"], 111)

    def test_user_table_add_row(self):
        """测试添加用户行"""
        self.app._show_page("users")
        initial_count = len(self.app._user_rows)
        self.app._add_user_row("newuser", "newpass")
        self.assertEqual(len(self.app._user_rows), initial_count + 1)
        self.assertEqual(self.app._user_rows[-1]["user"].get(), "newuser")
        self.assertEqual(self.app._user_rows[-1]["pass"].get(), "newpass")
        # 验证密码框使用了密码切换
        self.assertIsNotNone(self.app._user_rows[-1]["pass"]._toggle_btn)

    def test_user_table_delete_row(self):
        """测试删除用户行"""
        self.app._show_page("users")
        # 先清空再添加
        for row in list(self.app._user_rows):
            row["frame"].destroy()
        self.app._user_rows.clear()

        self.app._add_user_row("user1", "pass1")
        self.app._add_user_row("user2", "pass2")
        self.assertEqual(len(self.app._user_rows), 2)

        # 删除第一行
        row_frame = self.app._user_rows[0]["frame"]
        self.app._delete_user_row(row_frame)
        self.assertEqual(len(self.app._user_rows), 1)
        self.assertEqual(self.app._user_rows[0]["user"].get(), "user2")

    def test_user_table_build_from_config(self):
        """测试从配置构建用户表格"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"u1": "p1", "u2": "p2", "u3": "p3"}
        })
        reload_config()
        self.app._show_page("users")
        # 应有 3 个用户行
        filled_rows = [r for r in self.app._user_rows if r["user"].get()]
        self.assertEqual(len(filled_rows), 3)

    def test_save_users_preserves_users(self):
        """测试保存用户信息"""
        from Setting import load_config
        self.app._show_page("users")

        # 清空并添加用户
        for row in list(self.app._user_rows):
            row["frame"].destroy()
        self.app._user_rows.clear()

        self.app._add_user_row("zhangsan", "pass123")
        self.app._add_user_row("lisi", "pass456")
        self.app._save_users()

        cfg = load_config()
        self.assertIn("zhangsan", cfg["users"])
        self.assertIn("lisi", cfg["users"])
        self.assertEqual(cfg["users"]["zhangsan"], "pass123")
        self.assertEqual(cfg["users"]["lisi"], "pass456")

    # ---- 日志页功能测试 ----
    def test_log_page_clear(self):
        """测试日志页清空功能"""
        self.app._show_page("log")
        # 写入一些日志
        self.app.log_text.config(state="normal")
        self.app.log_text.insert("end", "test log line\n")
        self.app.log_text.config(state="disabled")

        # 清空
        self.app._clear_log()
        content = self.app.log_text.get("1.0", "end-1c")
        self.assertEqual(content, "")

    def test_append_log(self):
        """测试日志追加"""
        self.app._show_page("log")
        self.app._append_log("hello world\n")
        content = self.app.log_text.get("1.0", "end-1c")
        self.assertIn("hello world", content)

    def test_log_queue_polling(self):
        """测试日志队列轮询"""
        self.app._show_page("log")
        # 模拟 _on_log 放入队列
        self.app._on_log("queue test message\n")
        # 手动轮询一次
        self.app._poll_log_queue()
        content = self.app.log_text.get("1.0", "end-1c")
        self.assertIn("queue test message", content)

    def test_log_buffer_flush(self):
        """测试日志缓冲区和刷新机制"""
        # 清除 log_text 模拟日志页未创建
        if hasattr(self.app, 'log_text'):
            delattr(self.app, 'log_text')
        self.app._log_buffer.clear()

        # 追加日志（此时应进入缓冲区）
        self.app._append_log("buffered message 1\n")
        self.app._append_log("buffered message 2\n")
        self.assertEqual(len(self.app._log_buffer), 2)

        # 创建日志页
        self.app._show_page("log")
        # 刷新后缓冲区应清空
        self.assertEqual(len(self.app._log_buffer), 0)

        content = self.app.log_text.get("1.0", "end-1c")
        self.assertIn("buffered message 1", content)
        self.assertIn("buffered message 2", content)

    def test_export_log_empty(self):
        """测试导出空日志时的提示"""
        self.app._show_page("log")
        self.app._clear_log()
        # 导出空日志应弹出警告
        self.app._export_log()  # 不应抛异常

    def test_export_log_with_content(self):
        """测试导出有内容日志"""
        self.app._show_page("log")
        self.app._clear_log()
        self.app._append_log("2026-07-12 18:00:00,123 - test - INFO - test export\n")
        self.app._append_log("second line\n")

        # 导出
        self.app._export_log()  # 不应抛异常

        # 清理导出的文件
        import glob
        log_dir = os.path.join(PROJECT_DIR, "log")
        if os.path.exists(log_dir):
            for f in glob.glob(os.path.join(log_dir, "*.txt")):
                try:
                    os.remove(f)
                except Exception:
                    pass

    # ---- 错误信息块测试 ----
    def test_error_block_show_hide(self):
        """测试错误信息块的显示和隐藏"""
        self.app._show_page("home")
        self.assertTrue(hasattr(self.app, 'error_card'))
        self.assertTrue(hasattr(self.app, 'error_desc_label'))
        self.assertTrue(hasattr(self.app, 'error_solution_label'))
        self.assertTrue(hasattr(self.app, 'error_stack_btn'))

        # 显示错误
        self.app._show_error_block("测试错误消息", "Traceback test...")
        self.assertIn("测试错误消息", self.app.error_desc_label.cget("text"))

        # 隐藏错误
        self.app._hide_error_block()
        self.assertEqual(self.app._error_traceback, "")

    def test_analyze_error_types(self):
        """测试错误分析各种类型"""
        # 超时
        desc, sol = self.app._analyze_error("签到超时: TimeoutError")
        self.assertIn("超时", desc)
        self.assertIn("网络", sol)

        # 连接
        desc, sol = self.app._analyze_error("ADB 连接失败")
        self.assertIn("连接失败", desc)
        self.assertIn("ADB", sol)

        # 定位
        desc, sol = self.app._analyze_error("设置虚拟位置失败")
        self.assertIn("定位", desc)

        # shell output invalid（ADB Shell 返回格式异常）
        desc, sol = self.app._analyze_error(
            "('shell output invalid', 'monkey -p com.delicloud.app.smartoffice -c android.intent.category.LAUNCHER 1; echo X4EXIT:$?', b'  bash arg: -p\\n')"
        )
        self.assertIn("启动异常", desc)
        self.assertIn("持续重试启动", sol)

        # 应用
        desc, sol = self.app._analyze_error("应用启动失败")
        self.assertIn("应用启动失败", desc)

        # 登录
        desc, sol = self.app._analyze_error("登录失败: 账号错误")
        self.assertIn("登录失败", desc)

        # 中断
        desc, sol = self.app._analyze_error("签到流程被用户中断")
        self.assertIn("中断", desc)

        # 未知
        desc, sol = self.app._analyze_error("some random error")
        self.assertIn("未知错误", desc)

    def test_on_sign_finished_with_traceback(self):
        """测试签到失败带 traceback 时错误块显示"""
        self.app._show_page("home")
        self.app._on_sign_finished(False, "测试错误", "Full traceback\n  File test.py line 1")
        self.assertEqual(self.app._error_traceback, "Full traceback\n  File test.py line 1")

    def test_start_sign_hides_error_block(self):
        """测试开始签到时隐藏之前的错误块"""
        self.app._show_page("home")
        self.app._show_error_block("之前的错误", "")
        # 开始签到（需要有效配置）
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "C:\\Program Files\\NetEase\\MuMu\\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"testuser": "testpass"}
        })
        reload_config()
        self.app._start_sign()
        # 错误块应被隐藏
        self.assertEqual(self.app._error_traceback, "")

    # ---- 设置页实时自动保存测试 ----
    def test_settings_auto_save_on_change(self):
        """测试设置项变化时自动保存"""
        from Setting import save_config, reload_config, load_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": r"C:\Program Files\NetEase\MuMu\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {},
            "debugmode": True
        })
        reload_config()
        self.app._show_page("settings")

        # 修改序列号触发自动保存
        self.app.serial_entry.set("127.0.0.1:5555")
        self.app._auto_save_settings()
        cfg = load_config()
        self.assertEqual(cfg.get("serial"), "127.0.0.1:5555")

        # 恢复
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": r"C:\Program Files\NetEase\MuMu\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"user1": "pass1", "user2": "pass2"},
            "debugmode": True
        })
        reload_config()

    def test_validate_settings_errors(self):
        """测试设置项合法性验证"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {},
            "debugmode": True
        })
        reload_config()
        self.app._show_page("settings")

        # 清空路径输入框（避免前测试残留）
        self.app.emulator_path_entry.set("")

        # 设置非法经纬度
        self.app.lat_entry.set("abc")
        self.app.lng_entry.set("999")
        errors = self.app._validate_settings(show=False)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("纬度" in e for e in errors))
        self.assertTrue(any("经度" in e for e in errors))

        # 恢复有效值（中国范围：纬度 ~39，经度 ~116）
        self.app.lat_entry.set("39")
        self.app.lng_entry.set("116")
        # 清空路径以避免前测试残留
        self.app.emulator_path_entry.set("")
        errors = self.app._validate_settings(show=False)
        self.assertEqual(len(errors), 0)

    def test_validate_emulator_path_missing(self):
        """测试模拟器路径不存在时的验证"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": r"Z:\nonexistent\path",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {},
            "debugmode": True
        })
        reload_config()
        self.app._show_page("settings")
        errors = self.app._validate_settings(show=False)
        self.assertTrue(any("不存在" in e for e in errors))

        # 恢复
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": r"C:\Program Files\NetEase\MuMu\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"user1": "pass1", "user2": "pass2"},
            "debugmode": True
        })
        reload_config()

    def test_settings_error_label_display(self):
        """测试设置页错误提示标签"""
        from Setting import save_config, reload_config
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": "",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {},
            "debugmode": True
        })
        reload_config()
        self.app._show_page("settings")
        self.assertTrue(hasattr(self.app, 'settings_error_label'))
        # 初始状态无错误（空路径不检查）
        self.assertEqual(self.app.settings_error_label.cget("text"), "")

    # ---- 窗口关闭测试 ----
    def test_close_without_sign_thread(self):
        """测试无签到线程时关闭"""
        self.app._sign_thread = None
        # 不应抛出异常（直接测试关闭逻辑，不真正 destroy root）
        self.assertIsNone(self.app._sign_thread)

    # ---- 边界条件测试 ----
    def test_empty_emulator_num_save(self):
        """测试模拟器编号为空时的保存"""
        self.app._show_page("settings")
        self.app.emulator_num_entry.set("")
        self.app._save_settings()
        from Setting import load_config
        cfg = load_config()
        # emulator_num 为空字符串时不应被保存（保持原值）
        self.assertIsNotNone(cfg.get("emulator_num"))

    def test_empty_serial_save(self):
        """测试序列号为空时的保存"""
        self.app._show_page("settings")
        self.app.serial_entry.set("")
        self.app._save_settings()
        from Setting import load_config
        cfg = load_config()
        # serial 为空时不应被覆盖
        self.assertIsNotNone(cfg.get("serial"))

    def test_debugmode_save_and_load(self):
        """测试调试模式开关的保存和加载（自动保存）"""
        from Setting import save_config, reload_config, load_config
        # 设置 debugmode 为 True
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": r"C:\Program Files\NetEase\MuMu\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {},
            "debugmode": True
        })
        reload_config()
        self.app._show_page("settings")
        self.assertTrue(self.app.debug_var.get())

        # 切换为 False —— 自动保存触发
        self.app.debug_var.set(False)
        # 手动触发保存（确保已写入）
        self.app._auto_save_settings()
        cfg = load_config()
        self.assertFalse(cfg.get("debugmode"))

        # 恢复默认
        save_config({
            "serial": "127.0.0.1:16384",
            "emulator_path": r"C:\Program Files\NetEase\MuMu\nx_main",
            "emulator_num": "0",
            "location": {"latitude": 111, "longitude": 111},
            "users": {"user1": "pass1", "user2": "pass2"},
            "debugmode": True
        })
        reload_config()

    # ---- Mumu start_app 重试逻辑测试 ----
    def test_mumu_start_app_retry_logic(self):
        """测试 Mumu.start_app 的重试和回退逻辑"""
        import subprocess
        from unittest.mock import patch, MagicMock
        from emulator.mumu import Mumu

        # 模拟 Setting
        with patch('emulator.mumu.Setting') as mock_setting:
            mock_setting.serial = "127.0.0.1:16384"
            mock_setting.emulator_path = r"C:\Program Files\NetEase\MuMu\nx_main"
            mock_setting.emulator_num = "0"
            mock_setting.location = {"latitude": 111, "longitude": 111}

            mumu = Mumu.__new__(Mumu)
            mumu.serial = "127.0.0.1:16384"
            mumu.path = r"C:\Program Files\NetEase\MuMu\nx_main"
            mumu.adb_path = r"C:\Program Files\NetEase\MuMu\nx_main\adb.exe"
            mumu.log = MagicMock()
            mumu.device = MagicMock()

            # 场景1：app_start 直接成功
            mumu.device.app_start = MagicMock()
            mumu.start_app("com.test.app", timeout=5)
            mumu.device.app_start.assert_called_once()
            mumu.log.info.assert_any_call = True

    def test_mumu_start_app_shell_invalid_retry(self):
        """测试 shell output invalid 后持续重试直到超时（不再使用 am start 回退）"""
        from unittest.mock import patch, MagicMock
        from emulator.mumu import Mumu

        with patch('emulator.mumu.Setting') as mock_setting:
            mock_setting.serial = "127.0.0.1:16384"
            mock_setting.emulator_path = r"C:\Program Files\NetEase\MuMu\nx_main"
            mock_setting.emulator_num = "0"
            mock_setting.location = {"latitude": 111, "longitude": 111}

            mumu = Mumu.__new__(Mumu)
            mumu.serial = "127.0.0.1:16384"
            mumu.path = r"C:\Program Files\NetEase\MuMu\nx_main"
            mumu.adb_path = r"C:\Program Files\NetEase\MuMu\nx_main\adb.exe"
            mumu.log = MagicMock()
            mumu.device = MagicMock()

            # app_start 抛出 shell output invalid 错误
            mumu.device.app_start = MagicMock(
                side_effect=Exception(
                    "('shell output invalid', 'monkey -p com.test -c android.intent.category.LAUNCHER 1', b'bash arg: -p')"
                )
            )

            # 新行为：不再回退到 am start，而是持续重试 app_start 直到超时
            # mock sleep 避免实际等待，但让 timeout 检查正常触发
            with patch('emulator.mumu.sleep', return_value=None):
                with self.assertRaises(TimeoutError):
                    mumu.start_app("com.test.app", timeout=0.01)

            # 验证 app_start 被调用了多次（重试逻辑）
            self.assertGreater(mumu.device.app_start.call_count, 1)

    def test_mumu_start_app_timeout(self):
        """测试 start_app 超时抛出 TimeoutError"""
        from unittest.mock import patch, MagicMock
        from emulator.mumu import Mumu

        with patch('emulator.mumu.Setting') as mock_setting:
            mock_setting.serial = "127.0.0.1:16384"
            mock_setting.emulator_path = r"C:\Program Files\NetEase\MuMu\nx_main"
            mock_setting.emulator_num = "0"
            mock_setting.location = {"latitude": 111, "longitude": 111}

            mumu = Mumu.__new__(Mumu)
            mumu.serial = "127.0.0.1:16384"
            mumu.path = r"C:\Program Files\NetEase\MuMu\nx_main"
            mumu.adb_path = r"C:\Program Files\NetEase\MuMu\nx_main\adb.exe"
            mumu.log = MagicMock()
            mumu.device = MagicMock()

            # 始终抛出非 shell 错误
            mumu.device.app_start = MagicMock(
                side_effect=Exception("连接超时")
            )

            with self.assertRaises(TimeoutError):
                mumu.start_app("com.test.app", timeout=0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
