const state = {
  dashboard: null,
  courses: [],
  rule: null,
  rules: [],
  user: null,
  integration: null,
  loginFlow: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "object" ? detail?.message : detail;
    const error = new Error(message || "请求失败，请稍后重试");
    error.code = typeof detail === "object" ? detail?.code : "request_failed";
    throw error;
  }
  return data;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(digits);
}

function switchView(viewName) {
  $$("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("is-visible", panel.dataset.viewPanel === viewName);
  });
  $$("[data-view]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderUser() {
  if (!state.user) return;
  $("#sidebar-user-name").textContent = state.user.name;
  $("#sidebar-user-id").textContent = state.user.studentId;
  $("#term-context").textContent = `${state.user.school} · ${state.user.cohort} 级`;
  const sync = state.user.sync;
  $("#last-sync").textContent = sync?.last_sync_at || "尚未同步";
}

function renderIntegration() {
  const connected = Boolean(state.integration?.authenticated);
  $("#connection-card").classList.toggle("is-connected", connected);
  $("#connection-title").textContent = connected ? "学校数据已连接" : "脱敏演示模式";
  $("#connection-caption").textContent = connected
    ? state.integration.user?.studentId || "会话有效"
    : "学校账户未连接";
  $("#mobile-mode-pill").textContent = connected ? "学校数据" : "演示模式";
  $("#integration-button").textContent = connected ? "管理学校同步" : "连接学校账户";
  const tag = $("#source-tag");
  tag.textContent = connected ? "学校同步" : "演示数据";
  tag.classList.toggle("demo", !connected);
  tag.classList.toggle("school", connected);
}

function renderDashboard() {
  const dashboard = state.dashboard;
  if (!dashboard) return;
  const metrics = dashboard.metrics;
  $("#gpa-value").textContent = formatNumber(metrics.gpa, 3);
  $("#included-credits").textContent = `${formatNumber(metrics.includedCredits, 1)} 学分`;
  $("#weighted-average").textContent = formatNumber(metrics.weightedAverage, 2);
  $("#arithmetic-average").textContent = formatNumber(metrics.arithmeticAverage, 2);
  const futureRange = dashboard.futureRange;
  $("#future-range").textContent = futureRange.remainingCredits
    ? `${formatNumber(futureRange.min, 2)}–${formatNumber(futureRange.max, 2)}`
    : formatNumber(metrics.gpa, 2);
  $("#future-range").title = futureRange.assumption;
  $("#completed-course-count").textContent = `${metrics.completedCourses} 门`;
  $("#gpa-caption").textContent = metrics.projected
    ? "当前为情景结果，不会写回真实成绩"
    : "仅统计规则内、已有成绩且已确认的课程";

  const selection = dashboard.directionSelection;
  const notice = $("#selection-notice");
  notice.hidden = !selection.required;
  $("#selection-message").textContent = selection.message;

  $("#rule-route").innerHTML = dashboard.groups
    .map(
      (group) => `
        <article class="route-step ${group.complete ? "is-complete" : ""}">
          <span class="route-code">${escapeHtml(group.code)}</span>
          <h3>${escapeHtml(group.name)}</h3>
          <p>${escapeHtml(group.current)}</p>
        </article>`,
    )
    .join("");

  state.courses = dashboard.courses;
  renderScenario();
  renderCourses();
}

function recommendedScore(course) {
  if (course.group === "D") return 88;
  if (course.group === "E") return 90;
  return 86;
}

function renderScenario() {
  const pending = (state.dashboard?.pending || [])
    .filter((course) => course.ruleMode === "gpa")
    .slice(0, 5);
  const list = $("#scenario-list");
  if (!pending.length) {
    list.innerHTML = '<p class="page-intro">规则内课程均已有成绩，暂时没有待测课程。</p>';
    $("#calculate-scenario").disabled = true;
    return;
  }
  $("#calculate-scenario").disabled = false;
  list.innerHTML = pending
    .map((course) => {
      const score = recommendedScore(course);
      return `
        <div class="scenario-item" data-code="${escapeHtml(course.code)}">
          <label for="range-${escapeHtml(course.code)}">
            ${escapeHtml(course.name)}
            <small>${escapeHtml(course.code)} · ${course.credits} 学分</small>
          </label>
          <input id="range-${escapeHtml(course.code)}" type="range" min="0" max="100" value="${score}" />
          <span class="scenario-score">
            <input aria-label="${escapeHtml(course.name)}预估分数" type="number" min="0" max="100" value="${score}" />分
          </span>
        </div>`;
    })
    .join("");
  $$(".scenario-item", list).forEach((item) => {
    const range = $('input[type="range"]', item);
    const number = $('input[type="number"]', item);
    range.addEventListener("input", () => (number.value = range.value));
    number.addEventListener("input", () => {
      const value = Math.max(0, Math.min(100, Number(number.value || 0)));
      range.value = String(value);
    });
  });
}

