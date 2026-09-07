<div align="center">

<img src="assets/app.ico" width="80" alt="Deli E+ AutoSignUp 图标">

# Deli_EPlus_AutoSignUp

**得力 E+ 自动签到工具**

控制 MuMu 模拟器完成「登录 → 虚拟定位 → 打卡 → 登出」全流程，多账号顺序执行，GUI 与 CLI 双入口。

[![CI Tests](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/actions/workflows/ci.yml/badge.svg)](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/xinbaji/Deli_EPlus_AutoSignUp)](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/releases)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

## 功能特性

- **全流程自动化**：启动 MuMu 实例（官方 `MuMuManager control launch`）→ 打开 App → 自动跳过广告、退出已登录账号 → 逐账号登录 → MuMu 虚拟定位 → 智能考勤打卡 → 退出登录
- **多账号批量执行**：顺序签到，单个账号失败不影响后续，结束时汇总成功/失败数
- **GUI / CLI 双入口**：GUI 基于 pywebview + Fluent 2 风格前端（纯 HTML/CSS/JS，零构建步骤）；CLI 供无界面场景，两者共用同一套签到流程
- **调试模式**：`--debug` 走完整流程但跳过实际打卡，用于验证配置与界面选择器
- **稳健执行**：所有等待带超时、关键点击带验证（无效自动补点）、每阶段边界响应停止令牌——卡死会转为明确报错，不会无限挂起
- **应用内自更新**：后台检查 GitHub Release（直连 / 镜像源自动择优回退），下载便携 zip 后自动重启替换，不动用户数据
- **开机自启**（打包版）：写入 HKCU Run 注册表键，无需管理员权限
- **日志三路输出**：控制台 / 按天轮转文件（`logs/`）/ GUI 实时活动流

## 快速开始（EXE 版）

> [!NOTE]
> 前置要求：Windows 10/11、[MuMu 模拟器](https://mumu.163.com/)，得力E+，并在模拟器设置->性能设置->高性能。

1. 从 [Releases](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/releases) 下载便携 zip，解压后运行 `Deli_EPlus_AutoSignUp.exe`（Win10/11 自带 WebView2，无需额外安装）。
2. 首次使用按顺序配置：
   - **设置页 → 模拟器**：选择 MuMu 安装目录
   - **设置页 → 虚拟定位**：填写考勤点经纬度，在mumu自带的虚拟定位功能中可查询到
   - **账号页**：添加手机号与密码（配置保存在 exe 旁边的 `config.json`，可随时导出/导入备份）。
3. 回到主页点「开始签到」。左侧状态列表实时显示每个账号进度，下方「运行动态」展示每一步动作。
4. 出错时页面会弹出错误卡片，含原因与建议；详细日志在 `logs/` 目录，反馈问题时请附带。

> [!IMPORTANT]
> 账号密码以明文保存在本地 `config.json` 中（已被 `.gitignore` 排除，不会入库），请勿将配置文件分享给他人。

## 从源码运行

```bash
# 1. 创建虚拟环境并安装依赖（含 pytest / pyinstaller）
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"

# 2. 运行离线测试（全部用假设备，无需模拟器；CI 同款）
.venv/Scripts/pytest

# 2b. 本地真机测试（连真实 MuMu，模拟器没开会自动拉起）
#     覆盖 CI 测不了的部分：启动实例 / ADB 连接 / UI dump / App 启动
script\test_local.bat                    # 或 .venv/Scripts/pytest tests_local -v

# 3. 启动 GUI / CLI
.venv/Scripts/python -m deli_eplus.gui
.venv/Scripts/python -m deli_eplus --debug     # 调试签到：不实际打卡

# 4. 打包（目录版 + 便携 zip，发 Release 用）
.venv/Scripts/python script/build.py
```

## 配置说明

配置文件为 exe / 项目根目录下的 `config.json`，损坏时会自动备份为 `config.json.bak-<时间戳>` 并用默认值启动，不会静默覆写。

| 字段 | 说明 | 默认值 |
|---|---|---|
| `serial` | ADB 序列号，MuMu 默认 `127.0.0.1:16384` | `127.0.0.1:16384` |
| `emulator_path` | MuMu 安装目录（包含 `MuMuManager.exe`） | — |
| `emulator_num` | MuMu 实例号 | `0` |
| `location` | 打卡点经纬度 `{"latitude": 41.0, "longitude": 122.0}` | — |
| `users` | 账号字典 `{"手机号": "密码"}`，按插入顺序执行 | — |
| `theme` | 界面主题 | `dark` |
| `download_source` | 更新下载源：`github`（直连）/ `mirror`（加速镜像） | `github` |

## 项目结构

```
├── src/deli_eplus/
│   ├── gui.py / cli.py          两个入口（GUI 打包为 exe；CLI 供无界面场景）
│   ├── config.py                config.json 读写（原子保存 / 损坏自动备份 / 导入导出）
│   ├── log.py                   一套 logging 三处输出：控制台 / 按天轮转文件 / UI 活动流
│   ├── webui.py                 pywebview 窗口 + JS API 桥 + 事件推送
│   ├── autostart.py             开机自启（HKCU Run 键，仅打包版）
│   ├── updater.py               版本检查与自更新（直连 / 镜像自动回退）
│   ├── device/                  ★ 设备操作层，不依赖业务，可整体复用
│   │   ├── base.py              find / wait_any / click_until / wait_gone（真等待语义）
│   │   ├── mumu.py              MuMu 专属：启动实例、MuMuManager 虚拟定位
│   │   └── exceptions.py        类型化异常
│   ├── core/signup.py           唯一签到流程实现（GUI 与 CLI 共用）
│   └── web/                     前端（Fluent 2 设计语言，纯 HTML/CSS/JS，零构建步骤）
├── tests/                       pytest 离线测试（ScriptedDevice / FakeU2，秒级跑完）
├── tests_local/                 本地真机测试（连真实 MuMu，CI 不收集）
├── script/                      run.bat / test_local.bat / build.py / Deli_EPlus.spec
├── tools/                       dump_ui.py 排查选择器；gen_icons_css.py 生成图标样式
└── assets/                      应用图标与图标字体源
```

架构上，`device/` 层只封装 adb / uiautomator 通用操作，MuMu 专属能力（拉起实例、虚拟定位）独立在 `MuMuDevice` 子类中——更换其他模拟器（雷电、夜神…）只需照着写一个对应子类，`core/signup.py` 无需改动。

## 常见问题

- **提示「等待元素超时」**：App 界面与预期不符（版本更新改版 / 弹窗），可用 `tools/dump_ui.py` 抓取界面层级核对选择器。
- **提示「模拟器启动后仍无法连接」**：确认 MuMu 能手动打开、ADB 调试已开启、设置页的 serial 与模拟器实例一致。
- **程序卡死了怎么办**：所有等待都有超时，卡死会在超时后转为明确报错并标记该账号失败，不会无限挂起。
- **打卡未生效**：确认虚拟定位经纬度在考勤点附近；可在「设置页 → 虚拟定位」点「测试定位」后打开 App 人工核对。

## 作者

**xinbaji** · [仓库](https://github.com/xinbaji/Deli_EPlus_AutoSignUp) · [问题反馈](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/issues)
