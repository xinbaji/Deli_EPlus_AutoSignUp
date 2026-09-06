# script/ 脚本说明

本文件夹集中存放构建与启动脚本。所有脚本**不依赖当前工作目录**，从任意位置调用均可。

## 一键上手

| 想做什么 | 用哪个 | 怎么用 |
|---|---|---|
| 源码运行程序（开发调试） | `run.bat` | 双击，或任意位置执行 |
| 打包发布（出便携 zip） | `build.py` | `.venv\Scripts\python script\build.py` |
| 跑全部测试 | 仓库根目录 | `.venv\Scripts\pytest` |
| 跑不能进 CI 的本地测试 | `test_local.bat` | 双击（需要真实模拟器环境） |

## 脚本明细

### run.bat —— 源码启动
- 自动定位仓库根目录下的 `.venv\Scripts\python.exe` 启动 GUI
- 没有虚拟环境会提示先执行：`python -m venv .venv` + `pip install -e ".[dev]"`

### build.py —— 打包
- 流程：PyInstaller onedir 构建 → 校验产物 → 压缩便携 zip
- 产物（都在仓库根 `dist\`）：
  - `Deli_EPlus_AutoSignUp\` 目录版（解压即用，启动最快）
  - `Deli_EPlus_AutoSignUp_portable.zip` 便携包（发 GitHub Release 用）
- 内置硬超时与详细日志，失败会打印具体原因
- 推送 `v*` 标签后，GitHub Actions 会自动跑同样的构建并发 Release

### test_local.bat —— 本地测试入口
- 运行**无法在 CI 远程执行**的本地测试（需要真实模拟器/设备的用例）
- CI 只跑纯软件测试；两边合起来才是完整覆盖

## 常见问题

- **打包报找不到文件**：确认在仓库根目录存在 `script\Deli_EPlus.spec` 与 `assets\`
- **启动提示缺依赖**：`.venv\Scripts\pip install -e ".[dev]"`
- **zip 里文件在根层**：这是故意的——自动更新解压时直接覆盖安装目录
