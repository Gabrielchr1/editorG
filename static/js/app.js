import { MONTH_NAMES_PT, cmykToHex, escXml, getTrimDimsMm, hexToCmyk } from "./calendar_client.js";
import { CanvasEditorController, isElementOutOfSafety } from "./canvas_editor.js";
import {
  downloadBatchExport,
  downloadExportFile,
  fetchPreviewPdfUrl,
  renderPreflightReport,
  renderReviewContent,
  runPreflightCheck,
} from "./export_preflight.js";

const state = {
  meta: null,
  projects: [],
  library: [],
  currentProject: null,
  config: null,
  generated: null,
  currentPageIdx: 0,
  selectedElementId: null,
  clipboardElement: null,
  activeLeftTab: "formato",
  zoomPct: 100,
  showRulers: true,
  spreadMode: false,
  undoStack: [],
  redoStack: [],
  saveTimer: null,
  calendarTimer: null,
  isDirty: false,
  selectedTemplateId: "diario",
  reviewMode: "single",
  reviewMonthFilter: "all",
  reviewPdfUrl: null,
  batchRecipients: [],
  libraryCategoryFilter: "all",
  libraryInsertMode: "canvas", // "canvas" | "footer"
};

let canvasCtrl = null;

// ---------------- TEMAS (DARK / CLARO) ----------------

function applyTheme(theme) {
  const normalized = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", normalized);
  localStorage.setItem("eg_theme", normalized);
  const dashBtn = document.getElementById("btn-theme-dash");
  const edBtn = document.getElementById("btn-theme-ed");
  if (normalized === "dark") {
    if (dashBtn) dashBtn.textContent = "☀️ Tema Claro";
    if (edBtn) edBtn.textContent = "☀️ Claro";
  } else {
    if (dashBtn) dashBtn.textContent = "🌙 Tema Escuro";
    if (edBtn) edBtn.textContent = "🌙 Escuro";
  }
}

function initTheme() {
  const saved = localStorage.getItem("eg_theme") || "dark";
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
}

// ---------------- HELPERS & TOAST ----------------

