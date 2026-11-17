// Conferência Completa, Pré-Impressão (Preflight), Exportação CMYK e Personalização em Massa

import { MONTH_NAMES_PT, escXml, renderPageSVG } from "./calendar_client.js";

export async function runPreflightCheck(projectId, config) {
  const res = await fetch(`/api/projects/${projectId}/preflight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function renderPreflightReport(report, containerEl) {
  const badgeMap = {
    ok: `<span class="badge badge-success">APROVADO PARA IMPRESSÃO</span>`,
    warning: `<span class="badge badge-warning">ATENÇÃO (${report.warnings} alerta(s))</span>`,
    error: `<span class="badge badge-danger">ERROS CRÍTICOS (${report.errors})</span>`,
  };
  const iconMap = { ok: "✅", warning: "⚠️", error: "❌", info: "ℹ️" };

  let html = `
    <div class="preflight-header">
      <div>
        <div style="font-weight:700;font-size:13.5px;">Diagnóstico Técnico de Pré-Impressão</div>
        <div class="text-muted" style="font-size:11.5px;margin-top:2px;">${report.total_pages} páginas • ${report.total_sheets} folhas frente/verso</div>
      </div>
      <div>${badgeMap[report.status] || ""}</div>
    </div>
  `;

  (report.checks || []).forEach((chk) => {
    html += `
      <div class="preflight-item">
        <div style="font-size:15px;">${iconMap[chk.status] || "•"}</div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <strong style="font-size:12.5px;">${escXml(chk.title)}</strong>
            <span class="badge">${escXml(chk.category)}</span>
          </div>
          <div class="text-muted" style="font-size:11.5px;margin-top:3px;">${escXml(chk.detail)}</div>
          ${chk.fix_hint ? `<div class="text-accent" style="font-size:11px;margin-top:3px;">💡 ${escXml(chk.fix_hint)}</div>` : ""}
        </div>
      </div>
    `;
  });

  containerEl.innerHTML = html;
}

export async function downloadExportFile(projectId, config, options) {
  const res = await fetch(`/api/projects/${projectId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_mode: options.export_mode,
      include_bleed: options.include_bleed,
      include_crop_marks: options.include_crop_marks,
      mirror_margins: options.mirror_margins,
      page_range: options.page_range || "",
      config_override: config,
    }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(errText || "Falha ao gerar arquivo para impressão.");
  }
  const disp = res.headers.get("Content-Disposition") || "";
  const match = disp.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : (options.export_mode === "single_pdf" ? "agenda.pdf" : "agenda.zip");
  const blob = await res.blob();
  triggerBlobDownload(blob, filename);
  return filename;
}

export async function fetchPreviewPdfUrl(projectId, config, pageNumber, opts = {}) {
  const params = new URLSearchParams({
    page_number: String(pageNumber),
    include_bleed: String(opts.include_bleed ?? true),
    include_crop_marks: String(opts.include_crop_marks ?? true),
    mirror_margins: String(opts.mirror_margins ?? config.page_setup?.mirror_margins ?? true),
  });
  const res = await fetch(`/api/projects/${projectId}/preview-pdf?${params.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function downloadBatchExport(projectId, config, recipients, opts) {
  const res = await fetch(`/api/projects/${projectId}/batch-export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recipients,
      include_bleed: opts.include_bleed,
      include_crop_marks: opts.include_crop_marks,
      mirror_margins: opts.mirror_margins,
      page_range: opts.page_range || "",
      config_override: config,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  const disp = res.headers.get("Content-Disposition") || "";
  const match = disp.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `lote_personalizado.zip`;
  const blob = await res.blob();
  triggerBlobDownload(blob, filename);
  return filename;
}

export function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function renderReviewContent({
  mode,
  generated,
  config,
  currentPageIdx,
  monthFilter,
  problemElements,
  containerEl,
  onPickPage,
  pdfBlobUrl,
}) {
  const pages = generated.pages || [];
  if (!pages.length) {
    containerEl.innerHTML = `<div class="badge badge-warning">Nenhuma página gerada.</div>`;
    return;
  }

  let warningBanner = "";
  if (problemElements.length > 0) {
    warningBanner = `
      <div class="warning-callout">
        <strong class="text-danger">⚠️ ${problemElements.length} elemento(s) fora da área de segurança / margens:</strong>
        <div class="text-muted" style="font-size:11.5px;margin-top:4px;">
          ${problemElements.map((e) => escXml(e.label || e.text || e.id)).join(" • ")}
        </div>
      </div>
    `;
  }

  if (mode === "pdf_real") {
    containerEl.innerHTML = warningBanner + (pdfBlobUrl
      ? `<iframe src="${pdfBlobUrl}" style="width:100%;height:62vh;border:1px solid var(--border);border-radius:6px;background:#fff;"></iframe>`
      : `<div class="text-muted" style="padding:30px;text-align:center;">Gerando visualização PDF real em CMYK...</div>`);
    return;
  }

  if (mode === "single" || mode === "spread") {
    const p1 = pages[currentPageIdx] || pages[0];
    const p2 = mode === "spread" && currentPageIdx + 1 < pages.length ? pages[currentPageIdx + 1] : null;
    const maxW = p2 ? "44%" : "420px";
    let html = warningBanner + `<div style="display:flex;justify-content:center;gap:20px;align-items:flex-start;flex-wrap:wrap;padding:10px 0;">`;
    [p1, p2].filter(Boolean).forEach((p) => {
      html += `
        <div style="width:${maxW};min-width:290px;">
          <div style="background:#fff;box-shadow:var(--shadow-paper);border:1px solid var(--border);border-radius:3px;overflow:hidden;">
            ${renderPageSVG(p, config, { includeElementsInSvg: true })}
          </div>
          <div class="page-stage-caption">
            Página ${p.page_number} (${p.is_even ? "Par" : "Ímpar"}) • ${escXml(p.title)}
          </div>
        </div>
      `;
    });
    html += `</div>`;
    containerEl.innerHTML = html;
    return;
  }

  // Modo Sequência Completa (Grade)
  let filtered = pages;
  if (monthFilter === "special") {
    filtered = pages.filter((p) => p.page_type.startsWith("special_"));
  } else if (monthFilter && monthFilter !== "all") {
    const mNum = Number(monthFilter);
    filtered = pages.filter((p) => p.month === mNum);
  }

  const maxShow = 60;
  const slice = filtered.slice(0, maxShow);
  let gridHtml = warningBanner;
  if (filtered.length > maxShow) {
    gridHtml += `<div class="text-muted" style="margin-bottom:10px;font-size:11.5px;">Exibindo ${maxShow} de ${filtered.length} páginas (filtre por mês acima para inspecionar cada bloco).</div>`;
  }
  gridHtml += `<div class="review-grid">`;
  slice.forEach((p) => {
    gridHtml += `
      <div class="review-thumb" data-jump-page="${p.page_number - 1}">
        <div class="review-thumb-paper">
          ${renderPageSVG(p, config, { includeElementsInSvg: true })}
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;">
          <strong>Pág. ${p.page_number}</strong>
          <span class="text-muted">${p.month ? MONTH_NAMES_PT[p.month].slice(0, 3) : "Esp."}</span>
        </div>
        <div class="text-muted" style="font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escXml(p.title)}</div>
      </div>
    `;
  });
  gridHtml += `</div>`;
  containerEl.innerHTML = gridHtml;

  containerEl.querySelectorAll("[data-jump-page]").forEach((card) => {
    card.addEventListener("click", () => {
      onPickPage(Number(card.dataset.jumpPage));
    });
  });
}
