# Deli_EPlus_AutoSignUp

得力 E+ 自动签到工具。控制 MuMu 模拟器完成「登录 → 虚拟定位 → 打卡 → 登出」全流程，
支持多账号顺序执行，提供 GUI 与 CLI 两种使用方式。

- 作者：**xinbaji**
- 仓库：<https://github.com/xinbaji/Deli_EPlus_AutoSignUp>
- 问题反馈：<https://github.com/xinbaji/Deli_EPlus_AutoSignUp/issues>

---

## 一、EXE 版（普通用户）

1. 下载安装 [MuMu 模拟器](https://mumu.163.com/)，并在模拟器设置中开启 ROOT 与 ADB 调试。
2. 从 [Releases](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/releases) 下载便携 zip，解压后运行 `Deli_EPlus_AutoSignUp.exe`（Win10/11 自带 WebView2，无需安装）。
3. 首次使用按顺序配置：
   - **设置页 → 模拟器**：选择 MuMu 安装目录，点「一键检测」确认 ADB 可连接；
   - **设置页 → 虚拟定位**：填写考勤点经纬度，可点「测试定位」验证；
   - **账号页**：添加手机号与密码（配置保存在 exe 旁边的 `config.json`，可随时导出/导入备份）。
4. 回到主页点「开始签到」。左侧状态列表实时显示每个账号进度，下方「运行动态」展示每一步动作。
5. 出错时会在页面弹出错误卡片，含原因与建议；详细日志在 `logs/` 目录，反馈问题时请附带。

## 二、开发环境

```bash
# 1. 创建虚拟环境并安装依赖（含 pytest / pyinstaller）
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"

# 2. 运行测试（全部用假设备，无需模拟器）
.venv/Scripts/pytest

# 3. 启动 GUI / CLI
.venv/Scripts/python -m deli_eplus.gui
.venv/Scripts/python -m deli_eplus --debug     # 调试签到：不实际打卡

# 4. 打包
.venv/Scripts/python scripts/build.py          # 目录版 + 便携 zip（发 release 用）
```

## 三、项目结构

```
├── src/deli_eplus/
│   ├── gui.py / cli.py          两个入口（GUI 打包为 exe；CLI 供无界面场景）
│   ├── config.py                config.json 读写（原子保存 / 损坏自动备份 / 导入导出）
│   ├── log.py                   一套 logging 三处输出：控制台 / 按天轮转文件 / UI 活动流
│   ├── device/                  ★ 设备操作层，不依赖业务，可整体复用
│   │   ├── base.py              find/exists/wait_any/wait_gone/click/type_text（真等待语义）
│   │   ├── mumu.py              MuMu 专属：启动模拟器、MuMuManager 虚拟定位
│   │   └── exceptions.py        类型化异常
│   ├── core/signup.py           唯一签到流程（GUI 与 CLI 共用）
│   ├── webui.py                 pywebview 窗口 + JS API 桥 + 事件推送
│   └── web/                     前端（Fluent 2 设计语言，纯 HTML/CSS/JS，零构建步骤）
├── tests/                       pytest 测试（ScriptedDevice / FakeU2，秒级跑完）
├── tools/                       dump_ui.py 排查选择器；gen_icons_css.py 生成图标样式
├── scripts/                     打包：spec + build.py + installer.iss
└── assets/fonts/                Bootstrap Icons 字体源（生成 web/fonts 的图标样式）
```

## 四、config.json 字段

| 字段 | 说明 |
|---|---|
| `serial` | adb 序列号，MuMu 默认 `127.0.0.1:16384` |
| `emulator_path` | MuMu 安装目录（包含 `MuMuManager.exe`） |
| `emulator_num` | MuMu 实例号 |
| `location` | 打卡经纬度 `{"latitude": 45.0, "longitude": 45.0}` |
| `users` | 账号 `{"手机号": "密码"}` |

配置文件损坏时会自动备份为 `config.json.bak-<时间戳>` 并用默认值启动，不会静默覆写。

## 五、常见问题

- **提示"等待元素超时"**：App 界面与预期不符（版本更新改版/弹窗），可用 `tools/dump_ui.py` 抓界面层级核对选择器。
- **提示"模拟器启动后仍无法连接"**：确认 MuMu 能手动打开、ADB 调试已开启、设置页 serial 与模拟器实例一致。
- **卡死了怎么办**：所有等待都有超时，卡死会在超时后转为明确报错并标记该账号失败，不会无限挂起。