function toast(msg, type = "info") {
  const box = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

function cloneDeep(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function makeCmykObj(c, m, y, k) {
  return { c, m, y, k, hex: cmykToHex(c, m, y, k) };
}

function getSelectedElement() {
  if (!state.config || !state.selectedElementId) return null;
  return (state.config.elements || []).find((e) => e.id === state.selectedElementId) || null;
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

function buildCmykWidgetHtml(prefix, label, colorObj) {
  const col = colorObj || makeCmykObj(0, 0, 0, 100);
  const hex = col.hex || cmykToHex(col.c, col.m, col.y, col.k);
  return `
    <div class="cmyk-card" data-cmyk-group="${prefix}">
      <div class="cmyk-card-head">
        <span class="cmyk-card-title">${escXml(label)}</span>
        <div class="cmyk-preview-wrap">
          <input type="color" class="cmyk-swatch" data-cmyk-picker="${prefix}" value="${hex}" title="Seletor visual (converte para CMYK)" />
          <input type="text" class="input hex-mini" data-cmyk-hex="${prefix}" value="${hex}" maxlength="7" />
        </div>
      </div>
      <div class="cmyk-channels">
        ${["c", "m", "y", "k"].map((ch) => `
          <div class="cmyk-ch">
            <span>${ch.toUpperCase()} %</span>
            <input type="number" min="0" max="100" value="${col[ch] ?? 0}" data-cmyk-num="${prefix}:${ch}" />
            <input type="range" min="0" max="100" value="${col[ch] ?? 0}" data-cmyk-range="${prefix}:${ch}" />
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function bindCmykWidgets(rootEl, getTargetFn, onChangeAfter) {
  rootEl.querySelectorAll("[data-cmyk-num], [data-cmyk-range]").forEach((inp) => {
    inp.addEventListener("input", () => {
      const attr = inp.dataset.cmykNum || inp.dataset.cmykRange;
      const [prefix, ch] = attr.split(":");
      const target = getTargetFn(prefix);
      if (!target) return;
      const val = Math.max(0, Math.min(100, parseInt(inp.value || "0", 10) || 0));
      target[ch] = val;
      target.hex = cmykToHex(target.c, target.m, target.y, target.k);

      const card = inp.closest(".cmyk-card");
      const otherNum = card.querySelector(`[data-cmyk-num="${prefix}:${ch}"]`);
      const otherRng = card.querySelector(`[data-cmyk-range="${prefix}:${ch}"]`);
      const hexInp = card.querySelector(`[data-cmyk-hex="${prefix}"]`);
      const swatch = card.querySelector(`[data-cmyk-picker="${prefix}"]`);
      if (otherNum && otherNum !== inp) otherNum.value = val;
      if (otherRng && otherRng !== inp) otherRng.value = val;
      if (hexInp) hexInp.value = target.hex;
      if (swatch) swatch.value = target.hex;

      onChangeAfter(prefix, target);
    });
  });

  rootEl.querySelectorAll("[data-cmyk-picker], [data-cmyk-hex]").forEach((inp) => {
    const evtName = inp.dataset.cmykPicker ? "input" : "change";
    inp.addEventListener(evtName, () => {
      const prefix = inp.dataset.cmykPicker || inp.dataset.cmykHex;
      const target = getTargetFn(prefix);
      if (!target) return;
      const conv = hexToCmyk(inp.value);
      target.c = conv.c;
      target.m = conv.m;
      target.y = conv.y;
      target.k = conv.k;
      target.hex = conv.hex;

      const card = inp.closest(".cmyk-card");
      ["c", "m", "y", "k"].forEach((ch) => {
        const n = card.querySelector(`[data-cmyk-num="${prefix}:${ch}"]`);
        const r = card.querySelector(`[data-cmyk-range="${prefix}:${ch}"]`);
        if (n) n.value = target[ch];
        if (r) r.value = target[ch];
      });
      const hexInp = card.querySelector(`[data-cmyk-hex="${prefix}"]`);
      const swatch = card.querySelector(`[data-cmyk-picker="${prefix}"]`);
      if (hexInp) hexInp.value = target.hex;
      if (swatch) swatch.value = target.hex;

      onChangeAfter(prefix, target);
    });
  });
}

// ---------------- HISTORY & SAVE ----------------

function pushUndoSnapshot() {
  if (!state.config) return;
  state.undoStack.push(JSON.stringify(state.config));
  if (state.undoStack.length > 40) state.undoStack.shift();
  state.redoStack = [];
}

function applyHistorySnapshot(snapStr) {
  state.config = JSON.parse(snapStr);
  renderLeftTab();
  renderRightPanel();
  refreshCalendarAndRender(true);
  markDirtyAndScheduleSave();
}

function undo() {
  if (!state.undoStack.length) return;
  state.redoStack.push(JSON.stringify(state.config));
  const prev = state.undoStack.pop();
  applyHistorySnapshot(prev);
  toast("Alteração desfeita.");
}

function redo() {
  if (!state.redoStack.length) return;
  state.undoStack.push(JSON.stringify(state.config));
  const nxt = state.redoStack.pop();
  applyHistorySnapshot(nxt);
  toast("Alteração refeita.");
}

function setSaveBadge(status) {
  const el = document.getElementById("save-status");
  if (status === "saving") {
    el.className = "badge badge-warning";
    el.textContent = "Salvando...";
  } else if (status === "dirty") {
    el.className = "badge badge-warning";
    el.textContent = "Não salvo";
  } else if (status === "error") {
    el.className = "badge badge-danger";
    el.textContent = "Erro ao salvar";
  } else {
    el.className = "badge badge-success";
    el.textContent = "Salvo automaticamente";
  }
}

function markDirtyAndScheduleSave() {
  state.isDirty = true;
  setSaveBadge("dirty");
  if (state.saveTimer) clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => {
    saveCurrentProject(true);
  }, 1100);
}

async function saveCurrentProject(silent = false) {
  if (!state.currentProject || !state.config) return;
  setSaveBadge("saving");
  try {
    const res = await fetch(`/api/projects/${state.currentProject.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("ed-project-name").value.trim() || state.currentProject.name,
        client_name: document.getElementById("ed-client-name").value.trim(),
        config: state.config,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const updated = await res.json();
    state.currentProject = updated;
    state.isDirty = false;
    setSaveBadge("saved");
    if (!silent) toast("Projeto salvo com sucesso.", "success");
  } catch (err) {
    setSaveBadge("error");
    toast(`Erro ao salvar: ${err.message}`, "error");
  }
}

// ---------------- CALENDAR SYNC & STAGE RENDER ----------------

function updateStageOverlaysAndStatus() {
  if (!state.config || !state.generated) return;
  const pages = state.generated.pages || [];
  const total = pages.length;
  if (state.currentPageIdx >= total) state.currentPageIdx = Math.max(0, total - 1);

  const page = pages[state.currentPageIdx];
  document.getElementById("nav-page-input").value = page ? page.page_number : 0;
  document.getElementById("nav-page-total").textContent = `/ ${total}`;

  const { w, h } = getTrimDimsMm(state.config);
  const bleed = Number(state.config.page_setup?.bleed_mm ?? 3);
  const gutter = Number(state.config.page_setup?.margin_inner_mm ?? 18);
  document.getElementById("canvas-dim-info").textContent =
    `${w} x ${h} mm (${w / 10}x${h / 10}cm) • Sangria ${bleed}mm • Gutter ${gutter}mm • CMYK`;

  if (page) {
    document.getElementById("canvas-page-info").textContent =
      `Pág. ${page.page_number} de ${total} • ${page.title} • ${state.generated.total_sheets} folhas`;
  }

  const outProblems = (state.config.elements || []).filter((el) => isElementOutOfSafety(el, state.config));
  const alertBadge = document.getElementById("canvas-safety-alert");
  alertBadge.classList.toggle("hidden", outProblems.length === 0);
  if (outProblems.length > 0) {
    alertBadge.textContent = `⚠️ ${outProblems.length} elemento(s) fora da área de segurança`;
  }

  // Atualiza dropdown de meses
  const mSel = document.getElementById("nav-month-jump");
  const curVal = mSel.value;
  let mHtml = `<option value="">Ir p/ Mês...</option>`;
  const mFirst = state.generated.month_first_page || {};
  for (let m = 1; m <= 12; m++) {
    if (mFirst[m]) {
      mHtml += `<option value="${mFirst[m] - 1}">${MONTH_NAMES_PT[m]} (pág. ${mFirst[m]})</option>`;
    }
  }
  mSel.innerHTML = mHtml;
  mSel.value = curVal;
}

function renderStageOnly() {
  if (!canvasCtrl || !state.config || !state.generated) return;
  updateStageOverlaysAndStatus();
  canvasCtrl.render({
    config: state.config,
    pages: state.generated.pages || [],
    currentIndex: state.currentPageIdx,
    zoomPct: state.zoomPct,
    showRulers: state.showRulers,
    spreadMode: state.spreadMode,
    selectedId: state.selectedElementId,
  });
}

async function refreshCalendarAndRender(immediate = false) {
  if (!state.config) return;
  const run = async () => {
    try {
      const res = await fetch("/api/calendar/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.config),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Erro de calendário" }));
        toast(err.detail || "Erro ao gerar páginas", "error");
        return;
      }
      state.generated = await res.json();
      renderStageOnly();
      if (!state.selectedElementId) renderRightPanel();
    } catch (err) {
      toast(`Falha na geração de páginas: ${err.message}`, "error");
    }
  };

  if (immediate) {
    await run();
  } else {
    if (state.calendarTimer) clearTimeout(state.calendarTimer);
    state.calendarTimer = setTimeout(run, 130);
  }
}

// ---------------- DASHBOARD ----------------

async function loadMetaAndLibrary() {
  const [metaRes, libRes] = await Promise.all([fetch("/api/meta"), fetch("/api/library")]);
  state.meta = await metaRes.json();
  const libData = await libRes.json();
  state.library = libData.items || [];
  document.getElementById("stat-templates").textContent = (state.meta.templates || []).length;
  document.getElementById("stat-palettes").textContent = (state.meta.palettes || []).length;
  document.getElementById("stat-library").textContent = state.library.length;
}

async function loadProjects() {
  const res = await fetch("/api/projects");
  const data = await res.json();
  state.projects = data.projects || [];
  document.getElementById("stat-projects").textContent = state.projects.length;
  renderDashboardProjects();
}

function renderDashboardProjects() {
  const grid = document.getElementById("projects-grid");
  const q = (document.getElementById("dash-search-input").value || "").trim().toLowerCase();
  const layoutFilter = document.getElementById("dash-filter-layout").value;

  const filtered = state.projects.filter((p) => {
    const matchQ = !q || p.name.toLowerCase().includes(q) || p.client_name.toLowerCase().includes(q) || String(p.year).includes(q);
    const matchL = layoutFilter === "all" || (p.summary?.layout_mode === layoutFilter);
    return matchQ && matchL;
  });

  if (!filtered.length) {
    grid.innerHTML = `<div class="stat-card" style="grid-column:1/-1;text-align:center;padding:34px;">Nenhum projeto encontrado. Clique em <strong>+ Nova Agenda</strong> para começar.</div>`;
    return;
  }

  const layoutLabels = {
    "1_dpp": "1 Dia/Pág", "2_dpp": "2 Dias/Pág", weekly: "Semanal",
    monthly: "Mensal", financial: "Financeiro", corporate: "Empresarial", planner: "Planner",
  };

  grid.innerHTML = filtered.map((p) => {
    const cols = p.config?.colors || {};
    const swatches = [cols.title_color, cols.decorative_color, cols.highlight_color, cols.holiday_color]
      .filter(Boolean)
      .map((c) => `<span class="cmyk-dot" style="background:${c.hex || "#1e3a5f"}" title="${c.c}/${c.m}/${c.y}/${c.k}"></span>`)
      .join("");

    return `
      <article class="project-card">
        <div class="project-card-top">
          <div>
            <h3>${escXml(p.name)}</h3>
            <div class="project-client">${escXml(p.client_name || "Uso interno / Modelo")}</div>
          </div>
          <span class="badge badge-accent">${p.summary?.is_dated ? p.year : "Permanente"}</span>
        </div>
        <div class="project-meta">
          <span class="badge">${escXml(p.format_name)}</span>
          <span class="badge">${p.page_count} págs</span>
          <span class="badge">${layoutLabels[p.summary?.layout_mode] || p.template_type}</span>
          <span class="badge">${escXml(p.summary?.ruling_type || "horizontal")}</span>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div class="cmyk-dots">${swatches}<span style="font-size:11px;color:var(--text-muted);margin-left:4px;">${escXml(p.summary?.palette_name || "CMYK")}</span></div>
        </div>
        <div class="project-card-actions">
          <button class="btn btn-primary btn-sm" style="flex:1;" data-act="open" data-id="${p.id}">✏️ Abrir no Editor</button>
          <button class="btn btn-secondary btn-sm" data-act="duplicate" data-id="${p.id}" title="Duplicar Projeto">⧉ Duplicar</button>
          <button class="btn btn-secondary btn-sm btn-icon" data-act="export" data-id="${p.id}" title="Exportar PDF">🖨️</button>
          <button class="btn btn-danger btn-sm btn-icon" data-act="delete" data-id="${p.id}" title="Excluir Projeto">🗑</button>
        </div>
      </article>
    `;
  }).join("");

  grid.querySelectorAll("[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.id);
      const act = btn.dataset.act;
      if (act === "open") {
        await openProjectInEditor(id);
      } else if (act === "duplicate") {
        const res = await fetch(`/api/projects/${id}/duplicate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        if (res.ok) {
          toast("Projeto duplicado com sucesso.", "success");
          await loadProjects();
        }
      } else if (act === "export") {
        await openProjectInEditor(id);
        openExportModal();
      } else if (act === "delete") {
        if (!confirm("Deseja realmente excluir este projeto?")) return;
        const res = await fetch(`/api/projects/${id}`, { method: "DELETE" });
        if (res.ok) {
          toast("Projeto excluído.");
          await loadProjects();
        }
      }
    });
  });
}

async function openProjectInEditor(projectId) {
  const res = await fetch(`/api/projects/${projectId}`);
  if (!res.ok) {
    toast("Projeto não encontrado.", "error");
    return;
  }
  const proj = await res.json();
  state.currentProject = proj;
  state.config = proj.config;
  state.selectedElementId = null;
  state.currentPageIdx = 0;
  state.undoStack = [];
  state.redoStack = [];
  state.isDirty = false;
  setSaveBadge("saved");

  document.getElementById("ed-project-name").value = proj.name;
  document.getElementById("ed-client-name").value = proj.client_name || "";

  document.getElementById("view-dashboard").classList.add("hidden");
  document.getElementById("view-editor").classList.remove("hidden");

  syncToolbarToggles();
  renderLeftTab();
  await refreshCalendarAndRender(true);
  renderRightPanel();
}

function syncToolbarToggles() {
  const ps = state.config?.page_setup || {};
  document.getElementById("tog-rulers").classList.toggle("active", state.showRulers);
  document.getElementById("tog-grid").classList.toggle("active", Boolean(ps.show_grid));
  document.getElementById("tog-bleed").classList.toggle("active", Boolean(ps.show_bleed_guide));
  document.getElementById("tog-margins").classList.toggle("active", Boolean(ps.show_margin_guide));
  document.getElementById("tog-safety").classList.toggle("active", Boolean(ps.show_safety_guide));
  document.getElementById("tog-spread").classList.toggle("active", state.spreadMode);
}

// ---------------- LEFT PANEL TABS ----------------

function renderLeftTab() {
  const container = document.getElementById("left-tab-content");
  if (!state.config) return;
  const tab = state.activeLeftTab;

  if (tab === "formato") renderTabFormato(container);
  else if (tab === "datas") renderTabDatas(container);
  else if (tab === "cores") renderTabCores(container);
  else if (tab === "pauta") renderTabPauta(container);
  else if (tab === "rodape") renderTabRodape(container);
  else if (tab === "frases") renderTabFrases(container);
  else if (tab === "especiais") renderTabEspeciais(container);
}

function bindConfigInputs(root, onStructureChange, onVisualOnlyChange) {
  root.querySelectorAll("[data-bind]").forEach((el) => {
    const path = el.dataset.bind;
    const isStruct = el.dataset.struct === "1";
    const evt = (el.type === "checkbox" || el.tagName === "SELECT" || el.type === "date") ? "change" : "input";

    el.addEventListener(evt, () => {
      pushUndoSnapshot();
      const parts = path.split(".");
      let obj = state.config;
      for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
      const key = parts[parts.length - 1];
      let val;
      if (el.type === "checkbox") val = el.checked;
      else if (el.type === "number") val = Number(el.value);
      else val = el.value;
      obj[key] = val;

      // Sincronia automática de ano com datas se aplicável
      if (path === "calendar.year") {
        const yr = parseInt(val, 10) || 2026;
        state.config.calendar.start_date = `${yr}-01-01`;
        state.config.calendar.end_date = `${yr}-12-31`;
        renderLeftTab();
      }
      if (path === "calendar.is_dated" || path === "calendar.layout_mode" || path === "ruling.line_count_mode" || path === "ruling.ruling_type") {
        renderLeftTab();
      }

      markDirtyAndScheduleSave();
      if (isStruct) onStructureChange();
      else onVisualOnlyChange();
    });
  });
}

function renderTabFormato(el) {
  const ps = state.config.page_setup;
  el.innerHTML = `
    <div class="section-title">Tamanho &amp; Orientação da Agenda</div>
    <div class="field">
      <label>Formatos Gráficos Predefinidos</label>
      <select id="fmt-preset" class="select">
        <option value="">Personalizado...</option>
        <option value="150x210">15 x 21 cm (A5 - Padrão Obrigatório)</option>
        <option value="140x200">14 x 20 cm (Agenda Comercial)</option>
        <option value="170x240">17 x 24 cm (Executiva Grande)</option>
        <option value="105x148">10,5 x 14,8 cm (A6 Bolso)</option>
        <option value="210x297">21 x 29,7 cm (A4)</option>
      </select>
    </div>
    <div class="grid-2">
      <div class="field"><label>Largura (mm)</label><input class="input" type="number" step="1" min="60" max="500" value="${ps.width_mm}" data-bind="page_setup.width_mm" /></div>
      <div class="field"><label>Altura (mm)</label><input class="input" type="number" step="1" min="80" max="600" value="${ps.height_mm}" data-bind="page_setup.height_mm" /></div>
    </div>
    <div class="field">
      <label>Orientação</label>
      <select class="select" data-bind="page_setup.orientation">
        <option value="portrait" ${ps.orientation === "portrait" ? "selected" : ""}>Retrato (Vertical)</option>
        <option value="landscape" ${ps.orientation === "landscape" ? "selected" : ""}>Paisagem (Horizontal)</option>
      </select>
    </div>

    <div class="section-title">Sangria &amp; Área de Segurança</div>
    <div class="grid-2">
      <div class="field"><label>Sangria (mm)</label><input class="input" type="number" step="0.5" min="0" max="20" value="${ps.bleed_mm}" data-bind="page_setup.bleed_mm" /></div>
      <div class="field"><label>Segurança (mm)</label><input class="input" type="number" step="0.5" min="0" max="30" value="${ps.safety_margin_mm}" data-bind="page_setup.safety_margin_mm" /></div>
    </div>

    <div class="section-title">Margens &amp; Encadernação (Gutter)</div>
    <div class="grid-2">
      <div class="field"><label>Interna / Espiral (mm)</label><input class="input" type="number" step="0.5" min="2" max="60" value="${ps.margin_inner_mm}" data-bind="page_setup.margin_inner_mm" data-struct="1" /></div>
      <div class="field"><label>Externa (mm)</label><input class="input" type="number" step="0.5" min="2" max="50" value="${ps.margin_outer_mm}" data-bind="page_setup.margin_outer_mm" data-struct="1" /></div>
      <div class="field"><label>Superior (mm)</label><input class="input" type="number" step="0.5" min="2" max="50" value="${ps.margin_top_mm}" data-bind="page_setup.margin_top_mm" data-struct="1" /></div>
      <div class="field"><label>Inferior (mm)</label><input class="input" type="number" step="0.5" min="2" max="50" value="${ps.margin_bottom_mm}" data-bind="page_setup.margin_bottom_mm" data-struct="1" /></div>
    </div>
    <label class="switch-row">
      <span>Espelhar margem interna (frente/verso)</span>
      <input type="checkbox" ${ps.mirror_margins ? "checked" : ""} data-bind="page_setup.mirror_margins" data-struct="1" />
    </label>

    <div class="section-title">Grades &amp; Guias Auxiliares</div>
    <div class="field"><label>Tamanho da Grade (mm)</label><input class="input" type="number" step="1" min="1" max="50" value="${ps.grid_size_mm}" data-bind="page_setup.grid_size_mm" /></div>
  `;

  el.querySelector("#fmt-preset").addEventListener("change", (ev) => {
    const val = ev.target.value;
    if (!val) return;
    pushUndoSnapshot();
    const [w, h] = val.split("x").map(Number);
    state.config.page_setup.width_mm = w;
    state.config.page_setup.height_mm = h;
    markDirtyAndScheduleSave();
    renderLeftTab();
    renderStageOnly();
  });

  bindConfigInputs(el, () => refreshCalendarAndRender(true), () => renderStageOnly());
}

function renderTabDatas(el) {
  const cal = state.config.calendar;
  const statesList = Object.keys(state.meta?.state_holidays || {}).sort();
  const customHols = cal.custom_holidays || [];

  el.innerHTML = `
    <div class="section-title">Configuração do Calendário</div>
    <label class="switch-row">
      <span>Agenda Datada (desmarque p/ Permanente)</span>
      <input type="checkbox" ${cal.is_dated ? "checked" : ""} data-bind="calendar.is_dated" data-struct="1" />
    </label>

    <div class="grid-2">
      <div class="field"><label>Ano</label><input class="input" type="number" min="1950" max="2100" value="${cal.year}" data-bind="calendar.year" data-struct="1" ${!cal.is_dated ? "disabled" : ""} /></div>
      <div class="field">
        <label>Início da Semana</label>
        <select class="select" id="cal-week-start">
          <option value="0" ${Number(cal.week_starts_on) === 0 ? "selected" : ""}>Domingo</option>
          <option value="1" ${Number(cal.week_starts_on) === 1 ? "selected" : ""}>Segunda-feira</option>
        </select>
      </div>
    </div>

    <div class="grid-2">
      <div class="field"><label>Data Inicial</label><input class="input" type="date" value="${cal.start_date}" data-bind="calendar.start_date" data-struct="1" ${!cal.is_dated ? "disabled" : ""} /></div>
      <div class="field"><label>Data Final</label><input class="input" type="date" value="${cal.end_date}" data-bind="calendar.end_date" data-struct="1" ${!cal.is_dated ? "disabled" : ""} /></div>
    </div>

    <div class="grid-2">
      <div class="field">
        <label>Disposição das Páginas</label>
        <select class="select" data-bind="calendar.layout_mode" data-struct="1">
          <option value="1_dpp" ${cal.layout_mode === "1_dpp" ? "selected" : ""}>1 Dia por Página</option>
          <option value="2_dpp" ${cal.layout_mode === "2_dpp" ? "selected" : ""}>2 Dias por Página</option>
          <option value="weekly" ${cal.layout_mode === "weekly" ? "selected" : ""}>Agenda Semanal</option>
          <option value="monthly" ${cal.layout_mode === "monthly" ? "selected" : ""}>Planner Mensal</option>
          <option value="financial" ${cal.layout_mode === "financial" ? "selected" : ""}>Financeiro Diário</option>
          <option value="corporate" ${cal.layout_mode === "corporate" ? "selected" : ""}>Empresarial</option>
          <option value="planner" ${cal.layout_mode === "planner" ? "selected" : ""}>Planner Diário</option>
        </select>
      </div>
      <div class="field">
        <label>Finais de Semana</label>
        <select class="select" data-bind="calendar.weekend_mode" data-struct="1">
          <option value="together" ${cal.weekend_mode === "together" ? "selected" : ""}>Sáb e Dom juntos</option>
          <option value="separate" ${cal.weekend_mode === "separate" ? "selected" : ""}>Sáb e Dom separados</option>
        </select>
      </div>
    </div>

    <div class="field">
      <label>Exibição dos Meses</label>
      <select class="select" data-bind="calendar.month_display_style" data-struct="1">
        <option value="full_upper" ${cal.month_display_style === "full_upper" ? "selected" : ""}>JANEIRO (Maiúsculo)</option>
        <option value="full_title" ${cal.month_display_style === "full_title" ? "selected" : ""}>Janeiro (Capitalizado)</option>
        <option value="short_upper" ${cal.month_display_style === "short_upper" ? "selected" : ""}>JAN (Abreviado)</option>
        <option value="num_full" ${cal.month_display_style === "num_full" ? "selected" : ""}>01 • JANEIRO (Numérico)</option>
      </select>
    </div>

    <label class="switch-row"><span>Exibir mini-calendário no cabeçalho</span><input type="checkbox" ${cal.show_mini_calendar ? "checked" : ""} data-bind="calendar.show_mini_calendar" data-struct="1" /></label>
    <label class="switch-row"><span>Gerar páginas de abertura de cada mês</span><input type="checkbox" ${cal.include_month_openers ? "checked" : ""} data-bind="calendar.include_month_openers" data-struct="1" /></label>

    <div class="section-title">Feriados &amp; Datas Comemorativas</div>
    <label class="switch-row"><span>Destacar feriados nacionais do Brasil</span><input type="checkbox" ${cal.highlight_national_holidays ? "checked" : ""} data-bind="calendar.highlight_national_holidays" data-struct="1" /></label>

    <div class="field">
      <label>Feriados Estaduais por UF</label>
      <select class="select" data-bind="calendar.state_code" data-struct="1">
        <option value="">Nenhum estado selecionado</option>
        ${statesList.map((uf) => `<option value="${uf}" ${cal.state_code === uf ? "selected" : ""}>${uf} — Feriados Estaduais</option>`).join("")}
      </select>
    </div>

    <div class="cmyk-card">
      <div style="font-size:11.5px;font-weight:600;margin-bottom:6px;">Adicionar Feriado Municipal / Data Comemorativa</div>
      <div class="grid-2" style="margin-bottom:6px;">
        <input id="ch-date" class="input" type="text" placeholder="MM-DD ou AAAA-MM-DD" />
        <select id="ch-type" class="select">
          <option value="municipal">Municipal</option>
          <option value="state">Estadual</option>
          <option value="commemorative">Comemorativa</option>
        </select>
      </div>
      <div style="display:flex;gap:6px;">
        <input id="ch-name" class="input" type="text" placeholder="Ex: Aniversário da Cidade / Dia do Médico" />
        <button id="btn-add-holiday" class="btn btn-primary btn-sm">+ Add</button>
      </div>
    </div>

    <div id="custom-holidays-list">
      ${customHols.map((h) => `
        <div class="list-card">
          <div>
            <strong style="font-size:11.5px;">${escXml(h.date)}</strong> — ${escXml(h.name)}
            <span class="badge" style="margin-left:4px;">${escXml(h.type)}</span>
          </div>
          <button class="btn btn-danger btn-xs" data-del-hol="${escXml(h.id)}">✕</button>
        </div>
      `).join("")}
    </div>
  `;

  el.querySelector("#cal-week-start").addEventListener("change", (ev) => {
    pushUndoSnapshot();
    state.config.calendar.week_starts_on = Number(ev.target.value);
    markDirtyAndScheduleSave();
    refreshCalendarAndRender(true);
  });

  el.querySelector("#btn-add-holiday").addEventListener("click", () => {
    const dtStr = el.querySelector("#ch-date").value.trim();
    const nm = el.querySelector("#ch-name").value.trim();
    const tp = el.querySelector("#ch-type").value;
    if (!/^\d{2}-\d{2}$/.test(dtStr) && !/^\d{4}-\d{2}-\d{2}$/.test(dtStr)) {
      toast("Informe a data no formato MM-DD (ex: 01-25) ou AAAA-MM-DD.", "warning");
      return;
    }
    if (!nm) {
      toast("Informe o nome do feriado ou data comemorativa.", "warning");
      return;
    }
    pushUndoSnapshot();
    state.config.calendar.custom_holidays.push({
      id: "h_" + Math.random().toString(36).slice(2, 8),
      date: dtStr,
      name: nm,
      type: tp,
      recurring: true,
    });
    markDirtyAndScheduleSave();
    renderLeftTab();
    refreshCalendarAndRender(true);
  });

  el.querySelectorAll("[data-del-hol]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pushUndoSnapshot();
      state.config.calendar.custom_holidays = state.config.calendar.custom_holidays.filter((x) => x.id !== btn.dataset.delHol);
      markDirtyAndScheduleSave();
      renderLeftTab();
      refreshCalendarAndRender(true);
    });
  });

  bindConfigInputs(el, () => refreshCalendarAndRender(), () => renderStageOnly());
}

function renderTabCores(el) {
  const cols = state.config.colors;
  const sysPalettes = state.meta?.palettes || [];
  const userPalettes = state.library.filter((it) => it.category === "palette" && !it.is_system);

  const colorFields = [
    ["title_color", "Cor dos Títulos (Mês / Cabeçalhos)"],
    ["weekday_color", "Cor dos Dias da Semana"],
    ["date_number_color", "Cor dos Números das Datas"],
    ["ruling_line_color", "Cor das Linhas de Pauta"],
    ["decorative_color", "Cor dos Elementos Decorativos"],
    ["highlight_color", "Cor dos Destaques"],
    ["weekend_color", "Cor dos Finais de Semana"],
    ["holiday_color", "Cor dos Feriados"],
    ["background_color", "Cor de Fundo do Papel"],
  ];

  el.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <span class="badge badge-accent">Cartela Gráfica 100% CMYK</span>
      <button id="btn-save-palette" class="btn btn-secondary btn-xs">💾 Salvar Paleta Atual</button>
    </div>

    <div class="section-title">Paletas Predefinidas CMYK</div>
    <div style="max-height:170px;overflow-y:auto;margin-bottom:10px;">
      ${[...userPalettes.map((u) => ({ name: u.name, description: "Modelo salvo por você", colors: u.content })), ...sysPalettes].map((p, idx) => {
        const c = p.colors;
        const dots = [c.title_color, c.decorative_color, c.highlight_color, c.holiday_color]
          .filter(Boolean)
          .map((d) => `<span class="cmyk-dot" style="background:${d.hex || cmykToHex(d.c, d.m, d.y, d.k)}"></span>`)
          .join("");
        return `
          <div class="palette-chip" data-pal-idx="${idx}">
            <div>
              <div style="font-weight:600;font-size:12px;">${escXml(p.name)}</div>
              <div style="font-size:10.5px;color:var(--text-muted);">${escXml(p.description || "")}</div>
            </div>
            <div class="cmyk-dots">${dots}</div>
          </div>
        `;
      }).join("")}
    </div>

    <div class="section-title">Personalização Individual CMYK</div>
    ${colorFields.map(([key, lbl]) => buildCmykWidgetHtml(key, lbl, cols[key])).join("")}
  `;

  const allPals = [
    ...userPalettes.map((u) => ({ name: u.name, colors: u.content })),
    ...sysPalettes,
  ];
  el.querySelectorAll("[data-pal-idx]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const pal = allPals[Number(chip.dataset.palIdx)];
      if (!pal) return;
      pushUndoSnapshot();
      state.config.colors = cloneDeep(pal.colors);
      if (pal.colors.ruling_line_color) {
        state.config.ruling.line_color = cloneDeep(pal.colors.ruling_line_color);
      }
      markDirtyAndScheduleSave();
      renderLeftTab();
      renderStageOnly();
      toast(`Paleta CMYK "${pal.name}" aplicada.`, "success");
    });
  });

  el.querySelector("#btn-save-palette").addEventListener("click", async () => {
    const name = prompt("Nome do modelo de paleta CMYK para salvar:");
    if (!name || !name.trim()) return;
    const res = await fetch("/api/library", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: "palette",
        name: name.trim(),
        description: "Paleta CMYK personalizada",
        tags: "cmyk,personalizada",
        content_json: { ...state.config.colors, palette_name: name.trim() },
      }),
    });
    if (res.ok) {
      await loadMetaAndLibrary();
      renderLeftTab();
      toast("Paleta salva na biblioteca para reutilização!", "success");
    }
  });

  bindCmykWidgets(
    el,
    (prefix) => state.config.colors[prefix],
    (prefix, target) => {
      if (prefix === "ruling_line_color") {
        state.config.ruling.line_color = cloneDeep(target);
      }
      markDirtyAndScheduleSave();
      renderStageOnly();
    }
  );
}

