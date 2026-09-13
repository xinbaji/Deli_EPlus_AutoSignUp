# 更新日志

本文件记录项目的所有重要变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 本文件自 v1.4.0 起建立；更早版本的变更请看
> [提交历史](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/commits/main)。

## [未发布]

### 新增

- `LICENSE`：明确 MIT 许可（`pyproject.toml` 里此前只声明了 license 字段）。
- 静态检查门：引入 **ruff**（lint）、**black**（格式化）、**mypy**（类型检查），
  已加进 `dev` 依赖，并在 CI 与发版流程里前置执行（不通过则不出包）。

### 修复

- **GUI「停止」按钮失效**：`_StopToken.stopped` 是返回 bool 的 property，却被直接当回调
  传给 `SignupFlow(stop_check=...)`；构造时它为 `False`，被 `stop_check or (lambda: False)`
  兜底吞掉，导致停止令牌永远读不到。改为传 `lambda: self._stop_token.stopped`。

## [1.4.0] - 2026-09-13

### 新增

- **失效弹窗后台监听**：App 启动后开一个后台线程盯「您登录的账号已失效，请重新登录」弹窗，
  出现即点「确定」回到登录页。该弹窗每个登录流程最多出现一次，主流程不必为它加分支；
  线程随「进入登录页」阶段结束而收口，不留后台线程。
- 本地调试工具：`tests_local/run_timing.py`（真机各阶段计时）、`tests_local/run_detect_gap.py`
  （选择器漏检扫描）、`tests_local/make_speed_report.py`（计时结果汇总成报告）。

### 修复

- **界面明明有目标元素，程序却检测不到**：uiautomator 的 `dumpWindowHierarchy` 只返回
  **最上层窗口**——任何弹窗（服务协议、登录失效、权限提示…）一出现，底层 Activity 的控件在
  层级里整体消失，于是界面正常却判定「元素不存在」。实测会导致 `_enter_login_page` 卡满
  120 秒后整轮中止。现在该阶段每一步判定前都会先关掉遮挡弹窗（「确定」/「同意并继续」）。
- **退出登录失败不再中止整轮**：会话失效时 `_logout` 的失败可由「关弹窗 → 回登录页」自愈，
  并加了超时兜底，避免反复退出/弹窗时无限循环。
- **设置页上滑改为 0.2s 快滑**（原 0.3s）：真机实测每次都是第 1 次上滑即露出「退出登录」。

### 变更

- `click_until` 语义调整：点一次源按钮后**立即**在 0.2 秒内查目标元素，未出现则再点源按钮，
  如此循环直至超时；源按钮一旦消失就不再回头补点（避免对同一按钮高频连点）。

### 测试

- 离线用例 +12（`click_until` 轮询与停止令牌、失效弹窗监听线程、遮挡弹窗自愈、上滑时长），
  套件合计 98 条，全部通过。
