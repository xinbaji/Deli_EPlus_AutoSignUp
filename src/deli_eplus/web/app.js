/* 得力E+ 自动签到前端逻辑
   与 Python 的通信：
   - 调用后端：await window.pywebview.api.xxx()
   - 后端推送：window.__pushEvent({type, data})
   视图不持有业务状态，全部从后端拉取/由事件驱动。 */
"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  users: {},          // phone -> password（账号页渲染用）
  accountStates: {},  // phone -> {state, message}（主页状态表用）
  feedFollow: true,
  running: false,
  editing: null,      // 编辑中的旧手机号；null = 新增
  confirmAction: null,
};

/* ============ 启动 ============ */

let booted = false;
async function waitApi() {
  for (let i = 0; i < 200; i++) {          // 最多等 20s
    if (window.pywebview && window.pywebview.api) return;
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("后端桥接超时");
}

async function startBoot() {
  if (booted) return;
  booted = true;
  try {
    await waitApi();
    await boot();
  } catch (e) {
    document.title = "BOOT ERR: " + (e && e.message || e);
  }
}

// pywebviewready 事件与桥注入的时序不保证，轮询兜底（双启动有 booted 保护）
window.addEventListener("pywebviewready", startBoot);
startBoot();

async function boot() {
  const api = window.pywebview.api;
  let init;
  try {
    init = await api.get_initial();
  } catch (e) {
    $("preview").textContent = "初始化失败：" + e;
    return;
  }
  applyTheme(init.theme === "dark", false);
  fillAbout(init.app);
  markUpdateSource(init.download_source || "github");
  window.pywebview.api.check_update().then(applyUpdateCheck).catch(() => {});
  fillSettings(init);
  state.users = init.users || {};
  renderAccounts();
  renderPreview(init);
  renderStatusList();
  bindNav();
  bindHome();
  bindAccounts();
  bindSettings();
  switchView("home");
}

/* ============ 视图切换 ============ */

function switchView(name) {
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== "view-" + name));
  document.querySelectorAll(".nav-item[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  const onShow = { home: onHomeShow, accounts: onAccountsShow, settings: onSettingsShow }[name];
  onShow && onShow();
}

function bindNav() {
  document.querySelectorAll(".nav-item[data-view]").forEach((b) =>
    b.addEventListener("click", () => switchView(b.dataset.view)));
  $("theme-toggle").addEventListener("click", async () => {
    const dark = !document.body.classList.contains("dark");
    applyTheme(dark, true);
    await window.pywebview.api.set_theme(dark);
  });
}

function onHomeShow() {
  window.pywebview.api.get_config_brief().then((brief) => {
    renderPreview(brief);
    state.users = brief.users || {};
    renderStatusList();
  });
}
function onAccountsShow() { renderAccounts(); }
function onSettingsShow() {
  window.pywebview.api.get_config_brief().then(fillSettings);
}

/* ============ 主题 ============ */

function applyTheme(dark, animate) {
  document.body.classList.toggle("dark", dark);
  document.body.classList.toggle("light", !dark);
  $("theme-ic").className = "bi nav-ic " + (dark ? "bi-sun" : "bi-moon-stars");
  $("theme-label").textContent = dark ? "浅色主题" : "深色主题";
}

/* ============ 主页 ============ */

function bindHome() {
  $("btn-start").addEventListener("click", () => startSignup(false));
  $("btn-stop").addEventListener("click", stopSignup);
  $("btn-open-logs").addEventListener("click", () => window.pywebview.api.open_logs());
  $("btn-open-logs2").addEventListener("click", () => window.pywebview.api.open_logs());
  $("btn-follow").addEventListener("click", toggleFollow);
  $("btn-error-logs").addEventListener("click", () => window.pywebview.api.open_logs());
  $("btn-error-copy").addEventListener("click", copyError);
  $("btn-error-detail").addEventListener("click", () => {
    const pre = $("error-detail");
    pre.hidden = !pre.hidden;
    $("btn-error-detail").textContent = pre.hidden ? "技术详情" : "收起详情";
  });
}

async function startSignup(debug) {
  hideError();
  const res = await window.pywebview.api.start_signup(debug);
  if (!res.ok) {
    showError(debug ? "无法开始调试签到" : "无法开始签到", res.error, "");
    return;
  }
  switchView("home");
}