function renderTabPauta(el) {
  const r = state.config.ruling;
  const fonts = state.meta?.fonts || ["Arial", "Georgia"];
  const exp = state.config.export;

  el.innerHTML = `
    <div class="section-title">Configuração da Pauta (Área de Escrita)</div>
    <div class="field">
      <label>Tipo de Pauta</label>
      <select class="select" data-bind="ruling.ruling_type">
        <option value="horizontal" ${r.ruling_type === "horizontal" ? "selected" : ""}>Linhas Horizontais</option>
        <option value="dotted" ${r.ruling_type === "dotted" ? "selected" : ""}>Pontilhada (Bullet/Planner)</option>
        <option value="grid" ${r.ruling_type === "grid" ? "selected" : ""}>Quadriculada</option>
        <option value="blank" ${r.ruling_type === "blank" ? "selected" : ""}>Página Sem Pauta (Lisa)</option>
        <option value="custom" ${r.ruling_type === "custom" ? "selected" : ""}>Personalizada (Colunas/Check)</option>
      </select>
    </div>

    <div class="grid-2">
      <div class="field"><label>Espaçamento (mm)</label><input class="input" type="number" step="0.5" min="2.5" max="30" value="${r.line_spacing_mm}" data-bind="ruling.line_spacing_mm" /></div>
      <div class="field"><label>Espessura (pt)</label><input class="input" type="number" step="0.1" min="0.1" max="5" value="${r.line_thickness_pt}" data-bind="ruling.line_thickness_pt" /></div>
    </div>

    <div class="grid-2">
      <div class="field">
        <label>Quantidade de Linhas</label>
        <select class="select" data-bind="ruling.line_count_mode">
          <option value="auto" ${r.line_count_mode === "auto" ? "selected" : ""}>Automática (preencher)</option>
          <option value="fixed" ${r.line_count_mode === "fixed" ? "selected" : ""}>Quantidade Fixa</option>
        </select>
      </div>
      <div class="field">
        <label>Qtd. Fixa</label>
        <input class="input" type="number" min="1" max="80" value="${r.fixed_line_count}" data-bind="ruling.fixed_line_count" ${r.line_count_mode !== "fixed" ? "disabled" : ""} />
      </div>
    </div>

    <div class="section-title">Margens Internas da Pauta (Recuos)</div>
    <div class="grid-2">
      <div class="field"><label>Topo / Cabeçalho (mm)</label><input class="input" type="number" step="1" min="18" max="120" value="${r.margin_top_offset_mm}" data-bind="ruling.margin_top_offset_mm" /></div>
      <div class="field"><label>Base / Rodapé (mm)</label><input class="input" type="number" step="1" min="0" max="80" value="${r.margin_bottom_offset_mm}" data-bind="ruling.margin_bottom_offset_mm" /></div>
      <div class="field"><label>Recuo Esquerdo (mm)</label><input class="input" type="number" step="0.5" min="0" max="50" value="${r.margin_left_offset_mm}" data-bind="ruling.margin_left_offset_mm" /></div>
      <div class="field"><label>Recuo Direito (mm)</label><input class="input" type="number" step="0.5" min="0" max="50" value="${r.margin_right_offset_mm}" data-bind="ruling.margin_right_offset_mm" /></div>
    </div>

    <div class="section-title">Horários, Checkboxes &amp; Colunas</div>
    <label class="switch-row"><span>Exibir coluna de horários</span><input type="checkbox" ${r.show_time_column ? "checked" : ""} data-bind="ruling.show_time_column" /></label>
    <div class="grid-3">
      <div class="field"><label>Início (h)</label><input class="input" type="number" min="0" max="23" value="${r.time_start_hour}" data-bind="ruling.time_start_hour" /></div>
      <div class="field"><label>Fim (h)</label><input class="input" type="number" min="1" max="23" value="${r.time_end_hour}" data-bind="ruling.time_end_hour" /></div>
      <div class="field">
        <label>Intervalo</label>
        <select class="select" id="ruling-interval">
          <option value="60" ${Number(r.time_interval_min) === 60 ? "selected" : ""}>60 min</option>
          <option value="30" ${Number(r.time_interval_min) === 30 ? "selected" : ""}>30 min</option>
        </select>
      </div>
    </div>
    <div class="grid-2">
      <label class="switch-row" style="margin-bottom:0;"><span>Checkboxes</span><input type="checkbox" ${r.show_checkboxes ? "checked" : ""} data-bind="ruling.show_checkboxes" /></label>
      <div class="field" style="margin-bottom:0;"><label>Colunas</label><input class="input" type="number" min="1" max="4" value="${r.custom_columns}" data-bind="ruling.custom_columns" /></div>
    </div>

    <div class="section-title">Cor CMYK da Pauta &amp; Fontes do Miolo</div>
    ${buildCmykWidgetHtml("ruling_line", "Cor da Linha / Pontos da Pauta", r.line_color)}
    <div class="grid-2">
      <div class="field">
        <label>Fonte Títulos</label>
        <select class="select" data-bind="export.header_font_family">
          ${fonts.map((f) => `<option value="${escXml(f)}" ${exp.header_font_family === f ? "selected" : ""}>${escXml(f)}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label>Fonte Textos</label>
        <select class="select" data-bind="export.body_font_family">
          ${fonts.map((f) => `<option value="${escXml(f)}" ${exp.body_font_family === f ? "selected" : ""}>${escXml(f)}</option>`).join("")}
        </select>
      </div>
    </div>
  `;

  el.querySelector("#ruling-interval").addEventListener("change", (ev) => {
    pushUndoSnapshot();
    state.config.ruling.time_interval_min = Number(ev.target.value);
    markDirtyAndScheduleSave();
    renderStageOnly();
  });

  bindCmykWidgets(
    el,
    () => state.config.ruling.line_color,
    (_, target) => {
      state.config.colors.ruling_line_color = cloneDeep(target);
      markDirtyAndScheduleSave();
      renderStageOnly();
    }
  );
  bindConfigInputs(el, () => refreshCalendarAndRender(), () => renderStageOnly());
}

function renderTabRodape(el) {
  const f = state.config.footer;
  const fonts = state.meta?.fonts || ["Arial", "Georgia"];
  el.innerHTML = `
    <div class="section-title">Módulo de Rodapé Personalizado</div>
    <label class="switch-row"><span>Ativar rodapé nas páginas</span><input type="checkbox" ${f.enabled ? "checked" : ""} data-bind="footer.enabled" data-struct="1" /></label>

    <div class="field"><label>Nome da Empresa / Clínica / Escritório</label><input class="input" type="text" value="${escXml(f.company_name)}" data-bind="footer.company_name" placeholder="Ex: Studio Design Ltda" /></div>
    <div class="field"><label>Nome do Profissional</label><input class="input" type="text" value="${escXml(f.professional_name)}" data-bind="footer.professional_name" placeholder="Ex: Dra. Mariana Alves" /></div>
    <div class="field"><label>Texto Adicional (Site / Telefone / CRM)</label><input class="input" type="text" value="${escXml(f.extra_text)}" data-bind="footer.extra_text" placeholder="Ex: (11) 99999-0000 • @clinica" /></div>

    <div class="section-title">Logotipo / Imagem / Símbolo</div>
    <div class="cmyk-card">
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
        <label class="btn btn-primary btn-xs" style="cursor:pointer;">
          ⬆️ Enviar Logo (PNG/JPG/SVG/PDF)
          <input id="footer-logo-upload" type="file" accept=".png,.jpg,.jpeg,.svg,.pdf" class="hidden" />
        </label>
        <button id="btn-pick-logo-lib" class="btn btn-secondary btn-xs">📚 Da Biblioteca</button>
        ${f.logo_url ? `<button id="btn-clear-logo" class="btn btn-danger btn-xs">Remover</button>` : ""}
      </div>
      ${f.logo_url ? `<div class="text-accent" style="font-size:11px;word-break:break-all;">Ativo: ${escXml(f.logo_url)}</div>` : `<div class="text-dim" style="font-size:11px;">Nenhum logotipo selecionado</div>`}
      <div class="grid-2" style="margin-top:8px;">
        <div class="field" style="margin-bottom:0;"><label>Largura Logo (mm)</label><input class="input" type="number" min="4" max="120" step="1" value="${f.logo_width_mm}" data-bind="footer.logo_width_mm" /></div>
        <div class="field" style="margin-bottom:0;"><label>Altura Logo (mm)</label><input class="input" type="number" min="4" max="60" step="1" value="${f.logo_height_mm}" data-bind="footer.logo_height_mm" /></div>
      </div>
    </div>

    <div class="section-title">Estilo, Posição &amp; Aplicação</div>
    <div class="grid-2">
      <div class="field">
        <label>Posição</label>
        <select class="select" data-bind="footer.position">
          <option value="bottom_inside" ${f.position === "bottom_inside" ? "selected" : ""}>Rodapé Limpo</option>
          <option value="bottom_bar" ${f.position === "bottom_bar" ? "selected" : ""}>Faixa Decorativa</option>
          <option value="below_ruling" ${f.position === "below_ruling" ? "selected" : ""}>Logo Abaixo da Pauta</option>
        </select>
      </div>
      <div class="field">
        <label>Alinhamento</label>
        <select class="select" data-bind="footer.alignment">
          <option value="left" ${f.alignment === "left" ? "selected" : ""}>Esquerda</option>
          <option value="center" ${f.alignment === "center" ? "selected" : ""}>Centralizado</option>
          <option value="right" ${f.alignment === "right" ? "selected" : ""}>Direita</option>
          <option value="split" ${f.alignment === "split" ? "selected" : ""}>Dividido (Logo Esq + Texto Dir)</option>
        </select>
      </div>
    </div>

    <div class="grid-2">
      <div class="field">
        <label>Fonte</label>
        <select class="select" data-bind="footer.font_family">
          ${fonts.map((fn) => `<option value="${escXml(fn)}" ${f.font_family === fn ? "selected" : ""}>${escXml(fn)}</option>`).join("")}
        </select>
      </div>
      <div class="field"><label>Tamanho (pt)</label><input class="input" type="number" step="0.5" min="5" max="24" value="${f.font_size_pt}" data-bind="footer.font_size_pt" /></div>
    </div>

    <div class="grid-2" style="margin-bottom:8px;">
      <label class="switch-row" style="margin-bottom:0;"><span>Negrito</span><input type="checkbox" ${f.bold ? "checked" : ""} data-bind="footer.bold" /></label>
      <label class="switch-row" style="margin-bottom:0;"><span>Itálico</span><input type="checkbox" ${f.italic ? "checked" : ""} data-bind="footer.italic" /></label>
    </div>

    <div class="field"><label>Distância da Margem Inferior (mm)</label><input class="input" type="number" step="0.5" min="2" max="40" value="${f.distance_from_bottom_mm}" data-bind="footer.distance_from_bottom_mm" /></div>

    ${buildCmykWidgetHtml("footer_text", "Cor CMYK do Rodapé", f.text_color)}

    <div class="field">
      <label>Em quais páginas aparecerá</label>
      <select class="select" data-bind="footer.apply_to" data-struct="1">
        <option value="all" ${f.apply_to === "all" ? "selected" : ""}>Todas as páginas (exceto capa)</option>
        <option value="daily_only" ${f.apply_to === "daily_only" ? "selected" : ""}>Apenas páginas diárias / miolo</option>
        <option value="odd" ${f.apply_to === "odd" ? "selected" : ""}>Apenas páginas ímpares (Frente)</option>
        <option value="even" ${f.apply_to === "even" ? "selected" : ""}>Apenas páginas pares (Verso)</option>
        <option value="month_openers" ${f.apply_to === "month_openers" ? "selected" : ""}>Apenas aberturas de mês</option>
        <option value="weekdays" ${f.apply_to === "weekdays" ? "selected" : ""}>Apenas dias úteis</option>
        <option value="weekends" ${f.apply_to === "weekends" ? "selected" : ""}>Apenas finais de semana</option>
        <option value="specific_pages" ${f.apply_to === "specific_pages" ? "selected" : ""}>Páginas específicas</option>
      </select>
    </div>
    ${f.apply_to === "specific_pages" ? `<div class="field"><label>Páginas (ex: 2, 5, 10-30)</label><input class="input" type="text" value="${escXml(f.specific_pages)}" data-bind="footer.specific_pages" data-struct="1" /></div>` : ""}

    <button id="btn-footer-apply-all" class="btn btn-secondary btn-sm" style="width:100%;">✨ Aplicar Automaticamente em Todas as Páginas</button>
  `;

  el.querySelector("#footer-logo-upload").addEventListener("change", async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const up = await uploadAssetFile(file, "logo");
    if (up) {
      pushUndoSnapshot();
      state.config.footer.logo_url = up.url;
      state.config.footer.enabled = true;
      markDirtyAndScheduleSave();
      renderLeftTab();
      renderStageOnly();
      if (up.notes) toast(up.notes, "info");
    }
  });

  el.querySelector("#btn-pick-logo-lib").addEventListener("click", () => {
    state.libraryInsertMode = "footer";
    state.libraryCategoryFilter = "logo";
    openLibraryModal();
  });

  el.querySelector("#btn-clear-logo")?.addEventListener("click", () => {
    pushUndoSnapshot();
    state.config.footer.logo_url = "";
    markDirtyAndScheduleSave();
    renderLeftTab();
    renderStageOnly();
  });

  el.querySelector("#btn-footer-apply-all").addEventListener("click", () => {
    pushUndoSnapshot();
    state.config.footer.enabled = true;
    state.config.footer.apply_to = "all";
    markDirtyAndScheduleSave();
    renderLeftTab();
    refreshCalendarAndRender(true);
    toast("Rodapé aplicado automaticamente em todo o miolo!", "success");
  });

  bindCmykWidgets(el, () => state.config.footer.text_color, () => {
    markDirtyAndScheduleSave();
    renderStageOnly();
  });
  bindConfigInputs(el, () => refreshCalendarAndRender(), () => renderStageOnly());
}

function renderTabFrases(el) {
  const els = state.config.elements || [];
  const ruleLabels = {
    all: "Todas págs",
    daily_only: "Págs diárias",
    month_openers: "Abertura mês",
    weekdays: "Dias semana",
    weekends: "Fim semana",
    specific_dates: "Datas esp.",
    specific_pages: "Págs esp.",
  };

  el.innerHTML = `
    <div class="section-title">Frases, Textos &amp; Elementos Globais</div>
    <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:12px;">
      <button id="btn-tab-add-phrase" class="btn btn-primary btn-sm">+ Inserir Nova Frase no Canvas</button>
      <button id="btn-tab-gen-12-phrases" class="btn btn-secondary btn-sm">✨ Gerar 12 Frases Motivacionais (Jan–Dez)</button>
      <div class="grid-2">
        <button id="btn-tab-add-img" class="btn btn-secondary btn-xs">+ Inserir Imagem</button>
        <button id="btn-tab-open-lib" class="btn btn-secondary btn-xs">📚 Biblioteca</button>
      </div>
    </div>

    <div class="section-title">Elementos Ativos no Projeto (${els.length})</div>
    <div id="elements-list-box">
      ${els.length === 0 ? `<div style="color:var(--text-dim);font-size:12px;">Nenhum elemento livre inserido ainda.</div>` : els.map((item) => `
        <div class="list-card ${item.id === state.selectedElementId ? "active" : ""}" data-select-el="${item.id}" style="cursor:pointer;">
          <div style="min-width:0;flex:1;">
            <div style="font-weight:600;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
              ${item.type === "image" ? "🖼️" : (item.type === "shape" ? "◻️" : "✍️")}
              ${escXml(item.label || item.text || "Elemento")}
            </div>
            <div style="font-size:10.5px;color:var(--text-muted);margin-top:2px;">
              ${ruleLabels[item.target_rule] || item.target_rule} • X:${item.x_mm} Y:${item.y_mm} • ${item.rotation_deg || 0}°
            </div>
          </div>
          <div style="display:flex;gap:4px;">
            <button class="btn btn-ghost btn-xs" data-el-dup="${item.id}" title="Duplicar">⧉</button>
            <button class="btn btn-danger btn-xs" data-el-del="${item.id}" title="Excluir">✕</button>
          </div>
        </div>
      `).join("")}
    </div>
  `;

  el.querySelector("#btn-tab-add-phrase").addEventListener("click", () => addNewPhraseElement());
  el.querySelector("#btn-tab-add-img").addEventListener("click", () => triggerCanvasImageUpload());
  el.querySelector("#btn-tab-open-lib").addEventListener("click", () => {
    state.libraryInsertMode = "canvas";
    state.libraryCategoryFilter = "phrase";
    openLibraryModal();
  });

  el.querySelector("#btn-tab-gen-12-phrases").addEventListener("click", () => {
    const phrases = state.meta?.monthly_phrases || [];
    if (!phrases.length) return;
    pushUndoSnapshot();
    const { w } = getTrimDimsMm(state.config);
    phrases.forEach((txt, i) => {
      const m = i + 1;
      state.config.elements.push({
        id: "el_m_" + m + "_" + Math.random().toString(36).slice(2, 6),
        type: "phrase",
        label: `Frase ${MONTH_NAMES_PT[m]}`,
        text: txt,
        image_url: "",
        shape_type: "rect",
        x_mm: 20,
        y_mm: 102,
        width_mm: Math.max(40, Math.min(110, w - 40)),
        height_mm: 14,
        rotation_deg: 0,
        font_family: "Georgia",
        font_size_pt: 9.5,
        bold: false,
        italic: true,
        underline: false,
        alignment: "center",
        color: cloneDeep(state.config.colors.title_color || makeCmykObj(75, 55, 25, 25)),
        bg_color: null,
        border_color: null,
        border_width_pt: 0,
        opacity: 1,
        z_index: 12,
        locked: false,
        target_rule: state.config.calendar.include_month_openers ? "month_openers" : "daily_only",
        target_pages: "",
        target_weekdays: [],
        target_dates: [],
        target_months: [m],
      });
    });
    markDirtyAndScheduleSave();
    renderLeftTab();
    refreshCalendarAndRender(true);
    toast("12 frases motivacionais (Jan a Dez) criadas!", "success");
  });

  el.querySelectorAll("[data-select-el]").forEach((card) => {
    card.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-el-dup], [data-el-del]")) return;
      selectElementAndJumpIfHidden(card.dataset.selectEl);
    });
  });

  el.querySelectorAll("[data-el-dup]").forEach((btn) => {
    btn.addEventListener("click", () => duplicateElementById(btn.dataset.elDup));
  });

  el.querySelectorAll("[data-el-del]").forEach((btn) => {
    btn.addEventListener("click", () => deleteElementById(btn.dataset.elDel));
  });
}

function renderTabEspeciais(el) {
  const sp = state.config.special_pages;
  el.innerHTML = `
    <div class="section-title">Páginas Especiais Automáticas</div>
    <label class="switch-row"><span>Capa / Folha de Rosto</span><input type="checkbox" ${sp.cover_page ? "checked" : ""} data-bind="special_pages.cover_page" data-struct="1" /></label>
    <div class="field"><label>Título da Folha de Rosto</label><input class="input" type="text" value="${escXml(sp.cover_title)}" data-bind="special_pages.cover_title" data-struct="1" /></div>
    <div class="field"><label>Subtítulo da Folha de Rosto</label><input class="input" type="text" value="${escXml(sp.cover_subtitle)}" data-bind="special_pages.cover_subtitle" data-struct="1" /></div>

    <label class="switch-row"><span>Dados Pessoais</span><input type="checkbox" ${sp.personal_data ? "checked" : ""} data-bind="special_pages.personal_data" data-struct="1" /></label>
    <label class="switch-row"><span>Calendário Anual (12 meses)</span><input type="checkbox" ${sp.annual_calendar ? "checked" : ""} data-bind="special_pages.annual_calendar" data-struct="1" /></label>
    <label class="switch-row"><span>Planejamento Anual (Jan–Dez)</span><input type="checkbox" ${sp.annual_planner ? "checked" : ""} data-bind="special_pages.annual_planner" data-struct="1" /></label>
    <label class="switch-row"><span>Página de Metas &amp; Projetos</span><input type="checkbox" ${sp.goals_page ? "checked" : ""} data-bind="special_pages.goals_page" data-struct="1" /></label>
    <label class="switch-row"><span>Controle Financeiro Anual</span><input type="checkbox" ${sp.financial_summary ? "checked" : ""} data-bind="special_pages.financial_summary" data-struct="1" /></label>
    <label class="switch-row"><span>Aniversários &amp; Datas Importantes</span><input type="checkbox" ${sp.birthdays_page ? "checked" : ""} data-bind="special_pages.birthdays_page" data-struct="1" /></label>
    <label class="switch-row"><span>Lista de Contatos</span><input type="checkbox" ${sp.contacts_page ? "checked" : ""} data-bind="special_pages.contacts_page" data-struct="1" /></label>

    <div class="field"><label>Páginas de Anotações ao Final (0 a 40)</label><input class="input" type="number" min="0" max="40" value="${sp.notes_end_pages}" data-bind="special_pages.notes_end_pages" data-struct="1" /></div>
  `;
  bindConfigInputs(el, () => refreshCalendarAndRender(), () => renderStageOnly());
}

// ---------------- RIGHT PANEL: ELEMENT INSPECTOR ----------------

function renderRightPanel() {
  const panel = document.getElementById("right-panel");
  if (!state.config) {
    panel.innerHTML = "";
    return;
  }

  const el = getSelectedElement();
  if (!el) {
    const gen = state.generated || { total_pages: 0, total_sheets: 0, total_days: 0 };
    const { w, h } = getTrimDimsMm(state.config);
    const ps = state.config.page_setup;
    const outCount = (state.config.elements || []).filter((x) => isElementOutOfSafety(x, state.config)).length;

    panel.innerHTML = `
      <div class="section-title">Inspetor de Propriedades</div>
      <div class="info-callout" style="margin-bottom:14px;">
        Clique em qualquer <strong>frase, imagem ou elemento</strong> na página para mover, redimensionar, girar ou definir em quais páginas ele aparece.
      </div>

      <div class="section-title">Resumo Técnico do Miolo</div>
      <div class="list-card"><span>Formato Final</span><strong>${w} x ${h} mm</strong></div>
      <div class="list-card"><span>Total de Páginas</span><strong>${gen.total_pages} págs (${gen.total_sheets} fls)</strong></div>
      <div class="list-card"><span>Dias Gerados</span><strong>${gen.total_days}</strong></div>
      <div class="list-card"><span>Sangria</span><strong>${ps.bleed_mm} mm</strong></div>
      <div class="list-card"><span>Margem Interna</span><strong>${ps.margin_inner_mm} mm (${ps.mirror_margins ? "Espelhada" : "Fixa"})</strong></div>
      <div class="list-card"><span>Segurança</span><strong>${ps.safety_margin_mm} mm</strong></div>
      <div class="list-card"><span>Paleta CMYK</span><strong>${escXml(state.config.colors?.palette_name || "Personalizada")}</strong></div>
      <div class="list-card"><span>Alertas de Margem</span><strong class="${outCount ? "text-danger" : "text-success"}">${outCount ? outCount + " fora" : "Nenhum"}</strong></div>
    `;
    return;
  }

  const fonts = state.meta?.fonts || ["Arial", "Georgia"];
  const wdNames = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
  const isOut = isElementOutOfSafety(el, state.config);

  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <strong style="font-size:13px;">Editar Elemento</strong>
      ${isOut ? `<span class="badge badge-danger">Fora da Segurança</span>` : `<span class="badge badge-success">Na Área Segura</span>`}
    </div>

    <div class="field"><label>Identificação (Etiqueta)</label><input id="ins-label" class="input" type="text" value="${escXml(el.label || "")}" /></div>

    ${el.type === "phrase" ? `
      <div class="field">
        <label>Texto da Frase</label>
        <textarea id="ins-text" class="textarea">${escXml(el.text || "")}</textarea>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:5px;">
          <button class="btn btn-secondary btn-xs ins-var-btn" data-var="{{MES}}">+ Mês</button>
          <button class="btn btn-secondary btn-xs ins-var-btn" data-var="{{ano}}">+ Ano</button>
          <button class="btn btn-secondary btn-xs ins-var-btn" data-var="{{dia_semana}}">+ Dia Semana</button>
          <button class="btn btn-secondary btn-xs ins-var-btn" data-var="{{nome_personalizado}}">+ Nome (Lote)</button>
        </div>
      </div>

      <div class="grid-2">
        <div class="field">
          <label>Fonte</label>
          <select id="ins-font" class="select">
            ${fonts.map((f) => `<option value="${escXml(f)}" ${el.font_family === f ? "selected" : ""}>${escXml(f)}</option>`).join("")}
          </select>
        </div>
        <div class="field"><label>Tamanho (pt)</label><input id="ins-fsize" class="input" type="number" step="0.5" min="5" max="72" value="${el.font_size_pt}" /></div>
      </div>

      <div class="grid-2" style="margin-bottom:8px;">
        <div style="display:flex;gap:4px;">
          <button id="ins-bold" class="btn ${el.bold ? "btn-primary" : "btn-secondary"} btn-xs" style="flex:1;"><b>N</b></button>
          <button id="ins-italic" class="btn ${el.italic ? "btn-primary" : "btn-secondary"} btn-xs" style="flex:1;"><i>I</i></button>
          <button id="ins-under" class="btn ${el.underline ? "btn-primary" : "btn-secondary"} btn-xs" style="flex:1;"><u>S</u></button>
        </div>
        <select id="ins-align" class="select" style="padding:4px 6px;">
          <option value="left" ${el.alignment === "left" ? "selected" : ""}>Esquerda</option>
          <option value="center" ${el.alignment === "center" ? "selected" : ""}>Centro</option>
          <option value="right" ${el.alignment === "right" ? "selected" : ""}>Direita</option>
        </select>
      </div>

      ${buildCmykWidgetHtml("el_color", "Cor CMYK do Texto", el.color)}
    ` : ""}

    <div class="section-title">Posição &amp; Geometria (mm)</div>
    <div class="grid-2">
      <div class="field"><label>X (mm)</label><input id="ins-x" class="input" type="number" step="0.5" value="${el.x_mm}" /></div>
      <div class="field"><label>Y (mm)</label><input id="ins-y" class="input" type="number" step="0.5" value="${el.y_mm}" /></div>
      <div class="field"><label>Largura (mm)</label><input id="ins-w" class="input" type="number" step="0.5" min="4" value="${el.width_mm}" /></div>
      <div class="field"><label>Altura (mm)</label><input id="ins-h" class="input" type="number" step="0.5" min="3" value="${el.height_mm}" /></div>
    </div>
    <div class="grid-2">
      <div class="field"><label>Rotação (°)</label><input id="ins-rot" class="input" type="number" step="1" min="-360" max="360" value="${el.rotation_deg || 0}" /></div>
      <div class="field"><label>Opacidade (${Math.round((el.opacity ?? 1) * 100)}%)</label><input id="ins-op" class="input" type="range" min="0.1" max="1" step="0.05" value="${el.opacity ?? 1}" style="padding:2px;" /></div>
    </div>

    <div class="section-title">Em Quais Páginas Aparecerá</div>
    <div class="field">
      <label>Regra de Aplicação</label>
      <select id="ins-rule" class="select">
        <option value="all" ${el.target_rule === "all" ? "selected" : ""}>Todas as páginas</option>
        <option value="daily_only" ${el.target_rule === "daily_only" ? "selected" : ""}>Apenas páginas diárias / conteúdo</option>
        <option value="month_openers" ${el.target_rule === "month_openers" ? "selected" : ""}>Apenas aberturas de mês</option>
        <option value="weekdays" ${el.target_rule === "weekdays" ? "selected" : ""}>Determinados dias da semana</option>
        <option value="weekends" ${el.target_rule === "weekends" ? "selected" : ""}>Apenas finais de semana</option>
        <option value="specific_dates" ${el.target_rule === "specific_dates" ? "selected" : ""}>Apenas determinadas datas</option>
        <option value="specific_pages" ${el.target_rule === "specific_pages" ? "selected" : ""}>Apenas páginas específicas</option>
      </select>
    </div>

    ${el.target_rule === "specific_pages" ? `
      <div class="field"><label>Números de Páginas (ex: 1, 10, 25-30)</label><input id="ins-tpages" class="input" type="text" value="${escXml(el.target_pages || "")}" /></div>
    ` : ""}

    ${el.target_rule === "specific_dates" ? `
      <div class="field"><label>Datas (ex: 01-01, 03-08, 12-25)</label><input id="ins-tdates" class="input" type="text" value="${escXml((el.target_dates || []).join(", "))}" /></div>
    ` : ""}

    ${el.target_rule === "weekdays" ? `
      <div class="field">
        <label>Dias da Semana</label>
        <div class="wd-pills">
          ${wdNames.map((n, idx) => `<button type="button" class="wd-pill ${(el.target_weekdays || []).includes(idx) ? "active" : ""}" data-wd="${idx}">${n}</button>`).join("")}
        </div>
      </div>
    ` : ""}

    <div class="field">
      <label>Filtrar Meses Específicos (vazio = todos)</label>
      <div class="wd-pills">
        ${Object.entries(MONTH_NAMES_PT).map(([mNum, mName]) => `<button type="button" class="wd-pill ${(el.target_months || []).includes(Number(mNum)) ? "active" : ""}" data-tmonth="${mNum}">${mName.slice(0, 3)}</button>`).join("")}
      </div>
    </div>

    <div class="section-title">Ações do Elemento</div>
    <div class="grid-2" style="margin-bottom:6px;">
      <button id="ins-dup" class="btn btn-secondary btn-xs">⧉ Duplicar</button>
      <button id="ins-copy" class="btn btn-secondary btn-xs">📋 Copiar</button>
      <button id="ins-front" class="btn btn-secondary btn-xs">⬆️ Trazer Frente</button>
      <button id="ins-back" class="btn btn-secondary btn-xs">⬇️ Enviar Trás</button>
    </div>
    <div class="grid-2">
      <button id="ins-save-lib" class="btn btn-secondary btn-xs">📚 Salvar Biblioteca</button>
      <button id="ins-del" class="btn btn-danger btn-xs">🗑 Excluir</button>
    </div>
  `;

  // Bind inspector listeners
  const updateField = (patch, struct = false) => {
    pushUndoSnapshot();
    Object.assign(el, patch);
    // Sincroniza active_elements na página atual para feedback visual imediato sem piscar
    if (!struct && state.generated) {
      (state.generated.pages || []).forEach((p) => {
        (p.active_elements || []).forEach((ae) => {
          if (ae.id === el.id) {
            Object.assign(ae, patch);
            if (patch.text !== undefined) ae.resolved_text = patch.text;
          }
        });
      });
      renderStageOnly();
    } else {
      refreshCalendarAndRender(true);
    }
    markDirtyAndScheduleSave();
  };

  panel.querySelector("#ins-label").addEventListener("input", (e) => {
    el.label = e.target.value;
    markDirtyAndScheduleSave();
    if (state.activeLeftTab === "frases") renderLeftTab();
  });

  if (el.type === "phrase") {
    const txtArea = panel.querySelector("#ins-text");
    txtArea.addEventListener("input", (e) => {
      updateField({ text: e.target.value }, false);
    });
    panel.querySelectorAll(".ins-var-btn").forEach((b) => {
      b.addEventListener("click", () => {
        txtArea.value += (txtArea.value ? " " : "") + b.dataset.var;
        updateField({ text: txtArea.value }, true);
      });
    });
    panel.querySelector("#ins-font").addEventListener("change", (e) => updateField({ font_family: e.target.value }));
    panel.querySelector("#ins-fsize").addEventListener("input", (e) => updateField({ font_size_pt: Number(e.target.value) || 10 }));
    panel.querySelector("#ins-bold").addEventListener("click", () => { updateField({ bold: !el.bold }); renderRightPanel(); });
    panel.querySelector("#ins-italic").addEventListener("click", () => { updateField({ italic: !el.italic }); renderRightPanel(); });
    panel.querySelector("#ins-under").addEventListener("click", () => { updateField({ underline: !el.underline }); renderRightPanel(); });
    panel.querySelector("#ins-align").addEventListener("change", (e) => updateField({ alignment: e.target.value }));

    bindCmykWidgets(panel, () => el.color, () => {
      markDirtyAndScheduleSave();
      renderStageOnly();
    });
  }

  panel.querySelector("#ins-x").addEventListener("input", (e) => updateField({ x_mm: Number(e.target.value) || 0 }));
  panel.querySelector("#ins-y").addEventListener("input", (e) => updateField({ y_mm: Number(e.target.value) || 0 }));
  panel.querySelector("#ins-w").addEventListener("input", (e) => updateField({ width_mm: Math.max(4, Number(e.target.value) || 10) }));
  panel.querySelector("#ins-h").addEventListener("input", (e) => updateField({ height_mm: Math.max(3, Number(e.target.value) || 10) }));
  panel.querySelector("#ins-rot").addEventListener("input", (e) => updateField({ rotation_deg: Number(e.target.value) || 0 }));
  panel.querySelector("#ins-op").addEventListener("input", (e) => updateField({ opacity: Number(e.target.value) || 1 }));

  panel.querySelector("#ins-rule").addEventListener("change", (e) => {
    updateField({ target_rule: e.target.value }, true);
    renderRightPanel();
    if (state.activeLeftTab === "frases") renderLeftTab();
  });

  panel.querySelector("#ins-tpages")?.addEventListener("change", (e) => updateField({ target_pages: e.target.value }, true));
  panel.querySelector("#ins-tdates")?.addEventListener("change", (e) => {
    const arr = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
    updateField({ target_dates: arr }, true);
  });

  panel.querySelectorAll("[data-wd]").forEach((b) => {
    b.addEventListener("click", () => {
      const wd = Number(b.dataset.wd);
      const list = new Set(el.target_weekdays || []);
      if (list.has(wd)) list.delete(wd);
      else list.add(wd);
      updateField({ target_weekdays: Array.from(list).sort() }, true);
      renderRightPanel();
    });
  });

  panel.querySelectorAll("[data-tmonth]").forEach((b) => {
    b.addEventListener("click", () => {
      const mo = Number(b.dataset.tmonth);
      const list = new Set(el.target_months || []);
      if (list.has(mo)) list.delete(mo);
      else list.add(mo);
      updateField({ target_months: Array.from(list).sort((a, b) => a - b) }, true);
      renderRightPanel();
    });
  });

  panel.querySelector("#ins-dup").addEventListener("click", () => duplicateElementById(el.id));
  panel.querySelector("#ins-copy").addEventListener("click", () => {
    state.clipboardElement = cloneDeep(el);
    toast("Elemento copiado! Use Ctrl+V ou Colar.", "info");
  });
  panel.querySelector("#ins-front").addEventListener("click", () => updateField({ z_index: (el.z_index || 10) + 1 }, true));
  panel.querySelector("#ins-back").addEventListener("click", () => updateField({ z_index: Math.max(1, (el.z_index || 10) - 1) }, true));
  panel.querySelector("#ins-del").addEventListener("click", () => deleteElementById(el.id));
  panel.querySelector("#ins-save-lib").addEventListener("click", async () => {
    const res = await fetch("/api/library", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: el.type === "image" ? "graphic" : "phrase",
        name: el.label || (el.text || "").slice(0, 40) || "Elemento Salvo",
        description: "Salvo diretamente do editor",
        content_json: el.type === "image" ? { url: el.image_url } : { text: el.text },
        file_path: el.image_url || "",
      }),
    });
    if (res.ok) {
      await loadMetaAndLibrary();
      toast("Salvo na Biblioteca de Elementos!", "success");
    }
  });
}

