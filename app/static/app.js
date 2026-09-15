const state = {
  dashboard: null,
  courses: [],
  rule: null,
  rules: [],
  user: null,
  integration: null,
  analytics: null,
  comprehensive: null,
  competitionCalendar: null,
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
  const schoolConnected = Boolean(state.integration?.schoolAuthenticated);
  const localConnected = Boolean(state.integration?.localAuthenticated);
  $("#connection-card").classList.toggle("is-connected", localConnected);
  $("#connection-title").textContent = schoolConnected
    ? "学校数据已连接"
    : localConnected
      ? "个人数据已恢复"
      : "脱敏演示模式";
  $("#connection-caption").textContent = localConnected
    ? state.integration.user?.studentId || "本地会话有效"
    : "学校账户未连接";
  $("#mobile-mode-pill").textContent = localConnected ? "个人数据" : "演示模式";
  $("#integration-button").textContent = schoolConnected
    ? "管理学校同步"
    : localConnected
      ? "刷新学校数据"
      : "连接学校账户";
  const tag = $("#source-tag");
  tag.textContent = localConnected ? "本地已保存" : "演示数据";
  tag.classList.toggle("demo", !localConnected);
  tag.classList.toggle("school", localConnected);
  $("#account-logout").hidden = !localConnected;
  $("#export-actions").hidden = !localConnected;
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

function targetStatusText(target) {
  const messages = {
    already_met: "按当前已修成绩，目标已经满足",
    reachable: `覆盖 ${formatNumber(target.pendingCredits, 1)} 个剩余学分`,
    unreachable: "即使剩余课程均为 4.0 也无法达到",
    no_pending_courses: "当前规则中没有可用于反推的待修课程",
  };
  return messages[target?.status] || "暂无可计算数据";
}

function renderAnalytics() {
  const analytics = state.analytics;
  if (!analytics) return;
  $("#analysis-current-gpa").textContent = formatNumber(analytics.overall?.rule?.gpa, 3);
  $("#analysis-included-credits").textContent = formatNumber(analytics.summary?.includedCredits, 1);
  $("#analysis-weighted-points").textContent = formatNumber(analytics.summary?.weightedGradePoints, 2);
  $("#analysis-volatility").textContent = formatNumber(analytics.summary?.gradePointVolatility, 3);
  $("#regret-basis").textContent = analytics.calculationBasis || "按学分加权反事实计算";
  const target = analytics.target;
  $("#target-required-score").textContent =
    target?.status === "reachable" && target.requiredAverageScore !== null
      ? `约 ${formatNumber(target.requiredAverageScore, 1)} 分`
      : target?.status === "already_met"
        ? "已满足"
        : "—";
  $("#target-status").textContent = targetStatusText(target);

  const timeline = analytics.timeline || [];
  $("#term-timeline").innerHTML = timeline.length
    ? timeline
        .map((row) => {
          const allGpa = row.all?.gpa;
          const ruleGpa = row.rule?.gpa;
          return `
            <div class="term-row">
              <div class="term-row-head">
                <strong>${escapeHtml(row.term)}</strong>
                <span>${formatNumber(allGpa, 3)} / <b>${formatNumber(ruleGpa, 3)}</b></span>
              </div>
              <div class="term-bars" aria-label="全部课程 ${formatNumber(allGpa, 3)}，规则课程 ${formatNumber(ruleGpa, 3)}">
                <i style="width:${Math.max(0, Math.min(100, Number(allGpa || 0) * 25))}%"></i>
                <i style="width:${Math.max(0, Math.min(100, Number(ruleGpa || 0) * 25))}%"></i>
              </div>
              <small>${row.all.courseCount} 门 · ${formatNumber(row.all.credits, 1)} 学分 · 累计规则 GPA ${formatNumber(row.cumulativeRule?.gpa, 3)}</small>
            </div>`;
        })
        .join("")
    : '<p class="empty-copy">同步成绩后显示学期变化。</p>';

  const opportunities = analytics.opportunities || [];
  const impacts = opportunities.map((item) => ({
        name: item.name,
        meta: `${formatNumber(item.credits, 1)} 学分 · 待修`,
        value: `最多影响 ${formatNumber(item.gpaSwing60To100, 3)}`,
      }));
  $("#impact-list").innerHTML = impacts.length
    ? impacts
        .map(
          (item, index) => `
            <div class="impact-item">
              <span class="impact-rank">${String(index + 1).padStart(2, "0")}</span>
              <div><strong>${escapeHtml(item.name)}</strong><small>${item.meta}</small></div>
              <b>${escapeHtml(item.value)}</b>
            </div>`,
        )
        .join("")
    : '<p class="empty-copy">暂无规则内课程可分析。</p>';

  const regrets = analytics.regretCourses || [];
  $("#regret-list").innerHTML = regrets.length
    ? regrets
        .map(
          (item, index) => `
            <article class="regret-item ${index === 0 ? "is-primary" : ""}">
              <span class="regret-dose">${index + 1}</span>
              <div class="regret-course">
                <strong>${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(item.term)} · ${formatNumber(item.credits, 1)} 学分 · ${escapeHtml(item.score)} 分 / 绩点 ${formatNumber(item.gradePoint, 3)}</small>
              </div>
              <div class="regret-shift"><span>${formatNumber(item.currentGpa, 3)} → ${formatNumber(item.gpaWithoutCourse, 3)}</span><strong>+${formatNumber(item.gpaLiftIfExcluded, 4)}</strong></div>
            </article>`,
        )
        .join("")
    : '<p class="empty-copy">当前没有拉低加权 GPA 的规则内课程。</p>';

  const groups = analytics.groupPerformance || [];
  $("#group-performance").innerHTML = groups.length
    ? groups
        .map(
          (group) => `
            <div class="group-performance-row">
              <span>${escapeHtml(group.group)}</span>
              <div><i style="width:${Math.max(0, Math.min(100, Number(group.gpa || 0) * 25))}%"></i></div>
              <strong>${formatNumber(group.gpa, 3)}</strong>
              <small>${formatNumber(group.credits, 1)} 学分</small>
            </div>`,
        )
        .join("")
    : '<p class="empty-copy">暂无规则组数据。</p>';

  const distribution = analytics.gradePointDistribution || [];
  $("#grade-distribution").innerHTML = distribution
    .map(
      (band) => `
        <div class="distribution-row">
          <span>${escapeHtml(band.label)}</span>
          <div><i style="width:${Math.max(0, Math.min(100, Number(band.creditShare || 0) * 100))}%"></i></div>
          <strong>${formatNumber(Number(band.creditShare || 0) * 100, 1)}%</strong>
          <small>${band.courseCount} 门</small>
        </div>`,
    )
    .join("");
}

function calendarStatusMatches(item, filter) {
  if (filter === "all") return true;
  if (filter === "verified") return ["official", "window"].includes(item.status);
  if (filter === "estimated") return ["estimated", "pending"].includes(item.status);
  return item.status === filter;
}

function calendarDateParts(item, selectedYear) {
  if (!item.startDate) return { month: "本年", day: "休", group: "未安排" };
  const [startYear, startMonth, startDay] = item.startDate.split("-");
  if (Number(startYear) < selectedYear) {
    return { month: startMonth, day: startDay, group: "跨年启动" };
  }
  const endParts = item.endDate?.split("-") || [];
  const day = item.endDate && item.endDate !== item.startDate
    ? startMonth === endParts[1]
      ? `${startDay}—${endParts[2]}`
      : `${startDay}→${endParts[1]}.${endParts[2]}`
    : startDay;
  return { month: startMonth, day, group: `${startMonth} 月` };
}

function renderCompetitionCalendar() {
  const payload = state.competitionCalendar;
  if (!payload) return;
  const selectedYear = Number($("#calendar-year").value || 2027);
  const category = $("#calendar-category").value;
  const status = $("#calendar-status").value;
  const query = $("#calendar-search").value.trim().toLowerCase();
  const direction = $("#calendar-sort").value === "desc" ? -1 : 1;

  $("#calendar-updated").textContent = `资料更新于 ${payload.updatedAt}`;
  $("#calendar-policy-count").textContent = payload.summary.policyEntries;
  $("#calendar-unique-count").textContent = payload.summary.uniqueCompetitions;
  $("#calendar-official-count").textContent = payload.summary.official2026;
  $("#calendar-2027-official-count").textContent = payload.summary.official2027;
  $("#calendar-notice").textContent = payload.notice;

  const items = payload.items
    .filter((item) => item.year === selectedYear)
    .filter((item) => category === "all" || item.categoryId === category)
    .filter((item) => calendarStatusMatches(item, status))
    .filter((item) => !query || item.searchText.toLowerCase().includes(query))
    .sort((left, right) => {
      if (!left.startDate && !right.startDate) return 0;
      if (!left.startDate) return 1;
      if (!right.startDate) return -1;
      return direction * left.sortDate.localeCompare(right.sortDate);
    });

  $("#calendar-filter-count").textContent = `${items.length} 项`;
  if (!items.length) {
    $("#competition-calendar").innerHTML = '<div class="calendar-empty">没有符合当前筛选条件的竞赛。</div>';
    return;
  }

  const groups = [];
  items.forEach((item) => {
    const parts = calendarDateParts(item, selectedYear);
    let group = groups.at(-1);
    if (!group || group.name !== parts.group) {
      group = { name: parts.group, items: [] };
      groups.push(group);
    }
    group.items.push({ item, parts });
  });

  $("#competition-calendar").innerHTML = groups
    .map(
      (group) => `
        <section class="calendar-month-group">
          <header><h2>${escapeHtml(group.name)}</h2><span>${group.items.length} 项</span></header>
          <div class="calendar-rows">
            ${group.items
              .map(({ item, parts }) => {
                const basis = item.basis || item.note;
                return `
                  <article class="competition-row">
                    <time class="calendar-date-ticket" datetime="${escapeHtml(item.startDate || "")}">
                      <span>${escapeHtml(parts.month)}月</span><strong>${escapeHtml(parts.day)}</strong>
                    </time>
                    <div class="competition-main">
                      <div class="competition-tags">
                        <span>${escapeHtml(item.categoryName)}</span>
                        ${item.policyLabels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}
                      </div>
                      <h3>${escapeHtml(item.name)}</h3>
                      <p>${escapeHtml(item.displayDate)}</p>
                      ${basis ? `<small>${escapeHtml(basis)}</small>` : ""}
                    </div>
                    <div class="competition-source">
                      <span class="calendar-status is-${escapeHtml(item.status)}">${escapeHtml(item.statusName)}</span>
                      <small>${escapeHtml(item.stage)}</small>
                      <a href="${escapeHtml(item.source.url)}" target="_blank" rel="noopener noreferrer">查看来源</a>
                    </div>
                  </article>`;
              })
              .join("")}
          </div>
        </section>`,
    )
    .join("");
}

function renderCalendarFilters() {
  const payload = state.competitionCalendar;
  if (!payload) return;
  $("#calendar-category").innerHTML = [
    '<option value="all">全部类别</option>',
    ...payload.categories.map(
      (category) => `<option value="${escapeHtml(category.id)}">${escapeHtml(category.name)} (${category.count})</option>`,
    ),
  ].join("");
  renderCompetitionCalendar();
}

function renderComprehensiveItemTypes() {
  const categories = state.comprehensive?.rule?.categories || [];
  const category = categories.find((item) => item.id === $("#comprehensive-category").value);
  const selector = $("#comprehensive-item-type");
  const selectedKind = selector.value;
  const itemTypes = category?.itemTypes || [];
  selector.innerHTML = itemTypes
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`)
    .join("");
  if (itemTypes.some((item) => item.id === selectedKind)) selector.value = selectedKind;
  renderComprehensiveAutoFields();
  scheduleComprehensivePreview();
}

function currentComprehensiveDefinition() {
  return (state.comprehensive?.rule?.items || []).find(
    (item) => item.id === $("#comprehensive-item-type").value,
  );
}

function comprehensiveFieldVisible(field, values) {
  const condition = field.visibleWhen;
  if (!condition) return true;
  const current = String(values[condition.field] ?? "");
  if (condition.equals !== undefined) return current === condition.equals;
  if (condition.notEquals !== undefined) return current !== condition.notEquals;
  if (condition.notIn) return !condition.notIn.includes(current);
  return true;
}

function comprehensiveFieldOptions(field, values) {
  if (!field.optionsBy) return field.options || [];
  return field.optionsBy.values?.[String(values[field.optionsBy.field] ?? "")] || field.optionsBy.default || [];
}

function collectComprehensiveValues() {
  return Object.fromEntries(
    $$('[data-comprehensive-field]', $("#comprehensive-auto-fields")).map((input) => [
      input.dataset.comprehensiveField,
      input.type === "number" && input.value !== "" ? Number(input.value) : input.value,
    ]),
  );
}

function renderComprehensiveAutoFields(preserved = null) {
  const definition = currentComprehensiveDefinition();
  const container = $("#comprehensive-auto-fields");
  if (!definition) {
    container.innerHTML = "";
    return;
  }
  const incoming = preserved || collectComprehensiveValues();
  const values = { ...incoming };
  const html = [];
  definition.fields.forEach((field) => {
    if (!comprehensiveFieldVisible(field, values)) return;
    if (field.type === "select") {
      const options = comprehensiveFieldOptions(field, values);
      if (!options.some((item) => item.value === String(values[field.key] ?? ""))) {
        values[field.key] = options[0]?.value || "";
      }
      html.push(`
        <label class="field auto-field">
          <span>${escapeHtml(field.label)}</span>
          <select data-comprehensive-field="${escapeHtml(field.key)}">
            ${options.map((item) => `<option value="${escapeHtml(item.value)}" ${item.value === String(values[field.key]) ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}
          </select>
        </label>`);
      return;
    }
    if (values[field.key] === undefined || values[field.key] === null) {
      values[field.key] = field.default ?? "";
    }
    const attributes = field.type === "number"
      ? `type="number" min="${field.min ?? 0}" max="${field.max ?? 10000}" step="${field.step ?? 0.0001}"`
      : `type="text" maxlength="160"`;
    html.push(`
      <label class="field auto-field ${field.type === "text" ? "wide-field" : ""}">
        <span>${escapeHtml(field.label)}</span>
        <input ${attributes} data-comprehensive-field="${escapeHtml(field.key)}" value="${escapeHtml(values[field.key])}" placeholder="${escapeHtml(field.placeholder || "")}" ${field.required ? "required" : ""} />
        ${field.suffix ? `<small>${escapeHtml(field.suffix)}</small>` : ""}
      </label>`);
  });
  container.innerHTML = html.join("");
}

