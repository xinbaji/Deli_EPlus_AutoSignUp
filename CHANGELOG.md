# 更新日志

本文件记录项目的所有重要变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> 本文件自 v1.4.0 起建立；更早版本的变更请看
> [提交历史](https://github.com/xinbaji/Deli_EPlus_AutoSignUp/commits/main)。

## [1.4.2] - 2026-09-30

### 修复

- **弹窗按钮选择器锁死了控件类别**（真机「元素明明在屏幕上、程序却检测不到」的根因）：
  通用弹窗的「确定」「同意并继续」原本写死 `//android.widget.TextView[@text=...]`。
  实测模拟器上其他 App 的协议弹窗用的是 `android.widget.Button` → 选择器判否 →
  弹窗关不掉；而 uiautomator 的 `dumpWindowHierarchy` **只返回最上层窗口**，
  弹窗一挡，底层得力 App 的控件在层级里整体"消失"，只能一路等到超时
  （「120 秒内未能进入登录页」）。改为 `//*[@text=...]`，不再限定控件类别。
- **等待「智能考勤」时被弹窗遮挡无法自愈**：`click_until` 新增 `on_round` 每轮回调，
  等待期间先清遮挡弹窗再判定元素，避免底层控件被"遮没"后空等到超时。

### 变更

- 「点同意并继续 → 出现智能考勤」的等待预算由固定 15 秒放宽到
  `ENTER_HOME_TIMEOUT = 45` 秒；预算只是上限，元素出现即返回，快态仍是约 3.5 秒。
- 命中「智能考勤」后直接用 `click_until` 已定位到的元素点击，不再二次查找——出现即点。

### 开发

- `tests_local/run_timing.py`：新增 `--no-start`（模拟器已在运行时跳过 `launch`，
  直接连接，避开 launch 触发实例重启的窗口）；探针补挂 `Element.click`
  （"命中即点"不经过 `AndroidDevice.click`，此前这类点击在计时里会整个丢失）。
- 新增 6 条回归测试（`on_round` 每轮执行/抛错不中断/停止令牌透传、弹窗遮挡自愈、
  选择器不锁控件类别），测试总数 101 → **107**。

## [1.4.1] - 2026-09-28

### 修复

- **经纬度校验误报**：`Api.save_location` 里 `except (TypeError, ValueError)` 排在
  `except ConfigError` 前面，而 `ConfigError` 是 `ValueError` 的子类 —— 于是「超出范围」
  被前一个分支抢走、报成「经纬度必须是数字」。用户明明输入的是数字（例如 `999`），
  却收到「必须是数字」，还以为是没存进 `config.json`。已把 `ConfigError` 提到前面。
- **输入框清空时的误报**：经纬度有 700ms 防抖自动保存，框被清空（重新输入的空档）也会
  发一次请求，`float("")` 直接报「必须是数字」。现在两端都判空：后端返回
  `{"ok": true, "skipped": true}`，前端静默跳过、不弹任何错误。
- `Config.set_location` 不再把「不是数字」包装成 `ConfigError`：GUI/CLI 都在更外层先校验，
  这一层只做范围检查，避免那句提示误导用户。
- **GUI「停止」按钮失效**：`_StopToken.stopped` 是返回 bool 的 property，却被直接当回调
  传给 `SignupFlow(stop_check=...)`；构造时它为 `False`，被 `stop_check or (lambda: False)`
  兜底吞掉，导致停止令牌永远读不到。改为传 `lambda: self._stop_token.stopped`。

### 新增

- `LICENSE`：明确 MIT 许可（`pyproject.toml` 里此前只声明了 license 字段）。
- 静态检查门：引入 **ruff**（lint）、**black**（格式化）、**mypy**（类型检查），
  已加进 `dev` 依赖，并在 CI 与发版流程里前置执行（不通过则不出包）。

### 测试

- 离线用例 +15（`click_until` 轮询与停止令牌、失效弹窗监听线程、遮挡弹窗自愈、上滑时长、
  弹窗优先级、经纬度空值/超范围/非数字），套件合计 101 条，全部通过。

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