// ---------------- ELEMENT ACTIONS ----------------

function addNewPhraseElement(customText = "Digite sua frase personalizada aqui") {
  if (!state.config) return;
  pushUndoSnapshot();
  const { w } = getTrimDimsMm(state.config);
  const newEl = {
    id: "el_" + Math.random().toString(36).slice(2, 10),
    type: "phrase",
    label: "Nova Frase",
    text: customText,
    image_url: "",
    shape_type: "rect",
    x_mm: 20,
    y_mm: 165,
    width_mm: Math.max(40, Math.min(110, w - 40)),
    height_mm: 14,
    rotation_deg: 0,
    font_family: "Georgia",
    font_size_pt: 10,
    bold: false,
    italic: true,
    underline: false,
    alignment: "center",
    color: cloneDeep(state.config.colors.title_color || makeCmykObj(70, 50, 20, 30)),
    bg_color: null,
    border_color: null,
    border_width_pt: 0,
    opacity: 1,
    z_index: 15,
    locked: false,
    target_rule: "all",
    target_pages: "",
    target_weekdays: [],
    target_dates: [],
    target_months: [],
  };
  state.config.elements.push(newEl);
  state.selectedElementId = newEl.id;
  markDirtyAndScheduleSave();
  if (state.activeLeftTab === "frases") renderLeftTab();
  renderRightPanel();
  refreshCalendarAndRender(true);
}