function scheduleComprehensivePreview() {
  window.clearTimeout(scheduleComprehensivePreview.timer);
  scheduleComprehensivePreview.timer = window.setTimeout(previewComprehensiveItem, 180);
}

async function previewComprehensiveItem() {
  const definition = currentComprehensiveDefinition();
  if (!definition) return;
  const preview = $("#auto-score-preview");
  try {
    const result = await api("/api/v1/comprehensive/preview", {
      method: "POST",
      body: JSON.stringify({
        kind: definition.id,
        values: collectComprehensiveValues(),
        note: $("#comprehensive-note").value.trim(),
      }),
    });
    preview.classList.remove("is-pending");
    $("strong", preview).textContent = `${formatNumber(result.baseScore, 4)} × ${formatNumber(result.factor, 3)} = ${formatNumber(result.rawScore, 4)}`;
  } catch (error) {
    preview.classList.add("is-pending");
    $("strong", preview).textContent = error.message;
  }
}

function renderComprehensive() {
  const payload = state.comprehensive;
  if (!payload) return;
  const { rule, profile, calculation, editable } = payload;
  const categorySelect = $("#comprehensive-category");
  const selectedCategory = categorySelect.value;
  categorySelect.innerHTML = rule.categories
    .map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`)
    .join("");
  if (rule.categories.some((category) => category.id === selectedCategory)) {
    categorySelect.value = selectedCategory;
  }
  renderComprehensiveItemTypes();

  $("#use-current-gpa").checked = profile.useCurrentGpa;
  $("#manual-gpa-field").hidden = profile.useCurrentGpa;
  $("#manual-base-gpa").value = profile.manualBaseGpa ?? "";
  $("#current-gpa-source").textContent = `当前为 ${formatNumber(profile.currentRuleGpa, 3)}`;
  $("#comprehensive-base-gpa").textContent = formatNumber(calculation.baseGpa, 4);
  $("#comprehensive-addition").textContent = `+ ${formatNumber(calculation.weightedAddition, 5)}`;
  $("#comprehensive-final").textContent = formatNumber(calculation.finalScore, 5);
  $("#comprehensive-notice").textContent = rule.notice;

  $("#comprehensive-category-strip").innerHTML = calculation.categories
    .map(
      (category) => `
        <div class="category-cell ${category.limited ? "is-limited" : ""}">
          <span>${escapeHtml(category.shortName)}</span>
          <strong>${formatNumber(category.cappedScore, 4)}</strong>
          <small>× ${formatNumber(category.weight, 1)} · 上限 ${formatNumber(category.cap, 4)}</small>
        </div>`,
    )
    .join("");
  $("#comprehensive-ledger-rows").innerHTML = calculation.categories
    .map(
      (category) => `
        <div class="ledger-row">
          <span>${escapeHtml(category.shortName)}<small>${formatNumber(category.cappedScore, 4)} × ${formatNumber(category.weight, 1)}</small></span>
          <strong>+ ${formatNumber(category.weightedScore, 5)}</strong>
        </div>`,
    )
    .join("");

  const categoryNames = Object.fromEntries(rule.categories.map((item) => [item.id, item.shortName]));
  $("#comprehensive-item-count").textContent = `${calculation.items.length} 项`;
  $("#comprehensive-items").innerHTML = calculation.items.length
    ? calculation.items
        .map(
          (item) => `
            <div class="comprehensive-item ${item.included ? "" : "is-excluded"}">
              <span class="item-category">${escapeHtml(categoryNames[item.categoryId] || "未知")}</span>
              <div>
                <strong>${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(item.itemType)}${item.detail ? ` · ${escapeHtml(item.detail)}` : ""}${item.note ? ` · ${escapeHtml(item.note)}` : ""}</small>
                ${item.reason ? `<em>${escapeHtml(item.reason)}</em>` : ""}
                ${(item.warnings || []).map((warning) => `<em>${escapeHtml(warning)}</em>`).join("")}
              </div>
              <span class="item-score">${formatNumber(item.baseScore, 4)} × ${formatNumber(item.factor, 3)}<b>${formatNumber(item.finalScore, 4)}</b></span>
              ${editable ? `<button class="item-delete" type="button" data-comprehensive-id="${item.id}" aria-label="删除 ${escapeHtml(item.name)}">×</button>` : ""}
            </div>`,
        )
        .join("")
    : `<p class="empty-copy">${editable ? "还没有加分项。" : "登录后可保存自己的综测项目。"}</p>`;
  $$('[data-comprehensive-id]').forEach((button) => {
    button.addEventListener("click", () => deleteComprehensiveItem(Number(button.dataset.comprehensiveId)));
  });
  $$("input, select, button", $("#comprehensive-item-form")).forEach((element) => {
    element.disabled = !editable;
  });
  $("#use-current-gpa").disabled = !editable;
  $("#manual-base-gpa").disabled = !editable;
  $("#save-comprehensive-settings").disabled = !editable;
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
    await reloadExtendedData();
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
    await reloadExtendedData();
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
  const schoolConnected = Boolean(state.integration?.schoolAuthenticated);
  const localConnected = Boolean(state.integration?.localAuthenticated);
  $("#school-login-panel").hidden = schoolConnected;
  $("#school-connected-panel").hidden = !schoolConnected;
  $("#saved-account-note").hidden = !localConnected || schoolConnected;
  if (schoolConnected) {
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
    button.textContent = "验证并进入";
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
    if (!state.integration.schoolAuthenticated) await refreshLoginContext();
  } catch (error) {
    $("#school-login-error").textContent = error.message;
  }
}

async function loginSchool(event) {
  event.preventDefault();
  const refreshAfterLogin = Boolean(state.integration?.localAuthenticated);
  if (!state.loginFlow) {
    await refreshLoginContext();
    if (!state.loginFlow) return;
  }
  const button = $("#submit-school-login");
  button.disabled = true;
  button.textContent = "正在验证身份…";
  $("#school-login-error").textContent = "";
  try {
    const result = await api("/api/v1/integration/buaa/login", {
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
    await reloadCoreData();
    renderIntegration();
    showConnectionPanel();
    if (refreshAfterLogin) {
      await syncSchool(true);
    } else if (result.hasSavedGrades) {
      $("#integration-dialog").close();
      showToast("已载入本地保存的数据；需要时可手动刷新学校成绩");
    } else {
      await syncSchool(true);
    }
  } catch (error) {
    $("#school-password").value = "";
    $("#school-login-error").textContent = error.message;
    await refreshLoginContext();
  } finally {
    button.disabled = false;
    button.textContent = "验证并进入";
  }
}

async function reloadCoreData() {
  [state.user, state.dashboard, state.analytics, state.comprehensive] = await Promise.all([
    api("/api/v1/me"),
    api("/api/v1/dashboard"),
    api(`/api/v1/analytics?target_gpa=${encodeURIComponent($("#target-gpa").value || 3.85)}`),
    api("/api/v1/comprehensive"),
  ]);
  renderUser();
  renderDashboard();
  renderAnalytics();
  renderComprehensive();
}

async function reloadExtendedData() {
  [state.analytics, state.comprehensive] = await Promise.all([
    api(`/api/v1/analytics?target_gpa=${encodeURIComponent($("#target-gpa").value || 3.85)}`),
    api("/api/v1/comprehensive"),
  ]);
  renderAnalytics();
  renderComprehensive();
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
    await api("/api/v1/session/logout", { method: "POST" });
    state.integration = await api("/api/v1/integration/status");
    await reloadCoreData();
    renderIntegration();
    if ($("#integration-dialog").open) $("#integration-dialog").close();
    showToast("已退出登录；已保存数据未被删除");
  } catch (error) {
    $("#school-sync-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function calculateTarget() {
  const button = $("#calculate-target");
  const target = Number($("#target-gpa").value);
  if (!Number.isFinite(target) || target < 0 || target > 4) {
    showToast("目标 GPA 需要在 0 到 4 之间");
    return;
  }
  button.disabled = true;
  try {
    state.analytics = await api(`/api/v1/analytics?target_gpa=${encodeURIComponent(target)}`);
    renderAnalytics();
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

async function saveComprehensiveSettings() {
  const button = $("#save-comprehensive-settings");
  const useCurrentGpa = $("#use-current-gpa").checked;
  const manualValue = $("#manual-base-gpa").value;
  button.disabled = true;
  $("#comprehensive-error").textContent = "";
  try {
    state.comprehensive = await api("/api/v1/comprehensive/settings", {
      method: "PUT",
      body: JSON.stringify({
        use_current_gpa: useCurrentGpa,
        manual_base_gpa: manualValue === "" ? null : Number(manualValue),
      }),
    });
    renderComprehensive();
    showToast("综测基础分设置已保存");
  } catch (error) {
    $("#comprehensive-error").textContent = error.message;
  } finally {
    button.disabled = !state.comprehensive?.editable;
  }
}

async function addComprehensiveItem(event) {
  event.preventDefault();
  const button = $("#add-comprehensive-item");
  button.disabled = true;
  $("#comprehensive-error").textContent = "";
  try {
    state.comprehensive = await api("/api/v1/comprehensive/items", {
      method: "POST",
      body: JSON.stringify({
        kind: $("#comprehensive-item-type").value,
        values: collectComprehensiveValues(),
        note: $("#comprehensive-note").value.trim(),
      }),
    });
    const category = $("#comprehensive-category").value;
    const kind = $("#comprehensive-item-type").value;
    $("#comprehensive-item-form").reset();
    $("#comprehensive-category").value = category;
    renderComprehensive();
    $("#comprehensive-item-type").value = kind;
    renderComprehensiveAutoFields({});
    scheduleComprehensivePreview();
    showToast("加分项已保存并重算");
  } catch (error) {
    $("#comprehensive-error").textContent = error.message;
  } finally {
    button.disabled = !state.comprehensive?.editable;
  }
}

async function deleteComprehensiveItem(itemId) {
  $("#comprehensive-error").textContent = "";
  try {
    state.comprehensive = await api(`/api/v1/comprehensive/items/${itemId}`, {
      method: "DELETE",
    });
    renderComprehensive();
    showToast("加分项已删除");
  } catch (error) {
    $("#comprehensive-error").textContent = error.message;
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
  ["#calendar-search", "#calendar-year", "#calendar-category", "#calendar-status", "#calendar-sort"].forEach(
    (selector) => $(selector).addEventListener("input", renderCompetitionCalendar),
  );
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
  $("#account-logout").addEventListener("click", logoutSchool);
  $("#rule-selector").addEventListener("change", switchRule);
  $("#calculate-target").addEventListener("click", calculateTarget);
  $("#use-current-gpa").addEventListener("change", (event) => {
    $("#manual-gpa-field").hidden = event.target.checked;
  });
  $("#comprehensive-category").addEventListener("change", renderComprehensiveItemTypes);
  $("#comprehensive-item-type").addEventListener("change", () => {
    renderComprehensiveAutoFields({});
    scheduleComprehensivePreview();
  });
  $("#comprehensive-auto-fields").addEventListener("input", scheduleComprehensivePreview);
  $("#comprehensive-auto-fields").addEventListener("change", (event) => {
    if (event.target.matches("select")) {
      renderComprehensiveAutoFields(collectComprehensiveValues());
    }
    scheduleComprehensivePreview();
  });
  $("#save-comprehensive-settings").addEventListener("click", saveComprehensiveSettings);
  $("#comprehensive-item-form").addEventListener("submit", addComprehensiveItem);
}

async function bootstrap() {
  bindEvents();
  try {
    const [user, dashboard, rules, integration, analytics, comprehensive, competitionCalendar] = await Promise.all([
      api("/api/v1/me"),
      api("/api/v1/dashboard"),
      api("/api/v1/rules"),
      api("/api/v1/integration/status"),
      api("/api/v1/analytics?target_gpa=3.85"),
      api("/api/v1/comprehensive"),
      api("/api/v1/competition-calendar"),
    ]);
    state.user = user;
    state.dashboard = dashboard;
    state.rules = rules.items;
    state.integration = integration;
    state.analytics = analytics;
    state.comprehensive = comprehensive;
    state.competitionCalendar = competitionCalendar;
    state.rule = await api(`/api/v1/rules/${encodeURIComponent(rules.selectedRuleId)}`);
    renderUser();
    renderDashboard();
    renderRule();
    renderIntegration();
    renderAnalytics();
    renderComprehensive();
    renderCalendarFilters();
  } catch (error) {
    showToast(`初始化失败：${error.message}`);
  }
}

bootstrap();