async function stopSignup() {
  setBusy(false); // 事件回来前先恢复按钮，避免误双击
  await window.pywebview.api.stop_signup();
}

function renderPreview(brief) {
  const emu = brief.emulator_path
    ? `MuMu 实例 ${brief.emulator_num}（${brief.serial}）` : "未配置模拟器路径";
  $("preview").textContent =
    `共 ${Object.keys(brief.users || {}).length} 个账号，` +
    `定位 ${Number(brief.latitude).toFixed(2)}, ${Number(brief.longitude).toFixed(2)}，${emu}`;
}

function renderStatusList() {
  const list = $("status-list");
  const phones = Object.keys(state.users);
  if (!phones.length || !Object.keys(state.accountStates).length) {
    list.innerHTML = `<div class="empty-mini">开始签到后，这里会逐个显示每个账号的进度</div>`;
    $("status-summary").textContent = `共 ${phones.length} 个账号`;
    return;
  }
  list.innerHTML = phones.map((p) => {
    const st = state.accountStates[p] || { state: "pending", message: "" };
    const done = st.state === "done" ? st.doneAt || "" : esc(st.message);
    return `<div class="srow ${st.state === "failed" ? "failed" : ""}" data-phone="${esc(p)}">
      <span class="phone">${mask(p)}</span>
      <span class="msg">${done}</span>
      <span class="pill ${st.state}">${pillText(st.state)}</span>
    </div>`;
  }).join("");
  list.querySelectorAll(".srow.failed").forEach((row) =>
    row.addEventListener("click", () => {
      const p = row.dataset.phone;
      showError(`账号 ${mask(p)} 签到失败`, state.accountStates[p].message, "");
    }));
  const states = Object.values(state.accountStates);
  const done = states.filter((s) => s.state === "done").length;
  const failed = states.filter((s) => s.state === "failed").length;
  $("status-summary").textContent =
    `本轮 ${done}/${states.length} 完成` + (failed ? `，${failed} 失败` : "");
}

/* ============ 运行动态 ============ */

const FEED_ICON = {
  success: "bi-check-circle-fill",
  warning: "bi-exclamation-triangle-fill",
  danger: "bi-x-circle-fill",
  info: "bi-arrow-right-short",
};

function appendFeed(message, level) {
  const feed = $("feed");
  if (feed.querySelector(".empty-mini")) feed.innerHTML = "";
  const kind = level >= 40 ? "danger" : level >= 30 ? "warning"
    : level >= 25 ? "success" : "info";
  const ts = message.slice(0, 8);
  const body = message.includes("  ") ? message.slice(message.indexOf("  ") + 2) : message;
  const line = document.createElement("div");
  line.className = "feed-line " + kind;
  line.innerHTML =
    `<i class="bi ${FEED_ICON[kind]}"></i><span class="ts">${esc(ts)}</span><span>${esc(body)}</span>`;
  feed.appendChild(line);
  while (feed.children.length > 400) feed.removeChild(feed.firstChild);
  if (state.feedFollow) feed.scrollTop = feed.scrollHeight;
}

function toggleFollow() {
  state.feedFollow = !state.feedFollow;
  $("btn-follow").textContent = state.feedFollow ? "暂停滚动" : "跟随滚动";
  if (state.feedFollow) $("feed").scrollTop = $("feed").scrollHeight;
}

/* ============ 状态条 ============ */

function setStatus(kind, text, pulse) {
  const chip = $("status-chip");
  chip.className = "status-chip " + kind;
  $("status-dot").className = "dot" + (pulse ? " pulse" : "");
  $("status-text").textContent = text;
}

function setBusy(running) {
  state.running = running;
  $("btn-start").disabled = running;
  $("btn-stop").disabled = !running;
  $("btn-debug").disabled = running;
}

/* ============ 错误卡片 ============ */