function addNewShapeElement() {
  if (!state.config) return;
  pushUndoSnapshot();
  const newEl = {
    id: "el_" + Math.random().toString(36).slice(2, 10),
    type: "shape",
    label: "Caixa Decorativa",
    text: "",
    image_url: "",
    shape_type: "rounded_rect",
    x_mm: 24,
    y_mm: 140,
    width_mm: 100,
    height_mm: 22,
    rotation_deg: 0,
    font_family: "Arial",
    font_size_pt: 10,
    bold: false,
    italic: false,
    underline: false,
    alignment: "center",
    color: cloneDeep(state.config.colors.decorative_color || makeCmykObj(40, 20, 10, 10)),
    bg_color: null,
    border_color: cloneDeep(state.config.colors.decorative_color || makeCmykObj(40, 20, 10, 10)),
    border_width_pt: 1.0,
    opacity: 1,
    z_index: 8,
    locked: false,
    target_rule: "all",
    target_pages: "",
    target_weekdays: [],
    target_dates: [],
    target_months: [],
  };
  state.config.elements.push(newEl);
  state.selectedElementId = newEl.id;
  markDirtyAndScheduleSave();
  if (state.activeLeftTab === "frases") renderLeftTab();
  renderRightPanel();
  refreshCalendarAndRender(true);
}