function courseStatus(course) {
  if (course.status === "planned") return '<span class="status-chip pending">待修 / 待出分</span>';
  if (course.scoreIssue) {
    return `<span class="status-chip issue" title="${escapeHtml(course.scoreIssue)}">成绩制待确认</span>`;
  }
  if (course.ruleMode === "outside") return '<span class="status-chip outside">当前规则外</span>';
  if (course.ruleMode === "pass_only") return '<span class="status-chip pass-only">只需通过</span>';
  if (course.ruleMode === "direction" && !course.selectedForRule) {
    return '<span class="status-chip candidate">方向课候选</span>';
  }
  if (course.ruleMode === "direction" && course.selectedForRule) {
    return '<span class="status-chip">已选入 6 学分</span>';
  }
  return '<span class="status-chip">计入绩点</span>';
}

function filteredCourses() {
  const query = $("#course-search").value.trim().toLowerCase();
  const group = $("#group-filter").value;
  const status = $("#status-filter").value;
  return state.courses.filter((course) => {
    const matchesQuery =
      !query || course.name.toLowerCase().includes(query) || course.code.toLowerCase().includes(query);
    const matchesGroup = group === "all" || course.group === group;
    let matchesStatus = status === "all" || course.status === status;
    if (status === "selected") matchesStatus = course.selectedForRule;
    if (status === "outside") matchesStatus = course.ruleMode === "outside";
    return matchesQuery && matchesGroup && matchesStatus;
  });
}

function renderCourses() {
  const rows = filteredCourses();
  $("#filter-count").textContent = `${rows.length} / ${state.courses.length} 门`;
  $("#course-empty").hidden = rows.length > 0;
  $("#course-table-body").innerHTML = rows
    .map(
      (course) => `
        <tr>
          <td><span class="group-chip">${escapeHtml(course.group)}</span></td>
          <td class="course-name-cell">
            <strong>${escapeHtml(course.name)}</strong>
            <small>${escapeHtml(course.code)} · ${escapeHtml(course.source)}</small>
          </td>
          <td class="term-code">${escapeHtml(course.termCode)}</td>
          <td class="credit-number">${course.credits}</td>
          <td class="score-number">${escapeHtml(course.score ?? "—")}</td>
          <td class="grade-point">${course.gradePoint === null ? "—" : formatNumber(course.gradePoint, 3)}</td>
          <td>${courseStatus(course)}</td>
          <td><button class="edit-button" data-course-id="${course.id}" type="button">调整</button></td>
        </tr>`,
    )
    .join("");
  $$(".edit-button", $("#course-table-body")).forEach((button) => {
    button.addEventListener("click", () => openCourseDialog(Number(button.dataset.courseId)));
  });
}

function renderRule() {
  if (!state.rule) return;
  $("#rule-name").textContent = state.rule.name;
  $("#rule-version").textContent = `版本 ${state.rule.version}`;
  $("#rule-group-table").innerHTML = state.rule.groups
    .map(
      (group) => `
        <div class="rule-row">
          <span class="code">${escapeHtml(group.code)}</span>
          <strong>${escapeHtml(group.name)}</strong>
          <span>${escapeHtml(group.requirement)}</span>
        </div>`,
    )
    .join("");
  const selector = $("#rule-selector");
  selector.innerHTML = state.rules
    .map(
      (rule) => `<option value="${escapeHtml(rule.id)}">${escapeHtml(rule.label || rule.name)}</option>`,
    )
    .join("");
  selector.value = state.rule.id;
  $("#rule-count").textContent = `${state.rules.length} 套可用规则`;
}

async function switchRule() {
  const ruleId = $("#rule-selector").value;
  if (!ruleId || ruleId === state.rule?.id) return;
  $("#rule-selector").disabled = true;
  try {
    const result = await api("/api/v1/preferences/rule", {
      method: "PUT",
      body: JSON.stringify({ rule_id: ruleId }),
    });
    state.rule = result.rule;
    state.dashboard = result.dashboard;
    renderRule();
    renderDashboard();
    showToast("计分规则已切换");
  } catch (error) {
    showToast(error.message);
    $("#rule-selector").value = state.rule?.id || "";
  } finally {
    $("#rule-selector").disabled = false;
  }
}