function showError(title, message, detail) {
  $("error-title").textContent = title;
  $("error-message").textContent = message;
  $("error-detail").textContent = detail || "";
  $("error-detail").hidden = true;
  $("btn-error-detail").hidden = !detail;
  $("btn-error-detail").textContent = "技术详情";
  $("error-card").hidden = false;
  $("error-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideError() { $("error-card").hidden = true; }

async function copyError() {
  const text = $("error-title").textContent + "\n" +
    $("error-message").textContent +
    ($("error-detail").textContent ? "\n\n" + $("error-detail").textContent : "");
  try { await navigator.clipboard.writeText(text); toast("已复制到剪贴板", "ok"); }
  catch { toast("复制失败", "bad"); }
}

/* ============ 账号页 ============ */

function bindAccounts() {
  $("btn-add").addEventListener("click", () => openAccountModal(null));
  $("btn-export").addEventListener("click", async () => {
    const res = await window.pywebview.api.export_config();
    if (res.ok) toast("已导出：" + res.path, "ok"); else if (res.error) toast(res.error, "bad");
  });
  $("btn-import").addEventListener("click", async () => {
    const res = await window.pywebview.api.import_config();
    if (res.cancelled) return;
    if (!res.ok) { toast("导入失败：" + res.error, "bad"); return; }
    state.users = res.users;
    renderAccounts(); renderStatusList(); onHomeShow();
    toast("导入成功", "ok");
  });
  bindModal();
}

function renderAccounts() {
  const box = $("account-list");
  const phones = Object.keys(state.users);
  if (!phones.length) {
    box.innerHTML = `<div class="empty-state">
      <i class="bi bi-people"></i>
      <div class="t">还没有账号</div>
      <div class="d">点击右上角「添加账号」开始，或导入已有配置</div>
    </div>`;
    return;
  }
  box.innerHTML = phones.map((p) => `
    <div class="arow" data-phone="${esc(p)}">
      <span class="phone">${mask(p)}</span>
      <span class="pwd">
        <span class="value" data-shown="0">••••••••</span>
        <button class="icon-btn eye" title="显示/隐藏密码"><i class="bi bi-eye"></i></button>
      </span>
      <span class="actions">
        <button class="icon-btn edit" title="编辑"><i class="bi bi-pencil"></i></button>
        <button class="icon-btn danger del" title="删除"><i class="bi bi-trash3"></i></button>
      </span>
    </div>`).join("");

  box.querySelectorAll(".arow").forEach((row) => {
    const p = row.dataset.phone;
    row.querySelector(".eye").addEventListener("click", (e) => {
      const val = row.querySelector(".value");
      const shown = val.dataset.shown === "1";
      val.dataset.shown = shown ? "0" : "1";
      val.textContent = shown ? "••••••••" : state.users[p];
      e.currentTarget.firstElementChild.className = "bi " + (shown ? "bi-eye" : "bi-eye-slash");
    });
    row.querySelector(".edit").addEventListener("click", () => openAccountModal(p));
    row.querySelector(".del").addEventListener("click", () => confirmDelete(p));
  });
}

function openAccountModal(phone) {
  state.editing = phone;
  $("modal-title").textContent = phone ? "编辑账号" : "添加账号";
  $("modal-phone").value = phone || "";
  $("modal-pwd").value = phone ? state.users[phone] : "";
  $("modal-error").textContent = "";
  $("modal-mask").hidden = false;
  setTimeout(() => $(phone ? "modal-pwd" : "modal-phone").focus(), 30);
}

function bindModal() {
  const close = () => { $("modal-mask").hidden = true; state.editing = null; };
  $("modal-cancel").addEventListener("click", close);
  $("modal-mask").addEventListener("mousedown", (e) => { if (e.target === $("modal-mask")) close(); });
  $("modal-ok").addEventListener("click", saveAccount);
  $("modal-pwd").addEventListener("keydown", (e) => { if (e.key === "Enter") saveAccount(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!$("modal-mask").hidden) close();
      if (!$("confirm-mask").hidden) $("confirm-mask").hidden = true;
    }
  });
}

async function saveAccount() {
  const phone = $("modal-phone").value.trim();
  const pwd = $("modal-pwd").value;
  const old = state.editing;
  const res = old
    ? await window.pywebview.api.update_account(old, phone, pwd)
    : await window.pywebview.api.add_account(phone, pwd);
  if (!res.ok) { $("modal-error").textContent = res.error; return; }
  $("modal-mask").hidden = true;
  state.editing = null;
  state.users = res.users;
  renderAccounts(); renderStatusList(); onHomeShow();
}

function confirmDelete(phone) {
  $("confirm-text").textContent = `确定删除账号 ${mask(phone)} 吗？此操作不可撤销。`;
  $("confirm-mask").hidden = false;
  state.confirmAction = async () => {
    const res = await window.pywebview.api.remove_account(phone);
    if (res.ok) {
      state.users = res.users;
      renderAccounts(); renderStatusList(); onHomeShow();
    }
  };
}

/* ============ 设置页 ============ */

function fillAbout(app) {
  $("about-app").textContent = `${app.name}  v${app.version}`;
  $("about-author").textContent = app.author;
  const repo = $("about-repo");
  repo.textContent = app.repo;
  repo.onclick = (e) => { e.preventDefault(); window.pywebview.api.open_repo(); };
}

function fillSettings(brief) {
  $("set-path").value = brief.emulator_path || "";
  $("set-num").value = brief.emulator_num ?? "0";
  $("set-serial").value = brief.serial || "";
  $("set-lat").value = brief.latitude ?? 45;
  $("set-lon").value = brief.longitude ?? 45;
}

function bindSettings() {
  $("btn-browse").addEventListener("click", async () => {
    const path = await window.pywebview.api.browse_folder();
    if (path) { $("set-path").value = path; autoSaveEmu(); }
  });
  // 输入变动 -> 防抖 700ms 自动保存；路径有值则自动检测
  ["set-path", "set-num", "set-serial"].forEach((id) =>
    $(id).addEventListener("input", () => {
      clearTimeout(emuSaveTimer);
      emuSaveTimer = setTimeout(autoSaveEmu, 700);
    }));
  ["set-lat", "set-lon"].forEach((id) =>
    $(id).addEventListener("input", () => {
      clearTimeout(locSaveTimer);
      locSaveTimer = setTimeout(autoSaveLocation, 700);
    }));
  $("btn-test-loc").addEventListener("click", async () => {
    setResult("loc-result", null, "测试中…");
    const res = await window.pywebview.api.test_location($("set-lat").value, $("set-lon").value);
    if (!res.ok) setResult("loc-result", false, res.error);
  });
  $("btn-debug").addEventListener("click", () => startSignup(true));

  $("btn-update").addEventListener("click", startUpdateDownload);
  document.querySelectorAll(".pill-btn[data-src]").forEach((b) =>
    b.addEventListener("click", async () => {
      const res = await window.pywebview.api.set_update_source(b.dataset.src);
      if (res.ok) markUpdateSource(b.dataset.src);
    }));

  $("confirm-cancel").addEventListener("click", () => { $("confirm-mask").hidden = true; });
  $("confirm-ok").addEventListener("click", async () => {
    $("confirm-mask").hidden = true;
    if (state.confirmAction) { await state.confirmAction(); state.confirmAction = null; }
  });
}

let emuSaveTimer = null;
let emuLastSig = null;
async function autoSaveEmu() {
  const path = $("set-path").value.trim();
  const num = $("set-num").value.trim() || "0";
  const serial = $("set-serial").value.trim();
  const sig = JSON.stringify([path, num, serial]);
  if (sig === emuLastSig) return;
  const res = await window.pywebview.api.save_emulator(path, num, serial);
  if (!res.ok) {
    emuLastSig = null;
    setPathCheck("bad");
    setResult("emu-result", false, res.error);
    return;
  }
  emuLastSig = sig;
  onHomeShow();
  if (path) {
    setPathCheck("detecting");
    setResult("emu-result", null, "检测模拟器…");
    const det = await window.pywebview.api.detect_emulator();
    if (!det.ok) { setPathCheck("bad"); setResult("emu-result", false, det.error); }
  } else {
    setPathCheck("none");
    setResult("emu-result", null, "");
  }
}

let locSaveTimer = null;
let locLastSig = null;
async function autoSaveLocation() {
  const lat = $("set-lat").value.trim();
  const lon = $("set-lon").value.trim();
  const sig = JSON.stringify([lat, lon]);
  if (sig === locLastSig) return;
  const res = await window.pywebview.api.save_location(lat, lon);
  if (!res.ok) { locLastSig = null; setResult("loc-result", false, res.error); return; }
  locLastSig = sig;
  setResult("loc-result", true, "已自动保存");
  onHomeShow();
}

function setPathCheck(state) {
  const el = $("path-check");
  if (state === "ok") {
    el.hidden = false; el.className = "bi bi-check-circle-fill ok-check";
  } else if (state === "detecting") {
    el.hidden = false; el.className = "bi bi-hourglass-split ok-check detecting";
  } else if (state === "bad") {
    el.hidden = false; el.className = "bi bi-x-circle-fill ok-check bad";
  } else {
    el.hidden = true;
  }
}

function setResult(id, ok, text) {
  const el = $(id);
  el.textContent = text;
  el.className = "caption result " + (ok === true ? "ok" : ok === false ? "bad" : "");
}

/* ============ 自动更新 ============ */

function markUpdateSource(source) {
  document.querySelectorAll(".pill-btn[data-src]").forEach((b) =>
    b.classList.toggle("active", b.dataset.src === source));
}

function setUpdateState(text, showButton) {
  $("update-state").textContent = text || "";
  $("btn-update").hidden = !showButton;
}

function applyUpdateCheck(res) {
  if (!res.ok) { setUpdateState("检查更新失败"); return; }
  if (res.status === "latest") setUpdateState("已是最新版本", false);
  else setUpdateState(`发现新版本 v${res.tag}`, true);
}

let updating = false;
function startUpdateDownload() {
  if (updating) return;
  updating = true;
  $("btn-update").disabled = true;
  setUpdateState("准备下载…", false);
  $("update-progress").hidden = false;
  $("update-bar").style.width = "0%";
  $("update-percent").textContent = "";
  window.pywebview.api.download_update();
}

function onUpdateEvent(d) {
  switch (d.status) {
    case "progress":
      $("update-bar").style.width = d.percent + "%";
      $("update-percent").textContent = d.percent + "%";
      break;
    case "downloaded":
      updating = false;
      $("update-percent").textContent = "100%";
      setUpdateState("下载完成", false);
      $("btn-update").textContent = "重启并更新";
      $("btn-update").disabled = false;
      $("btn-update").hidden = false;
      $("btn-update").onclick = async () => {
        $("btn-update").disabled = true;
        setUpdateState("正在更新，程序将自动重启…", false);
        await window.pywebview.api.apply_update();
      };
      break;
    case "error":
      updating = false;
      $("btn-update").disabled = false;
      setUpdateState(d.message || "更新失败", true);
      $("update-progress").hidden = true;
      break;
    case "latest":
      updating = false;
      setUpdateState("已是最新版本", false);
      $("update-progress").hidden = true;
      break;
  }
}

/* ============ 事件入口（Python 推送） ============ */

window.__pushEvent = function (ev) {
  const d = ev.data || {};
  switch (ev.type) {
    case "account":
      state.accountStates[d.phone] = d;
      renderStatusList();
      break;
    case "run":
      onRunEvent(d);
      break;
    case "feed":
      (d.items || []).forEach((it) => appendFeed(it.message, it.level));
      break;
    case "detect":
      setResult(d.target === "loc" ? "loc-result" : "emu-result", d.ok, d.message);
      if (d.target === "emu") setPathCheck(d.ok ? "ok" : "bad");
      break;
    case "toast":
      toast(d.message, d.level);
      break;
    case "update":
      onUpdateEvent(d);
      break;
  }
};

function onRunEvent(d) {
  if (d.state === "started") {
    setBusy(true);
    state.accountStates = {};
    hideError();
    setStatus(d.debug ? "warning" : "accent", d.debug ? "调试签到中（不实际打卡）" : "运行中", true);
    renderStatusList();
  } else if (d.state === "finished") {
    setBusy(false);
    setStatus("accent", "就绪", false);
    $("status-chip").className = "status-chip";
    $("status-text").textContent = "就绪";
    if (d.has_failure) showError("本轮结束（部分账号失败）", d.message || "", "");
  } else if (d.state === "aborted") {
    setBusy(false);
    setStatus("danger", "已中止", false);
    showError("签到中止", d.message || "未知原因", d.detail || "");
  } else if (d.state === "stopping") {
    setStatus("warning", "停止中…", true);
  }
}

/* ============ 工具 ============ */

function mask(p) { return p.length >= 8 ? p.slice(0, 3) + "****" + p.slice(-4) : p; }
function pillText(s) {
  return { pending: "待签到", running: "进行中", done: "已完成", failed: "失败" }[s] || s;
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let toastTimer = null;
function toast(message, level) {
  const el = $("toast");
  el.textContent = message;
  el.className = level || "";
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}