function addImageElement(url, label = "Imagem / Símbolo") {
  if (!state.config) return;
  pushUndoSnapshot();
  const newEl = {
    id: "el_" + Math.random().toString(36).slice(2, 10),
    type: "image",
    label,
    text: "",
    image_url: url,
    shape_type: "rect",
    x_mm: 55,
    y_mm: 145,
    width_mm: 40,
    height_mm: 25,
    rotation_deg: 0,
    font_family: "Arial",
    font_size_pt: 10,
    bold: false,
    italic: false,
    underline: false,
    alignment: "center",
    color: makeCmykObj(0, 0, 0, 100),
    bg_color: null,
    border_color: null,
    border_width_pt: 0,
    opacity: 1,
    z_index: 12,
    locked: false,
    target_rule: "all",
    target_pages: "",
    target_weekdays: [],
    target_dates: [],
    target_months: [],
  };
  state.config.elements.push(newEl);
  state.selectedElementId = newEl.id;
  markDirtyAndScheduleSave();
  if (state.activeLeftTab === "frases") renderLeftTab();
  renderRightPanel();
  refreshCalendarAndRender(true);
}

function duplicateElementById(id) {
  const orig = (state.config?.elements || []).find((e) => e.id === id);
  if (!orig) return;
  pushUndoSnapshot();
  const copy = cloneDeep(orig);
  copy.id = "el_" + Math.random().toString(36).slice(2, 10);
  copy.label = (copy.label || "Elemento") + " (Cópia)";
  copy.x_mm = Number((Number(copy.x_mm) + 4).toFixed(1));
  copy.y_mm = Number((Number(copy.y_mm) + 4).toFixed(1));
  state.config.elements.push(copy);
  state.selectedElementId = copy.id;
  markDirtyAndScheduleSave();
  if (state.activeLeftTab === "frases") renderLeftTab();
  renderRightPanel();
  refreshCalendarAndRender(true);
  toast("Elemento duplicado.", "success");
}

function deleteElementById(id) {
  if (!state.config) return;
  pushUndoSnapshot();
  state.config.elements = state.config.elements.filter((e) => e.id !== id);
  if (state.selectedElementId === id) state.selectedElementId = null;
  markDirtyAndScheduleSave();
  if (state.activeLeftTab === "frases") renderLeftTab();
  renderRightPanel();
  refreshCalendarAndRender(true);
}