function openCourseDialog(courseId) {
  const course = state.courses.find((item) => item.id === courseId);
  if (!course) return;
  $("#dialog-course-id").value = course.id;
  $("#dialog-course-code").textContent = `${course.group} · ${course.code}`;
  $("#dialog-course-name").textContent = course.name;
  $("#dialog-score-scale").value = course.scoreScale;
  $("#dialog-score").value = course.score ?? "";
  $("#dialog-selected").checked = course.selectedForRule;
  $("#direction-checkbox").hidden = course.ruleMode !== "direction";
  $("#dialog-error").textContent = "";
  updateScoreHint();
  $("#course-dialog").showModal();
}

function updateScoreHint() {
  const scale = $("#dialog-score-scale").value;
  const hints = {
    percentage: "百分制请输入 0–100。",
    five_level: "可输入：优秀、良好、中等、及格、不及格。",
    pass_fail: "可输入：通过或不通过；该成绩不累计绩点。",
  };
  $("#score-hint").textContent = hints[scale];
}

async function saveCourse() {
  const button = $("#save-course");
  const courseId = Number($("#dialog-course-id").value);
  button.disabled = true;
  $("#dialog-error").textContent = "";
  try {
    const response = await api(`/api/v1/courses/${courseId}`, {
      method: "PATCH",
      body: JSON.stringify({
        score: $("#dialog-score").value || null,
        score_scale: $("#dialog-score-scale").value,
        selected_for_rule: $("#dialog-selected").checked,
      }),
    });
    state.dashboard = response.dashboard;
    renderDashboard();
    $("#course-dialog").close();
    showToast("课程已更新，所有指标已重新计算");
  } catch (error) {
    $("#dialog-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function calculateScenario() {
  const scores = {};
  $$(".scenario-item").forEach((item) => {
    scores[item.dataset.code] = Number($('input[type="number"]', item).value);
  });
  try {
    const result = await api("/api/v1/scenarios/calculate", {
      method: "POST",
      body: JSON.stringify({ scores }),
    });
    $("#scenario-result").textContent = `情景 GPA ${formatNumber(result.metrics.gpa, 3)}`;
    showToast("情景测算完成；真实课程数据没有改动");
  } catch (error) {
    showToast(error.message);
  }
}

function renderTermSelection() {
  const terms = state.integration?.defaultTerms || [];
  $("#term-grid").innerHTML = terms
    .map(
      (term) => `
        <label class="term-check">
          <input type="checkbox" value="${escapeHtml(term)}" checked />
          <span>${escapeHtml(term)}</span>
        </label>`,
    )
    .join("");
}

function showConnectionPanel() {
  const connected = Boolean(state.integration?.authenticated);
  $("#school-login-panel").hidden = connected;
  $("#school-connected-panel").hidden = !connected;
  if (connected) {
    $("#connected-user").textContent = state.integration.user?.name || "北航同学";
    $("#connected-student-id").textContent = state.integration.user?.studentId || "—";
    renderTermSelection();
  }
}

async function refreshLoginContext() {
  const button = $("#submit-school-login");
  button.disabled = true;
  button.textContent = "正在连接统一认证…";
  $("#school-login-error").textContent = "";
  try {
    state.loginFlow = await api("/api/v1/integration/buaa/prelogin", { method: "POST" });
    const needsCaptcha = state.loginFlow.captchaRequired;
    $("#captcha-field").hidden = !needsCaptcha;
    $("#school-captcha").required = needsCaptcha;
    $("#captcha-image").src = state.loginFlow.captchaImage || "";
    $("#school-captcha").value = "";
  } catch (error) {
    state.loginFlow = null;
    $("#school-login-error").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "登录并同步成绩";
  }
}

async function openIntegrationDialog() {
  const dialog = $("#integration-dialog");
  $("#school-login-error").textContent = "";
  $("#school-sync-error").textContent = "";
  if (!dialog.open) dialog.showModal();
  try {
    state.integration = await api("/api/v1/integration/status");
    renderIntegration();
    showConnectionPanel();
    if (!state.integration.authenticated) await refreshLoginContext();
  } catch (error) {
    $("#school-login-error").textContent = error.message;
  }
}

async function loginSchool(event) {
  event.preventDefault();
  if (!state.loginFlow) {
    await refreshLoginContext();
    if (!state.loginFlow) return;
  }
  const button = $("#submit-school-login");
  button.disabled = true;
  button.textContent = "正在验证身份…";
  $("#school-login-error").textContent = "";
  try {
    await api("/api/v1/integration/buaa/login", {
      method: "POST",
      body: JSON.stringify({
        flow_id: state.loginFlow.flowId,
        username: $("#school-username").value.trim(),
        password: $("#school-password").value,
        captcha: $("#school-captcha").value.trim() || null,
      }),
    });
    $("#school-password").value = "";
    state.loginFlow = null;
    state.integration = await api("/api/v1/integration/status");
    renderIntegration();
    showConnectionPanel();
    await syncSchool(true);
  } catch (error) {
    $("#school-password").value = "";
    $("#school-login-error").textContent = error.message;
    await refreshLoginContext();
  } finally {
    button.disabled = false;
    button.textContent = "登录并同步成绩";
  }
}

async function reloadCoreData() {
  [state.user, state.dashboard] = await Promise.all([
    api("/api/v1/me"),
    api("/api/v1/dashboard"),
  ]);
  renderUser();
  renderDashboard();
}

async function syncSchool(closeWhenDone = false) {
  const button = $("#school-sync");
  const terms = $$('#term-grid input[type="checkbox"]:checked').map((item) => item.value);
  if (!terms.length) {
    $("#school-sync-error").textContent = "请至少选择一个学期";
    return;
  }
  button.disabled = true;
  button.textContent = `正在同步 ${terms.length} 个学期…`;
  $("#school-sync-error").textContent = "";
  try {
    const result = await api("/api/v1/integration/buaa/sync", {
      method: "POST",
      body: JSON.stringify({ terms }),
    });
    state.dashboard = result.dashboard;
    await reloadCoreData();
    state.integration = await api("/api/v1/integration/status");
    renderIntegration();
    showToast(`同步完成：读取 ${result.summary.synced} 条成绩`);
    if (closeWhenDone) $("#integration-dialog").close();
  } catch (error) {
    $("#school-sync-error").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "立即同步";
  }
}

async function logoutSchool() {
  const button = $("#school-logout");
  button.disabled = true;
  try {
    await api("/api/v1/integration/buaa/logout", { method: "POST" });
    state.integration = await api("/api/v1/integration/status");
    await reloadCoreData();
    renderIntegration();
    $("#integration-dialog").close();
    showToast("已退出学校账户，恢复脱敏演示数据");
  } catch (error) {
    $("#school-sync-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function bindEvents() {
  $$("[data-view]").forEach((button) =>
    button.addEventListener("click", () => switchView(button.dataset.view)),
  );
  $$("[data-go-view]").forEach((button) =>
    button.addEventListener("click", () => switchView(button.dataset.goView)),
  );
  ["#course-search", "#group-filter", "#status-filter"].forEach((selector) => {
    $(selector).addEventListener("input", renderCourses);
  });
  $("#dialog-score-scale").addEventListener("change", updateScoreHint);
  $("#save-course").addEventListener("click", saveCourse);
  $("#calculate-scenario").addEventListener("click", calculateScenario);
  $("#reset-scenario").addEventListener("click", () => {
    renderScenario();
    $("#scenario-result").textContent = "尚未测算";
  });
  $("#integration-button").addEventListener("click", openIntegrationDialog);
  $("#close-integration").addEventListener("click", () => $("#integration-dialog").close());
  $("#cancel-school-login").addEventListener("click", () => $("#integration-dialog").close());
  $("#refresh-captcha").addEventListener("click", refreshLoginContext);
  $("#school-login-form").addEventListener("submit", loginSchool);
  $("#school-sync").addEventListener("click", () => syncSchool(false));
  $("#school-logout").addEventListener("click", logoutSchool);
  $("#rule-selector").addEventListener("change", switchRule);
}

async function bootstrap() {
  bindEvents();
  try {
    const [user, dashboard, rules, integration] = await Promise.all([
      api("/api/v1/me"),
      api("/api/v1/dashboard"),
      api("/api/v1/rules"),
      api("/api/v1/integration/status"),
    ]);
    state.user = user;
    state.dashboard = dashboard;
    state.rules = rules.items;
    state.integration = integration;
    state.rule = await api(`/api/v1/rules/${encodeURIComponent(rules.selectedRuleId)}`);
    renderUser();
    renderDashboard();
    renderRule();
    renderIntegration();
  } catch (error) {
    showToast(`初始化失败：${error.message}`);
  }
}

bootstrap();