function selectElementAndJumpIfHidden(elId) {
  state.selectedElementId = elId;
  const pages = state.generated?.pages || [];
  const curPage = pages[state.currentPageIdx];
  const visibleHere = (curPage?.active_elements || []).some((e) => e.id === elId);
  if (!visibleHere) {
    const firstMatchIdx = pages.findIndex((p) => (p.active_elements || []).some((e) => e.id === elId));
    if (firstMatchIdx >= 0) {
      state.currentPageIdx = firstMatchIdx;
      toast(`Navegado para a Página ${firstMatchIdx + 1} onde o elemento aparece.`, "info");
    }
  }
  renderLeftTab();
  renderRightPanel();
  renderStageOnly();
}

async function uploadAssetFile(file, category = "logo") {
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(`/api/upload?save_to_library=true&category=${encodeURIComponent(category)}`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Erro no upload" }));
      toast(err.detail || "Falha no upload.", "error");
      return null;
    }
    const data = await res.json();
    await loadMetaAndLibrary();
    toast(`Arquivo "${data.filename}" enviado!`, "success");
    return data;
  } catch (err) {
    toast(`Erro no upload: ${err.message}`, "error");
    return null;
  }
}

function triggerCanvasImageUpload() {
  document.getElementById("hidden-canvas-img-input").click();
}

// ---------------- MODALS: NEW PROJECT, REVIEW, EXPORT, BATCH, LIBRARY ----------------

function openNewProjectModal() {
  const templates = state.meta?.templates || [];
  const grid = document.getElementById("new-templates-grid");
  grid.innerHTML = templates.map((t) => `
    <div class="template-card ${state.selectedTemplateId === t.id ? "selected" : ""}" data-tpl="${t.id}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
        <strong style="font-size:13px;">${escXml(t.name)}</strong>
        <span class="badge badge-accent">${escXml(t.badge)}</span>
      </div>
      <div style="font-size:11.5px;color:var(--text-muted);">${escXml(t.description)}</div>
    </div>
  `).join("");

  grid.querySelectorAll("[data-tpl]").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedTemplateId = card.dataset.tpl;
      grid.querySelectorAll(".template-card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
    });
  });

  openModal("modal-new-project");
}

function openReviewModal() {
  if (!state.generated || !state.config) return;
  const mSel = document.getElementById("rev-month-filter");
  let opts = `<option value="all">Todos os Meses</option><option value="special">Páginas Especiais</option>`;
  for (let m = 1; m <= 12; m++) opts += `<option value="${m}">${MONTH_NAMES_PT[m]}</option>`;
  mSel.innerHTML = opts;
  mSel.value = state.reviewMonthFilter;
  openModal("modal-review");
  refreshReviewModalContent();
}

async function refreshReviewModalContent() {
  const bodyEl = document.getElementById("review-body");
  const pages = state.generated?.pages || [];
  const curPage = pages[state.currentPageIdx] || pages[0];
  document.getElementById("rev-page-lbl").textContent = `Página ${curPage?.page_number || 0} / ${pages.length}`;

  document.querySelectorAll(".review-mode-btn").forEach((b) => {
    const active = b.dataset.rmode === state.reviewMode;
    b.className = `btn ${active ? "btn-primary" : "btn-secondary"} btn-sm review-mode-btn`;
  });

  const problemElements = (state.config.elements || []).filter((e) => isElementOutOfSafety(e, state.config));

  if (state.reviewMode === "pdf_real") {
    if (state.reviewPdfUrl) URL.revokeObjectURL(state.reviewPdfUrl);
    state.reviewPdfUrl = null;
    renderReviewContent({
      mode: "pdf_real",
      generated: state.generated,
      config: state.config,
      currentPageIdx: state.currentPageIdx,
      monthFilter: state.reviewMonthFilter,
      problemElements,
      containerEl: bodyEl,
      pdfBlobUrl: null,
    });
    try {
      state.reviewPdfUrl = await fetchPreviewPdfUrl(state.currentProject.id, state.config, curPage.page_number);
    } catch (err) {
      toast(`Erro ao gerar preview PDF: ${err.message}`, "error");
    }
  }

  renderReviewContent({
    mode: state.reviewMode,
    generated: state.generated,
    config: state.config,
    currentPageIdx: state.currentPageIdx,
    monthFilter: state.reviewMonthFilter,
    problemElements,
    containerEl: bodyEl,
    pdfBlobUrl: state.reviewPdfUrl,
    onPickPage: (idx) => {
      state.currentPageIdx = idx;
      state.reviewMode = "single";
      refreshReviewModalContent();
      renderStageOnly();
    },
  });
}

async function openExportModal() {
  if (!state.currentProject || !state.config) return;
  document.getElementById("exp-mirror").checked = Boolean(state.config.page_setup.mirror_margins);
  document.getElementById("exp-bleed").checked = Boolean(state.config.export?.include_bleed ?? true);
  document.getElementById("exp-crop-marks").checked = Boolean(state.config.export?.include_crop_marks ?? false);
  openModal("modal-export");

  const box = document.getElementById("preflight-report-box");
  box.innerHTML = `<div style="padding:16px;color:var(--text-muted);">Analisando dimensões, margens, CMYK, fontes e imagens...</div>`;
  try {
    const report = await runPreflightCheck(state.currentProject.id, state.config);
    renderPreflightReport(report, box);
  } catch (err) {
    box.innerHTML = `<div class="badge badge-danger">Erro na pré-impressão: ${escXml(err.message)}</div>`;
  }
}

function parseBatchTextarea() {
  const txt = document.getElementById("batch-lines-input").value || "";
  const list = [];
  txt.split(/\r?\n/).forEach((line) => {
    const clean = line.trim();
    if (!clean) return;
    const [nome, empresa = "", cargo = "", extra = ""] = clean.split(/[;|]/).map((s) => s.trim());
    if (nome) list.push({ nome, empresa, cargo, extra });
  });
  state.batchRecipients = list;
  renderBatchPreviewList();
}

function renderBatchPreviewList() {
  const list = state.batchRecipients;
  document.getElementById("batch-count").textContent = list.length;
  const box = document.getElementById("batch-preview-list");
  if (!list.length) {
    box.innerHTML = `<div style="padding:12px;color:var(--text-dim);font-size:11.5px;">Nenhum destinatário carregado.</div>`;
    return;
  }
  box.innerHTML = list.slice(0, 100).map((r, i) => `
    <div class="batch-row">
      <span><strong>${i + 1}.</strong> ${escXml(r.nome)}</span>
      <span class="text-muted">${escXml(r.empresa || r.cargo || "")}</span>
    </div>
  `).join("") + (list.length > 100 ? `<div class="text-muted" style="padding:6px;font-size:11px;">+ ${list.length - 100} outros registros...</div>` : "");
}

function openLibraryModal() {
  renderLibraryGrid();
  openModal("modal-library");
}

function renderLibraryGrid() {
  const grid = document.getElementById("library-items-grid");
  document.querySelectorAll(".lib-cat-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.cat === state.libraryCategoryFilter);
    b.classList.toggle("btn-primary", b.dataset.cat === state.libraryCategoryFilter);
  });

  const items = state.library.filter((it) => state.libraryCategoryFilter === "all" || it.category === state.libraryCategoryFilter);
  if (!items.length) {
    grid.innerHTML = `<div style="grid-column:1/-1;color:var(--text-muted);padding:20px;">Nenhum item nesta categoria.</div>`;
    return;
  }

  grid.innerHTML = items.map((it) => {
    let previewHtml = "";
    if ((it.category === "logo" || it.category === "graphic") && it.file_path && !it.file_path.endsWith(".pdf")) {
      previewHtml = `<div class="library-thumb-box"><img src="${escXml(it.file_path)}" style="max-height:46px;max-width:100%;" /></div>`;
    } else if (it.category === "palette") {
      const dots = [it.content?.title_color, it.content?.decorative_color, it.content?.highlight_color, it.content?.holiday_color]
        .filter(Boolean)
        .map((c) => `<span class="cmyk-dot" style="background:${c.hex}"></span>`)
        .join("");
      previewHtml = `<div class="cmyk-dots">${dots}</div>`;
    } else if (it.category === "phrase") {
      previewHtml = `<div class="text-muted" style="font-style:italic;font-size:11.5px;">“${escXml((it.content?.text || "").slice(0, 90))}”</div>`;
    }

    return `
      <div class="template-card">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <strong style="font-size:12px;">${escXml(it.name)}</strong>
          <span class="badge">${escXml(it.category)}</span>
        </div>
        ${previewHtml}
        <div style="display:flex;gap:5px;margin-top:6px;">
          ${state.currentProject ? `<button class="btn btn-primary btn-xs" data-lib-use="${it.id}" style="flex:1;">Usar no Projeto</button>` : ""}
          ${!it.is_system ? `<button class="btn btn-danger btn-xs" data-lib-del="${it.id}">✕</button>` : ""}
        </div>
      </div>
    `;
  }).join("");

  grid.querySelectorAll("[data-lib-use]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = state.library.find((x) => x.id === Number(btn.dataset.libUse));
      if (!item || !state.config) return;
      if (item.category === "palette") {
        pushUndoSnapshot();
        state.config.colors = cloneDeep(item.content);
        if (item.content.ruling_line_color) state.config.ruling.line_color = cloneDeep(item.content.ruling_line_color);
        markDirtyAndScheduleSave();
        renderLeftTab();
        renderStageOnly();
      } else if (item.category === "phrase") {
        addNewPhraseElement(item.content?.text || item.name);
      } else if (item.category === "logo" || item.category === "graphic") {
        if (state.libraryInsertMode === "footer") {
          pushUndoSnapshot();
          state.config.footer.logo_url = item.file_path;
          state.config.footer.enabled = true;
          markDirtyAndScheduleSave();
          renderLeftTab();
          renderStageOnly();
        } else {
          addImageElement(item.file_path, item.name);
        }
      }
      closeModal("modal-library");
      toast(`"${item.name}" aplicado ao projeto!`, "success");
    });
  });

  grid.querySelectorAll("[data-lib-del]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.libDel);
      const res = await fetch(`/api/library/${id}`, { method: "DELETE" });
      if (res.ok) {
        await loadMetaAndLibrary();
        renderLibraryGrid();
      }
    });
  });
}

// ---------------- GLOBAL WIREUP ----------------

function bindGlobalEvents() {
  // Theme toggles
  document.getElementById("btn-theme-dash")?.addEventListener("click", toggleTheme);
  document.getElementById("btn-theme-ed")?.addEventListener("click", toggleTheme);

  // Modals close buttons
  document.querySelectorAll("[data-close-modal]").forEach((b) => {
    b.addEventListener("click", () => closeModal(b.dataset.closeModal));
  });

  // Dashboard events
  document.getElementById("dash-search-input").addEventListener("input", renderDashboardProjects);
  document.getElementById("dash-filter-layout").addEventListener("change", renderDashboardProjects);
  document.getElementById("btn-new-agenda-dash").addEventListener("click", openNewProjectModal);
  document.getElementById("btn-open-library-dash").addEventListener("click", openLibraryModal);

  document.getElementById("btn-confirm-create-project").addEventListener("click", async () => {
    const name = document.getElementById("new-proj-name").value.trim() || "Nova Agenda";
    const client = document.getElementById("new-proj-client").value.trim();
    const year = Number(document.getElementById("new-proj-year").value) || 2026;
    const tpl = state.meta.templates.find((t) => t.id === state.selectedTemplateId);
    const cfg = cloneDeep(tpl.config);
    cfg.calendar.year = year;
    cfg.calendar.start_date = `${year}-01-01`;
    cfg.calendar.end_date = `${year}-12-31`;
    if (cfg.calendar.is_dated) cfg.special_pages.cover_title = `AGENDA ${year}`;

    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        client_name: client,
        template_id: state.selectedTemplateId,
        config: cfg,
      }),
    });
    if (!res.ok) {
      toast("Erro ao criar projeto.", "error");
      return;
    }
    const created = await res.json();
    closeModal("modal-new-project");
    await loadProjects();
    await openProjectInEditor(created.id);
    toast("Nova agenda criada!", "success");
  });

  // Editor Topbar
  document.getElementById("btn-back-dash").addEventListener("click", async () => {
    if (state.isDirty) await saveCurrentProject(true);
    document.getElementById("view-editor").classList.add("hidden");
    document.getElementById("view-dashboard").classList.remove("hidden");
    await loadProjects();
  });

  document.getElementById("ed-project-name").addEventListener("input", markDirtyAndScheduleSave);
  document.getElementById("ed-client-name").addEventListener("input", markDirtyAndScheduleSave);
  document.getElementById("btn-save-now").addEventListener("click", () => saveCurrentProject(false));
  document.getElementById("btn-undo").addEventListener("click", undo);
  document.getElementById("btn-redo").addEventListener("click", redo);

  document.getElementById("btn-open-library-ed").addEventListener("click", () => {
    state.libraryInsertMode = "canvas";
    openLibraryModal();
  });
  document.getElementById("btn-open-review").addEventListener("click", openReviewModal);
  document.getElementById("btn-open-export").addEventListener("click", openExportModal);
  document.getElementById("btn-open-batch").addEventListener("click", () => {
    if (!state.batchRecipients.length && !document.getElementById("batch-lines-input").value.trim()) {
      document.getElementById("batch-lines-input").value =
        "Ana Clara Souza; Clínica Horizonte; Diretora\nMarcos Vinícius; Clínica Horizonte; Médico";
    }
    parseBatchTextarea();
    openModal("modal-batch");
  });

  // Left Tabs
  document.querySelectorAll(".left-tabs .tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".left-tabs .tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeLeftTab = btn.dataset.tab;
      renderLeftTab();
    });
  });

  // Subbar Graphic Tools
  document.getElementById("tool-select").addEventListener("click", () => {
    toast("Modo Seleção ativo. Clique e arraste elementos na página.", "info");
  });
  document.getElementById("tool-add-phrase").addEventListener("click", () => addNewPhraseElement());
  document.getElementById("tool-add-image").addEventListener("click", triggerCanvasImageUpload);
  document.getElementById("tool-add-shape").addEventListener("click", addNewShapeElement);
  document.getElementById("tool-dup-el").addEventListener("click", () => {
    if (state.selectedElementId) duplicateElementById(state.selectedElementId);
  });
  document.getElementById("tool-copy-el").addEventListener("click", () => {
    const el = getSelectedElement();
    if (el) {
      state.clipboardElement = cloneDeep(el);
      toast("Elemento copiado!", "info");
    }
  });
  document.getElementById("tool-paste-el").addEventListener("click", () => {
    if (!state.clipboardElement || !state.config) return;
    pushUndoSnapshot();
    const copy = cloneDeep(state.clipboardElement);
    copy.id = "el_" + Math.random().toString(36).slice(2, 10);
    copy.x_mm = Number((copy.x_mm + 4).toFixed(1));
    copy.y_mm = Number((copy.y_mm + 4).toFixed(1));
    state.config.elements.push(copy);
    state.selectedElementId = copy.id;
    markDirtyAndScheduleSave();
    renderRightPanel();
    refreshCalendarAndRender(true);
  });
  document.getElementById("tool-center-h").addEventListener("click", () => {
    const el = getSelectedElement();
    if (!el) return;
    pushUndoSnapshot();
    const { w } = getTrimDimsMm(state.config);
    el.x_mm = Number(((w - el.width_mm) / 2).toFixed(1));
    markDirtyAndScheduleSave();
    renderRightPanel();
    refreshCalendarAndRender(true);
  });
  document.getElementById("tool-del-el").addEventListener("click", () => {
    if (state.selectedElementId) deleteElementById(state.selectedElementId);
  });

  // View toggles
  document.getElementById("tog-rulers").addEventListener("click", () => {
    state.showRulers = !state.showRulers;
    syncToolbarToggles();
    renderStageOnly();
  });
  document.getElementById("tog-grid").addEventListener("click", () => {
    state.config.page_setup.show_grid = !state.config.page_setup.show_grid;
    syncToolbarToggles();
    renderStageOnly();
    markDirtyAndScheduleSave();
  });
  document.getElementById("tog-bleed").addEventListener("click", () => {
    state.config.page_setup.show_bleed_guide = !state.config.page_setup.show_bleed_guide;
    syncToolbarToggles();
    renderStageOnly();
  });
  document.getElementById("tog-margins").addEventListener("click", () => {
    state.config.page_setup.show_margin_guide = !state.config.page_setup.show_margin_guide;
    syncToolbarToggles();
    renderStageOnly();
  });
  document.getElementById("tog-safety").addEventListener("click", () => {
    state.config.page_setup.show_safety_guide = !state.config.page_setup.show_safety_guide;
    syncToolbarToggles();
    renderStageOnly();
  });
  document.getElementById("tog-spread").addEventListener("click", () => {
    state.spreadMode = !state.spreadMode;
    syncToolbarToggles();
    renderStageOnly();
  });

  document.getElementById("sel-zoom").addEventListener("change", (e) => {
    state.zoomPct = Number(e.target.value);
    renderStageOnly();
  });

  // Page Navigation
  const goTo = (idx) => {
    const max = Math.max(0, (state.generated?.pages?.length || 1) - 1);
    state.currentPageIdx = Math.max(0, Math.min(max, idx));
    renderStageOnly();
  };
  document.getElementById("nav-first").addEventListener("click", () => goTo(0));
  document.getElementById("nav-prev").addEventListener("click", () => goTo(state.currentPageIdx - 1));
  document.getElementById("nav-next").addEventListener("click", () => goTo(state.currentPageIdx + 1));
  document.getElementById("nav-last").addEventListener("click", () => goTo((state.generated?.pages?.length || 1) - 1));
  document.getElementById("nav-page-input").addEventListener("change", (e) => goTo((Number(e.target.value) || 1) - 1));
  document.getElementById("nav-month-jump").addEventListener("change", (e) => {
    if (e.target.value !== "") goTo(Number(e.target.value));
  });
  document.getElementById("nav-date-search").addEventListener("change", (e) => {
    const pNum = state.generated?.date_page_index?.[e.target.value];
    if (pNum) goTo(pNum - 1);
    else toast("Data não encontrada no período desta agenda.", "warning");
  });

  // Hidden image upload for canvas
  document.getElementById("hidden-canvas-img-input").addEventListener("change", async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const up = await uploadAssetFile(file, "graphic");
    if (up) addImageElement(up.url, file.name);
    ev.target.value = "";
  });

  // Review Modal Controls
  document.querySelectorAll(".review-mode-btn").forEach((b) => {
    b.addEventListener("click", () => {
      state.reviewMode = b.dataset.rmode;
      refreshReviewModalContent();
    });
  });
  document.getElementById("rev-first").addEventListener("click", () => { state.currentPageIdx = 0; refreshReviewModalContent(); });
  document.getElementById("rev-prev").addEventListener("click", () => { state.currentPageIdx = Math.max(0, state.currentPageIdx - 1); refreshReviewModalContent(); });
  document.getElementById("rev-next").addEventListener("click", () => {
    const max = (state.generated?.pages?.length || 1) - 1;
    state.currentPageIdx = Math.min(max, state.currentPageIdx + 1);
    refreshReviewModalContent();
  });
  document.getElementById("rev-last").addEventListener("click", () => {
    state.currentPageIdx = Math.max(0, (state.generated?.pages?.length || 1) - 1);
    refreshReviewModalContent();
  });
  document.getElementById("rev-month-filter").addEventListener("change", (e) => {
    state.reviewMonthFilter = e.target.value;
    refreshReviewModalContent();
  });
  document.getElementById("rev-find-date-btn").addEventListener("click", () => {
    const dt = document.getElementById("rev-date-search").value;
    const pNum = state.generated?.date_page_index?.[dt];
    if (pNum) {
      state.currentPageIdx = pNum - 1;
      if (state.reviewMode === "grid") state.reviewMode = "single";
      refreshReviewModalContent();
    } else {
      toast("Data não encontrada neste projeto.", "warning");
    }
  });

  // Export Modal Download
  document.getElementById("btn-run-export-download").addEventListener("click", async () => {
    const btn = document.getElementById("btn-run-export-download");
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Gerando PDF CMYK...";
    try {
      const fn = await downloadExportFile(state.currentProject.id, state.config, {
        export_mode: document.getElementById("exp-mode").value,
        mirror_margins: document.getElementById("exp-mirror").checked,
        include_bleed: document.getElementById("exp-bleed").checked,
        include_crop_marks: document.getElementById("exp-crop-marks").checked,
        page_range: document.getElementById("exp-page-range").value,
      });
      toast(`Arquivo "${fn}" gerado e baixado com sucesso!`, "success");
    } catch (err) {
      toast(`Erro na exportação: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  });

  // Batch Modal
  document.getElementById("btn-batch-parse-text").addEventListener("click", parseBatchTextarea);
  document.getElementById("batch-file-input").addEventListener("change", async (ev) => {
    const f = ev.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    const res = await fetch("/api/batch/parse-recipients", { method: "POST", body: fd });
    if (!res.ok) {
      toast("Erro ao ler planilha CSV/XLSX.", "error");
      return;
    }
    const data = await res.json();
    state.batchRecipients = data.recipients || [];
    renderBatchPreviewList();
    toast(`${data.count} destinatários carregados da planilha.`, "success");
  });

  document.getElementById("btn-run-batch-export").addEventListener("click", async () => {
    if (!state.batchRecipients.length) {
      toast("Adicione ao menos 1 destinatário para gerar o lote.", "warning");
      return;
    }
    const btn = document.getElementById("btn-run-batch-export");
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = `⏳ Gerando ${state.batchRecipients.length} PDFs...`;
    try {
      const fn = await downloadBatchExport(state.currentProject.id, state.config, state.batchRecipients, {
        include_bleed: document.getElementById("batch-bleed").checked,
        include_crop_marks: document.getElementById("batch-crop").checked,
        mirror_margins: document.getElementById("batch-mirror").checked,
        page_range: document.getElementById("batch-page-range").value,
      });
      toast(`Lote "${fn}" baixado com sucesso!`, "success");
    } catch (err) {
      toast(`Erro no lote: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  });

  // Library Modal
  document.querySelectorAll(".lib-cat-btn").forEach((b) => {
    b.addEventListener("click", () => {
      state.libraryCategoryFilter = b.dataset.cat;
      renderLibraryGrid();
    });
  });
  document.getElementById("lib-upload-input").addEventListener("change", async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const cat = state.libraryCategoryFilter === "graphic" ? "graphic" : "logo";
    await uploadAssetFile(file, cat);
    renderLibraryGrid();
    ev.target.value = "";
  });

  // Keyboard shortcuts
  window.addEventListener("keydown", (ev) => {
    if (!state.currentProject || document.getElementById("view-editor").classList.contains("hidden")) return;
    const tag = (ev.target?.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;

    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z") {
      ev.preventDefault();
      undo();
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "y") {
      ev.preventDefault();
      redo();
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "d" && state.selectedElementId) {
      ev.preventDefault();
      duplicateElementById(state.selectedElementId);
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "c" && state.selectedElementId) {
      const el = getSelectedElement();
      if (el) {
        state.clipboardElement = cloneDeep(el);
        toast("Elemento copiado!");
      }
    } else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "v" && state.clipboardElement) {
      document.getElementById("tool-paste-el").click();
    } else if (ev.key === "Delete" && state.selectedElementId) {
      deleteElementById(state.selectedElementId);
    }
  });
}

// ---------------- INIT ----------------

async function init() {
  canvasCtrl = new CanvasEditorController({
    stageEl: document.getElementById("canvas-stage"),
    onSelectElement: (id) => {
      state.selectedElementId = id;
      renderRightPanel();
      if (state.activeLeftTab === "frases") renderLeftTab();
      renderStageOnly();
    },
    onElementDragStart: () => {
      pushUndoSnapshot();
    },
    onElementMutate: (id, patch) => {
      const el = (state.config?.elements || []).find((e) => e.id === id);
      if (!el) return;
      Object.assign(el, patch);
      (state.generated?.pages || []).forEach((p) => {
        (p.active_elements || []).forEach((ae) => {
          if (ae.id === id) Object.assign(ae, patch);
        });
      });
      // Atualiza inputs numéricos no inspetor sem reconstruir DOM durante arraste
      const mapIds = { x_mm: "ins-x", y_mm: "ins-y", width_mm: "ins-w", height_mm: "ins-h", rotation_deg: "ins-rot" };
      Object.entries(patch).forEach(([k, v]) => {
        const inp = document.getElementById(mapIds[k]);
        if (inp) inp.value = v;
      });
    },
    onElementCommit: () => {
      markDirtyAndScheduleSave();
      renderRightPanel();
      renderStageOnly();
    },
    onDoubleClickText: (id) => {
      state.selectedElementId = id;
      renderRightPanel();
      const ta = document.getElementById("ins-text");
      if (ta) {
        ta.focus();
        ta.select();
      }
    },
  });

  initTheme();
  bindGlobalEvents();
  await loadMetaAndLibrary();
  await loadProjects();
}

init();
