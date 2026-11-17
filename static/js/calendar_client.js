// Renderização vetorial fiel em milímetros (SVG) das páginas geradas pelo Motor de Calendário

export const MONTH_NAMES_PT = {
  1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
  5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
  9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
};

export function escXml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function cmykToHex(c, m, y, k) {
  const cf = Math.max(0, Math.min(100, Number(c) || 0)) / 100;
  const mf = Math.max(0, Math.min(100, Number(m) || 0)) / 100;
  const yf = Math.max(0, Math.min(100, Number(y) || 0)) / 100;
  const kf = Math.max(0, Math.min(100, Number(k) || 0)) / 100;
  const r = Math.round(255 * (1 - cf) * (1 - kf));
  const g = Math.round(255 * (1 - mf) * (1 - kf));
  const b = Math.round(255 * (1 - yf) * (1 - kf));
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`.toUpperCase();
}

export function hexToCmyk(hex) {
  let s = String(hex || "").trim().replace("#", "");
  if (s.length === 3) s = s.split("").map((ch) => ch + ch).join("");
  if (s.length !== 6) return { c: 0, m: 0, y: 0, k: 100, hex: "#000000" };
  const r = parseInt(s.slice(0, 2), 16) / 255;
  const g = parseInt(s.slice(2, 4), 16) / 255;
  const b = parseInt(s.slice(4, 6), 16) / 255;
  const k = 1 - Math.max(r, g, b);
  if (k >= 0.9999) return { c: 0, m: 0, y: 0, k: 100, hex: "#000000" };
  const c = Math.round(((1 - r - k) / (1 - k)) * 100);
  const m = Math.round(((1 - g - k) / (1 - k)) * 100);
  const y = Math.round(((1 - b - k) / (1 - k)) * 100);
  const kPct = Math.round(k * 100);
  return { c, m, y, k: kPct, hex: cmykToHex(c, m, y, kPct) };
}

function getHex(cObj, fallback = "#1E293B") {
  if (!cObj) return fallback;
  return cObj.hex || cmykToHex(cObj.c, cObj.m, cObj.y, cObj.k);
}

function tintHex(cObj, factor = 0.14) {
  if (!cObj) return "rgba(100,116,139,0.12)";
  const cf = (Number(cObj.c) || 0) * factor;
  const mf = (Number(cObj.m) || 0) * factor;
  const yf = (Number(cObj.y) || 0) * factor;
  const kf = (Number(cObj.k) || 0) * factor;
  return cmykToHex(cf, mf, yf, kf);
}

export function getTrimDimsMm(config) {
  const ps = config.page_setup || {};
  const bw = Number(ps.width_mm || 150);
  const bh = Number(ps.height_mm || 210);
  if (ps.orientation === "landscape") {
    return { w: Math.max(bw, bh), h: Math.min(bw, bh) };
  }
  return { w: Math.min(bw, bh), h: Math.max(bw, bh) };
}

function ptToMm(pt) {
  return pt * 0.352778;
}

function svgRulingArea(x, yTop, w, h, config, opts = {}) {
  const r = config.ruling || {};
  const colors = config.colors || {};
  const rtype = r.ruling_type || "horizontal";
  if (rtype === "blank") return "";

  const spacing = Math.max(2.5, Number(r.line_spacing_mm || 7));
  const strokeW = Math.max(0.12, ptToMm(Number(r.line_thickness_pt || 0.5)));
  const lineCol = getHex(r.line_color || colors.ruling_line_color, "#C0C0C0");
  const decoCol = getHex(colors.decorative_color, "#94A3B8");
  const wdCol = getHex(colors.weekday_color, "#475569");
  const bodyFont = config.export?.body_font_family || "Arial";

  const showTimes = opts.showTimes !== undefined ? opts.showTimes : Boolean(r.show_time_column);
  const showChecks = opts.showChecks !== undefined ? opts.showChecks : Boolean(r.show_checkboxes);
  const cols = opts.columns || Number(r.custom_columns || 1);

  let out = "";

  if (rtype === "dotted") {
    const dotR = Math.max(0.16, strokeW * 0.85);
    for (let yy = yTop + spacing * 0.5; yy <= yTop + h - 0.8; yy += spacing) {
      for (let xx = x + 1; xx <= x + w - 0.8; xx += spacing) {
        out += `<circle cx="${xx.toFixed(2)}" cy="${yy.toFixed(2)}" r="${dotR.toFixed(2)}" fill="${lineCol}" />`;
      }
    }
    return out;
  }

  if (rtype === "grid") {
    for (let yy = yTop; yy <= yTop + h + 0.05; yy += spacing) {
      out += `<line x1="${x.toFixed(2)}" y1="${yy.toFixed(2)}" x2="${(x + w).toFixed(2)}" y2="${yy.toFixed(2)}" stroke="${lineCol}" stroke-width="${strokeW.toFixed(3)}" />`;
    }
    for (let xx = x; xx <= x + w + 0.05; xx += spacing) {
      out += `<line x1="${xx.toFixed(2)}" y1="${yTop.toFixed(2)}" x2="${xx.toFixed(2)}" y2="${(yTop + h).toFixed(2)}" stroke="${lineCol}" stroke-width="${strokeW.toFixed(3)}" />`;
    }
    return out;
  }

  // Horizontal / Custom
  const maxPossible = Math.floor(h / spacing);
  const count = r.line_count_mode === "fixed" ? Math.min(maxPossible, Number(r.fixed_line_count || 22)) : maxPossible;

  const colGap = cols > 1 ? 3 : 0;
  const colW = (w - colGap * (cols - 1)) / Math.max(1, cols);

  const timeLabels = [];
  if (showTimes) {
    const startH = Number(r.time_start_hour ?? 7);
    const endH = Number(r.time_end_hour ?? 21);
    const interval = Number(r.time_interval_min ?? 60);
    for (let m = startH * 60; m <= endH * 60; m += interval) {
      timeLabels.push(`${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);
    }
  }

  for (let cIdx = 0; cIdx < cols; cIdx++) {
    const cx = x + cIdx * (colW + colGap);
    for (let idx = 1; idx <= count; idx++) {
      const ly = yTop + idx * spacing;
      if (ly > yTop + h + 0.1) break;
      out += `<line x1="${cx.toFixed(2)}" y1="${ly.toFixed(2)}" x2="${(cx + colW).toFixed(2)}" y2="${ly.toFixed(2)}" stroke="${lineCol}" stroke-width="${strokeW.toFixed(3)}" />`;
      if (cIdx === 0 && showTimes && idx - 1 < timeLabels.length) {
        out += `<text x="${(cx + 0.5).toFixed(2)}" y="${(ly - 1.2).toFixed(2)}" fill="${wdCol}" font-family="${escXml(bodyFont)}" font-size="${ptToMm(6.8).toFixed(2)}">${timeLabels[idx - 1]}</text>`;
      }
      if (showChecks) {
        const cbX = cx + (cIdx === 0 && showTimes ? 11.0 : 0.8);
        const cbSz = Math.min(2.6, spacing * 0.45);
        out += `<rect x="${cbX.toFixed(2)}" y="${(ly - cbSz - 0.8).toFixed(2)}" width="${cbSz.toFixed(2)}" height="${cbSz.toFixed(2)}" fill="none" stroke="${decoCol}" stroke-width="0.2" />`;
      }
    }
  }
  return out;
}

function svgMiniCalendar(mc, x, yTop, w, h, config, activeDays = new Set()) {
  if (!mc) return "";
  const colors = config.colors || {};
  const titleCol = getHex(colors.title_color, "#1E3A5F");
  const wdCol = getHex(colors.weekday_color, "#475569");
  const numCol = getHex(colors.date_number_color, "#0F172A");
  const hiCol = getHex(colors.highlight_color, "#D97706");
  const decoCol = getHex(colors.decorative_color, "#94A3B8");
  const bodyFont = config.export?.body_font_family || "Arial";

  let out = "";
  out += `<text x="${(x + w / 2).toFixed(2)}" y="${(yTop + 2.3).toFixed(2)}" text-anchor="middle" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(5.8).toFixed(2)}">${escXml(mc.month_name.toUpperCase())} ${mc.year}</text>`;
  out += `<line x1="${x.toFixed(2)}" y1="${(yTop + 3.2).toFixed(2)}" x2="${(x + w).toFixed(2)}" y2="${(yTop + 3.2).toFixed(2)}" stroke="${decoCol}" stroke-width="0.18" />`;

  const weeks = mc.weeks || [];
  const colW = w / 7;
  const rowH = (h - 3.8) / Math.max(1, weeks.length + 1);

  (mc.headers || []).forEach((hdr, ci) => {
    const cx = x + (ci + 0.5) * colW;
    out += `<text x="${cx.toFixed(2)}" y="${(yTop + 3.5 + rowH * 0.72).toFixed(2)}" text-anchor="middle" fill="${wdCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(4.8).toFixed(2)}">${escXml(hdr)}</text>`;
  });

  weeks.forEach((wk, ri) => {
    const ry = yTop + 3.5 + (ri + 1) * rowH;
    wk.forEach((dVal, ci) => {
      if (!dVal) return;
      const cx = x + (ci + 0.5) * colW;
      const cyText = ry + rowH * 0.72;
      if (activeDays.has(dVal)) {
        const rad = Math.min(colW, rowH) * 0.42;
        out += `<circle cx="${cx.toFixed(2)}" cy="${(ry + rowH * 0.52).toFixed(2)}" r="${rad.toFixed(2)}" fill="${hiCol}" />`;
        out += `<text x="${cx.toFixed(2)}" y="${cyText.toFixed(2)}" text-anchor="middle" fill="#FFFFFF" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(4.8).toFixed(2)}">${dVal}</text>`;
      } else {
        out += `<text x="${cx.toFixed(2)}" y="${cyText.toFixed(2)}" text-anchor="middle" fill="${numCol}" font-family="${escXml(bodyFont)}" font-size="${ptToMm(4.8).toFixed(2)}">${dVal}</text>`;
      }
    });
  });

  return out;
}

function svgDayHeader(entry, x, yTop, w, headerH, config, miniCal, compact = false) {
  const colors = config.colors || {};
  const titleCol = getHex(colors.title_color);
  const wdCol = getHex(colors.weekday_color);
  const numCol = getHex(colors.date_number_color);
  const decoCol = getHex(colors.decorative_color);
  const wkndCol = getHex(colors.weekend_color);
  const holCol = getHex(colors.holiday_color);
  const hdrFont = config.export?.header_font_family || "Georgia";
  const bodyFont = config.export?.body_font_family || "Arial";

  const isHol = Boolean(entry.has_holiday);
  const isWknd = Boolean(entry.is_weekend);
  const activeNumCol = isHol ? holCol : (isWknd ? wkndCol : numCol);
  const activeWdCol = isHol ? holCol : (isWknd ? wkndCol : wdCol);
  const boxTint = tintHex(isHol ? colors.holiday_color : (isWknd ? colors.weekend_color : colors.decorative_color), 0.14);

  const boxSz = compact ? 15 : 20;
  let out = "";
  out += `<rect x="${x.toFixed(2)}" y="${yTop.toFixed(2)}" width="${boxSz}" height="${boxSz}" rx="2.2" fill="${boxTint}" />`;
  out += `<text x="${(x + boxSz / 2).toFixed(2)}" y="${(yTop + boxSz * 0.72).toFixed(2)}" text-anchor="middle" fill="${activeNumCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(compact ? 22 : 28).toFixed(2)}">${String(entry.day).padStart(2, "0")}</text>`;

  const infoX = x + boxSz + 4;
  const yearStr = entry.year ? ` ${entry.year}` : "";
  out += `<text x="${infoX.toFixed(2)}" y="${(yTop + 5.8).toFixed(2)}" fill="${titleCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(compact ? 10.5 : 13).toFixed(2)}">${escXml(entry.month_label + yearStr)}</text>`;
  out += `<text x="${infoX.toFixed(2)}" y="${(yTop + (compact ? 10.5 : 11.8)).toFixed(2)}" fill="${activeWdCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(compact ? 8.5 : 10).toFixed(2)}">${escXml(entry.weekday_name)}</text>`;

  const subText = entry.is_dated
    ? `Dia ${entry.day_of_year} • Faltam ${entry.days_remaining}`
    : "Marque:  (D)  (S)  (T)  (Q)  (Q)  (S)  (S)";
  out += `<text x="${infoX.toFixed(2)}" y="${(yTop + (compact ? 14.5 : 16.5)).toFixed(2)}" fill="${wdCol}" font-family="${escXml(bodyFont)}" font-size="${ptToMm(6.8).toFixed(2)}">${escXml(subText)}</text>`;

  if (isHol && entry.holidays?.length) {
    const holText = entry.holidays.map((h) => h.name).join(" • ");
    const badgeY = yTop + (compact ? 16.5 : 19.5);
    const maxBadgeW = (miniCal && !compact) ? Math.max(24, w - 38) : Math.max(24, w - 2);
    const badgeW = Math.min(maxBadgeW, Math.max(32, holText.length * 1.45 + 6));
    const maxChars = Math.max(12, Math.floor((badgeW - 4) / 1.35));
    const clippedHol = holText.length > maxChars ? holText.slice(0, maxChars - 1) + "…" : holText;
    out += `<rect x="${x.toFixed(2)}" y="${badgeY.toFixed(2)}" width="${badgeW.toFixed(2)}" height="4.8" rx="1.2" fill="${tintHex(colors.holiday_color, 0.14)}" />`;
    out += `<text x="${(x + 2).toFixed(2)}" y="${(badgeY + 3.5).toFixed(2)}" fill="${holCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(6.6).toFixed(2)}">${escXml(clippedHol)}</text>`;
  }

  if (miniCal && !compact) {
    const mcW = 34;
    const mcH = Math.min(23, headerH - 2);
    out += svgMiniCalendar(miniCal, x + w - mcW, yTop, mcW, mcH, config, new Set([entry.day]));
  }

  out += `<line x1="${x.toFixed(2)}" y1="${(yTop + headerH - 1.5).toFixed(2)}" x2="${(x + w).toFixed(2)}" y2="${(yTop + headerH - 1.5).toFixed(2)}" stroke="${decoCol}" stroke-width="0.28" />`;
  return out;
}

function svgFooter(page, trimW, trimH, config) {
  if (!page.show_footer) return "";
  const f = config.footer || {};
  const colors = config.colors || {};
  const m = page.effective_margins;
  const x0 = m.left;
  const w = trimW - m.left - m.right;
  const dist = Number(f.distance_from_bottom_mm || 8);
  const fyTop = trimH - dist;

  const parts = [f.company_name, f.professional_name, f.extra_text].map((s) => (s || "").trim()).filter(Boolean);
  const footerText = parts.join("  •  ");
  const textCol = getHex(f.text_color, "#475569");
  const fontFam = f.font_family || "Arial";
  const fontSizeMm = ptToMm(Number(f.font_size_pt || 8));
  const align = f.alignment || "center";
  const pos = f.position || "bottom_inside";

  let out = "";
  if (pos === "bottom_bar") {
    out += `<rect x="${x0.toFixed(2)}" y="${(fyTop - 4).toFixed(2)}" width="${w.toFixed(2)}" height="7.5" fill="${tintHex(colors.decorative_color, 0.14)}" />`;
  }

  const logoUrl = f.logo_url || "";
  const logoW = Number(f.logo_width_mm || 22);
  const logoH = Number(f.logo_height_mm || 10);
  if (logoUrl && !logoUrl.toLowerCase().endsWith(".pdf")) {
    let lx = x0 + (w - logoW) / 2;
    if (align === "left" || align === "split") lx = x0;
    else if (align === "right") lx = x0 + w - logoW;
    const ly = fyTop - logoH * 0.45 - (footerText && align !== "split" ? 3.5 : 0);
    out += `<image href="${escXml(logoUrl)}" x="${lx.toFixed(2)}" y="${ly.toFixed(2)}" width="${logoW.toFixed(2)}" height="${logoH.toFixed(2)}" preserveAspectRatio="xMidYMid meet" />`;
  }

  if (footerText) {
    const ty = fyTop + 1.5;
    let anchor = "middle";
    let tx = x0 + w / 2;
    if (align === "left") { anchor = "start"; tx = x0; }
    else if (align === "right" || align === "split") { anchor = "end"; tx = x0 + w; }
    const fw = f.bold ? "700" : "400";
    const fs = f.italic ? "italic" : "normal";
    out += `<text x="${tx.toFixed(2)}" y="${ty.toFixed(2)}" text-anchor="${anchor}" fill="${textCol}" font-family="${escXml(fontFam)}" font-weight="${fw}" font-style="${fs}" font-size="${fontSizeMm.toFixed(2)}">${escXml(footerText)}</text>`;
  }

  return out;
}

export function renderPageSVG(page, config, options = {}) {
  const { w: trimW, h: trimH } = getTrimDimsMm(config);
  const colors = config.colors || {};
  const ruling = config.ruling || {};
  const bgHex = getHex(colors.background_color, "#FFFFFF");
  const titleCol = getHex(colors.title_color, "#1E3A5F");
  const decoCol = getHex(colors.decorative_color, "#94A3B8");
  const wdCol = getHex(colors.weekday_color, "#475569");
  const numCol = getHex(colors.date_number_color, "#0F172A");
  const hiCol = getHex(colors.highlight_color, "#D97706");
  const wkndCol = getHex(colors.weekend_color, "#B45309");
  const holCol = getHex(colors.holiday_color, "#DC2626");
  const hdrFont = config.export?.header_font_family || "Georgia";
  const bodyFont = config.export?.body_font_family || "Arial";

  const m = page.effective_margins || { left: 18, right: 10, top: 12, bottom: 12 };
  const x0 = m.left;
  const w = trimW - m.left - m.right;
  const y0 = m.top;
  const pt = page.page_type;

  let body = `<rect x="0" y="0" width="${trimW}" height="${trimH}" fill="${bgHex}" />`;

  if (pt === "special_cover") {
    const h = trimH - m.top - m.bottom;
    const cx = x0 + w / 2;
    body += `<rect x="${(x0 + 4).toFixed(2)}" y="${(y0 + 4).toFixed(2)}" width="${(w - 8).toFixed(2)}" height="${(h - 8).toFixed(2)}" rx="4" fill="none" stroke="${decoCol}" stroke-width="0.45" />`;
    body += `<rect x="${(x0 + 6.5).toFixed(2)}" y="${(y0 + 6.5).toFixed(2)}" width="${(w - 13).toFixed(2)}" height="${(h - 13).toFixed(2)}" rx="3" fill="none" stroke="${decoCol}" stroke-width="0.18" />`;
    body += `<text x="${cx.toFixed(2)}" y="${(y0 + h * 0.38).toFixed(2)}" text-anchor="middle" fill="${titleCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(24).toFixed(2)}">${escXml(page.title || "AGENDA")}</text>`;
    body += `<text x="${cx.toFixed(2)}" y="${(y0 + h * 0.45).toFixed(2)}" text-anchor="middle" fill="${wdCol}" font-family="${escXml(hdrFont)}" font-style="italic" font-size="${ptToMm(10.5).toFixed(2)}">${escXml(page.subtitle || "")}</text>`;
    const comp = config.footer?.company_name || "";
    const prof = config.footer?.professional_name || "";
    if (comp || prof) {
      body += `<rect x="${(cx - 42).toFixed(2)}" y="${(y0 + h * 0.60).toFixed(2)}" width="84" height="20" rx="2.5" fill="${tintHex(colors.decorative_color, 0.16)}" />`;
      if (prof) body += `<text x="${cx.toFixed(2)}" y="${(y0 + h * 0.67).toFixed(2)}" text-anchor="middle" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(9.5).toFixed(2)}">${escXml(prof)}</text>`;
      if (comp) body += `<text x="${cx.toFixed(2)}" y="${(y0 + h * 0.73).toFixed(2)}" text-anchor="middle" fill="${wdCol}" font-family="${escXml(bodyFont)}" font-size="${ptToMm(8.5).toFixed(2)}">${escXml(comp)}</text>`;
    }
  } else if (pt.startsWith("special_")) {
    const h = trimH - m.top - m.bottom - 12;
    body += `<text x="${x0.toFixed(2)}" y="${(y0 + 6).toFixed(2)}" fill="${titleCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(13).toFixed(2)}">${escXml(page.title)}</text>`;
    body += `<line x1="${x0.toFixed(2)}" y1="${(y0 + 9).toFixed(2)}" x2="${(x0 + w).toFixed(2)}" y2="${(y0 + 9).toFixed(2)}" stroke="${decoCol}" stroke-width="0.3" />`;
    const sy = y0 + 13;
    const sh = h - 13;
    if (pt === "special_calendar" && page.extra?.calendars_current) {
      const gap = 4;
      const cw = (w - gap * 2) / 3;
      const ch = (sh - gap * 3) / 4;
      page.extra.calendars_current.slice(0, 12).forEach((mc, idx) => {
        const ri = Math.floor(idx / 3);
        const ci = idx % 3;
        body += svgMiniCalendar(mc, x0 + ci * (cw + gap), sy + ri * (ch + gap), cw, ch, config);
      });
    } else if (pt === "special_personal") {
      const fields = ["Nome Completo", "Empresa / Profissão", "Endereço", "Cidade / UF / CEP", "Telefone / WhatsApp", "E-mail", "Site / Redes", "Emergência avisar", "Telefone de emergência", "Tipo Sanguíneo / Saúde"];
      const step = Math.min(13.5, sh / fields.length);
      fields.forEach((lbl, i) => {
        const fy = sy + i * step;
        body += `<text x="${x0.toFixed(2)}" y="${(fy + 3.5).toFixed(2)}" fill="${wdCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">${escXml(lbl.toUpperCase())}</text>`;
        body += `<line x1="${x0.toFixed(2)}" y1="${(fy + 10).toFixed(2)}" x2="${(x0 + w).toFixed(2)}" y2="${(fy + 10).toFixed(2)}" stroke="${getHex(colors.ruling_line_color, "#CBD5E1")}" stroke-width="0.2" />`;
      });
    } else if (pt === "special_planner" || pt === "special_birthdays") {
      const gap = 3.5;
      const cw = (w - gap * 2) / 3;
      const ch = (sh - gap * 3) / 4;
      for (let i = 0; i < 12; i++) {
        const bx = x0 + (i % 3) * (cw + gap);
        const by = sy + Math.floor(i / 3) * (ch + gap);
        body += `<rect x="${bx.toFixed(2)}" y="${by.toFixed(2)}" width="${cw.toFixed(2)}" height="${ch.toFixed(2)}" rx="1.5" fill="none" stroke="${decoCol}" stroke-width="0.2" />`;
        body += `<rect x="${bx.toFixed(2)}" y="${by.toFixed(2)}" width="${cw.toFixed(2)}" height="5" fill="${tintHex(colors.decorative_color, 0.16)}" />`;
        body += `<text x="${(bx + 2).toFixed(2)}" y="${(by + 3.6).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">${MONTH_NAMES_PT[i + 1].toUpperCase()}</text>`;
        body += svgRulingArea(bx + 1.5, by + 5.5, cw - 3, ch - 6.5, config, { showTimes: false, showChecks: false });
      }
    } else if (pt === "special_goals") {
      const secs = ["METAS PROFISSIONAIS", "METAS PESSOAIS", "SAÚDE & HÁBITOS", "PROJETOS & FINANÇAS"];
      const gap = 4.5;
      const cw = (w - gap) / 2;
      const ch = (sh - gap) / 2;
      secs.forEach((sec, idx) => {
        const bx = x0 + (idx % 2) * (cw + gap);
        const by = sy + Math.floor(idx / 2) * (ch + gap);
        body += `<rect x="${bx.toFixed(2)}" y="${by.toFixed(2)}" width="${cw.toFixed(2)}" height="${ch.toFixed(2)}" rx="2" fill="none" stroke="${decoCol}" stroke-width="0.22" />`;
        body += `<text x="${(bx + 2.5).toFixed(2)}" y="${(by + 4.5).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.5).toFixed(2)}">${sec}</text>`;
        body += svgRulingArea(bx + 2, by + 6.5, cw - 4, ch - 8, config, { showTimes: false, showChecks: true });
      });
    } else if (pt === "special_financial") {
      const rh = sh / 14;
      body += `<rect x="${x0.toFixed(2)}" y="${sy.toFixed(2)}" width="${w.toFixed(2)}" height="${rh.toFixed(2)}" fill="${tintHex(colors.decorative_color, 0.2)}" />`;
      body += `<text x="${(x0 + 2).toFixed(2)}" y="${(sy + rh * 0.68).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">MÊS</text>`;
      body += `<text x="${(x0 + w * 0.5).toFixed(2)}" y="${(sy + rh * 0.68).toFixed(2)}" text-anchor="end" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">ENTRADAS</text>`;
      body += `<text x="${(x0 + w * 0.75).toFixed(2)}" y="${(sy + rh * 0.68).toFixed(2)}" text-anchor="end" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">SAÍDAS</text>`;
      body += `<text x="${(x0 + w - 2).toFixed(2)}" y="${(sy + rh * 0.68).toFixed(2)}" text-anchor="end" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">SALDO</text>`;
      for (let i = 1; i <= 13; i++) {
        const ry = sy + i * rh;
        body += `<rect x="${x0.toFixed(2)}" y="${ry.toFixed(2)}" width="${w.toFixed(2)}" height="${rh.toFixed(2)}" fill="none" stroke="${decoCol}" stroke-width="0.18" />`;
        const lbl = i === 13 ? "TOTAL ANUAL" : MONTH_NAMES_PT[i].toUpperCase();
        body += `<text x="${(x0 + 2).toFixed(2)}" y="${(ry + rh * 0.68).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="${i === 13 ? 700 : 400}" font-size="${ptToMm(7.5).toFixed(2)}">${lbl}</text>`;
      }
    } else if (pt === "special_contacts") {
      body += `<rect x="${x0.toFixed(2)}" y="${sy.toFixed(2)}" width="${w.toFixed(2)}" height="6" fill="${tintHex(colors.decorative_color, 0.18)}" />`;
      body += `<text x="${(x0 + 2).toFixed(2)}" y="${(sy + 4.2).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">NOME / EMPRESA</text>`;
      body += `<text x="${(x0 + w * 0.44).toFixed(2)}" y="${(sy + 4.2).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">TELEFONE</text>`;
      body += `<text x="${(x0 + w * 0.72).toFixed(2)}" y="${(sy + 4.2).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">E-MAIL</text>`;
      body += svgRulingArea(x0, sy + 6.5, w, sh - 7, config, { showTimes: false, showChecks: false });
    } else {
      body += svgRulingArea(x0, sy, w, sh, config, { showTimes: false, showChecks: false });
    }
  } else if (pt === "month_opener") {
    const h = trimH - m.top - m.bottom - 10;
    body += `<rect x="${x0.toFixed(2)}" y="${y0.toFixed(2)}" width="${w.toFixed(2)}" height="${h.toFixed(2)}" rx="4" fill="none" stroke="${decoCol}" stroke-width="0.35" />`;
    body += `<rect x="${(x0 + 4).toFixed(2)}" y="${(y0 + 6).toFixed(2)}" width="${(w - 8).toFixed(2)}" height="30" rx="3" fill="${tintHex(colors.decorative_color, 0.16)}" />`;
    const mNum = String(page.month || 1).padStart(2, "0");
    body += `<text x="${(x0 + w / 2).toFixed(2)}" y="${(y0 + 13.5).toFixed(2)}" text-anchor="middle" fill="${hiCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(10).toFixed(2)}">MÊS ${mNum}${page.year ? " • " + page.year : ""}</text>`;
    body += `<text x="${(x0 + w / 2).toFixed(2)}" y="${(y0 + 25).toFixed(2)}" text-anchor="middle" fill="${titleCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(23).toFixed(2)}">${escXml(page.title)}</text>`;
    body += `<text x="${(x0 + w / 2).toFixed(2)}" y="${(y0 + 32).toFixed(2)}" text-anchor="middle" fill="${wdCol}" font-family="${escXml(hdrFont)}" font-style="italic" font-size="${ptToMm(9).toFixed(2)}">Planejamento, Metas &amp; Datas Importantes</text>`;

    let curY = y0 + 42;
    if (page.mini_calendar) {
      const mcW = Math.min(w - 16, 74);
      const mcH = 46;
      body += svgMiniCalendar(page.mini_calendar, x0 + (w - mcW) / 2, curY, mcW, mcH, config);
      curY += mcH + 6;
    }
    const remH = Math.max(30, y0 + h - curY - 6);
    body += `<text x="${(x0 + 6).toFixed(2)}" y="${(curY + 3).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(8.5).toFixed(2)}">METAS &amp; FOCO DO MÊS</text>`;
    body += svgRulingArea(x0 + 6, curY + 5, w - 12, remH - 6, config, { showTimes: false, showChecks: true });
  } else if (pt === "daily_weekend_shared" || pt === "daily_2dpp") {
    const usableH = trimH - m.top - m.bottom - Number(ruling.margin_bottom_offset_mm || 14);
    const halfH = (usableH - 5) / 2;
    const isWknd = pt === "daily_weekend_shared";
    (page.dates || []).slice(0, 2).forEach((entry, idx) => {
      const by = y0 + idx * (halfH + 5);
      const hdrH = 20;
      body += svgDayHeader(entry, x0, by, w, hdrH, config, idx === 0 ? page.mini_calendar : null, true);
      const rl = x0 + Number(ruling.margin_left_offset_mm || 0);
      const rw = Math.max(20, w - Number(ruling.margin_left_offset_mm || 0) - Number(ruling.margin_right_offset_mm || 0));
      body += svgRulingArea(rl, by + hdrH + 1, rw, Math.max(12, halfH - hdrH - 1.5), config, isWknd ? { showTimes: false } : {});
    });
  } else if (pt === "weekly_spread") {
    const usableH = trimH - m.top - m.bottom - Number(ruling.margin_bottom_offset_mm || 14);
    body += `<text x="${x0.toFixed(2)}" y="${(y0 + 5).toFixed(2)}" fill="${titleCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(11.5).toFixed(2)}">${escXml(page.title)}</text>`;
    body += `<line x1="${x0.toFixed(2)}" y1="${(y0 + 7.5).toFixed(2)}" x2="${(x0 + w).toFixed(2)}" y2="${(y0 + 7.5).toFixed(2)}" stroke="${decoCol}" stroke-width="0.28" />`;
    const gridY = y0 + 10;
    const gridH = usableH - 10;
    const gap = 3.5;
    const cellW = (w - gap) / 2;
    const cellH = (gridH - gap * 3) / 4;
    const dates = page.dates || [];
    for (let slot = 0; slot < 8; slot++) {
      const sx = x0 + (slot % 2) * (cellW + gap);
      const sy = gridY + Math.floor(slot / 2) * (cellH + gap);
      body += `<rect x="${sx.toFixed(2)}" y="${sy.toFixed(2)}" width="${cellW.toFixed(2)}" height="${cellH.toFixed(2)}" rx="1.8" fill="none" stroke="${decoCol}" stroke-width="0.2" />`;
      if (slot < dates.length) {
        const d = dates[slot];
        const col = d.has_holiday ? holCol : (d.is_weekend ? wkndCol : titleCol);
        body += `<rect x="${sx.toFixed(2)}" y="${sy.toFixed(2)}" width="${cellW.toFixed(2)}" height="5.8" fill="${tintHex(d.has_holiday ? colors.holiday_color : colors.decorative_color, 0.14)}" />`;
        body += `<text x="${(sx + 2).toFixed(2)}" y="${(sy + 4.1).toFixed(2)}" fill="${col}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(8).toFixed(2)}">${String(d.day).padStart(2, "0")}/${String(d.month).padStart(2, "0")} • ${escXml(d.weekday_name)}</text>`;
        body += svgRulingArea(sx + 1.5, sy + 6.2, cellW - 3, cellH - 7, config, { showTimes: false });
      } else {
        const lbl = slot === 7 || dates.length ? "NOTAS & METAS DA SEMANA" : `DIA ${slot + 1} (D S T Q Q S S)`;
        body += `<rect x="${sx.toFixed(2)}" y="${sy.toFixed(2)}" width="${cellW.toFixed(2)}" height="5.8" fill="${tintHex(colors.highlight_color, 0.14)}" />`;
        body += `<text x="${(sx + 2).toFixed(2)}" y="${(sy + 4.1).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(8).toFixed(2)}">${lbl}</text>`;
        body += svgRulingArea(sx + 1.5, sy + 6.2, cellW - 3, cellH - 7, config, { showTimes: false });
      }
    }
  } else if (pt === "monthly_view") {
    const usableH = trimH - m.top - m.bottom - Number(ruling.margin_bottom_offset_mm || 14);
    body += `<text x="${x0.toFixed(2)}" y="${(y0 + 5.5).toFixed(2)}" fill="${titleCol}" font-family="${escXml(hdrFont)}" font-weight="700" font-size="${ptToMm(13).toFixed(2)}">${escXml(page.title)}</text>`;
    const mini = page.mini_calendar || {};
    const weeks = mini.weeks || [];
    const headers = mini.headers || ["D", "S", "T", "Q", "Q", "S", "S"];
    const holByDay = {};
    (page.dates || []).forEach((d) => { if (d.has_holiday) holByDay[d.day] = d.holidays[0].name; });
    const gridY = y0 + 10;
    const gridH = usableH * 0.72;
    const colW = w / 7;
    const rowH = (gridH - 6) / Math.max(1, weeks.length);
    body += `<rect x="${x0.toFixed(2)}" y="${gridY.toFixed(2)}" width="${w.toFixed(2)}" height="6" fill="${tintHex(colors.decorative_color, 0.22)}" />`;
    headers.forEach((hLbl, ci) => {
      body += `<text x="${(x0 + (ci + 0.5) * colW).toFixed(2)}" y="${(gridY + 4.3).toFixed(2)}" text-anchor="middle" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.5).toFixed(2)}">${escXml(hLbl)}</text>`;
    });
    weeks.forEach((wk, ri) => {
      const ry = gridY + 6 + ri * rowH;
      wk.forEach((dayNum, ci) => {
        const cx = x0 + ci * colW;
        body += `<rect x="${cx.toFixed(2)}" y="${ry.toFixed(2)}" width="${colW.toFixed(2)}" height="${rowH.toFixed(2)}" fill="none" stroke="${decoCol}" stroke-width="0.16" />`;
        if (dayNum > 0) {
          const isH = Boolean(holByDay[dayNum]);
          body += `<text x="${(cx + 1.5).toFixed(2)}" y="${(ry + 3.8).toFixed(2)}" fill="${isH ? holCol : numCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.5).toFixed(2)}">${dayNum}</text>`;
          if (isH) {
            body += `<text x="${(cx + 1.5).toFixed(2)}" y="${(ry + 7.2).toFixed(2)}" fill="${holCol}" font-family="${escXml(bodyFont)}" font-size="${ptToMm(4.8).toFixed(2)}">${escXml(holByDay[dayNum].slice(0, 14))}</text>`;
          }
        }
      });
    });
    const objY = gridY + gridH + 4;
    const objH = usableH - gridH - 14;
    if (objH > 16) {
      body += `<text x="${x0.toFixed(2)}" y="${(objY + 3.5).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(8).toFixed(2)}">OBJETIVOS &amp; PRIORIDADES DO MÊS</text>`;
      body += svgRulingArea(x0, objY + 5, w, objH - 5, config, { showTimes: false, showChecks: true });
    }
  } else {
    // daily_1dpp / financial_daily / corporate_daily / planner_daily
    const entry = (page.dates || [])[0];
    if (entry) {
      const headerH = Math.max(22, Number(ruling.margin_top_offset_mm || 28));
      body += svgDayHeader(entry, x0, y0, w, headerH, config, page.mini_calendar, false);
      const rLeft = x0 + Number(ruling.margin_left_offset_mm || 0);
      const rRight = Number(ruling.margin_right_offset_mm || 0);
      const rw = Math.max(20, w - Number(ruling.margin_left_offset_mm || 0) - rRight);
      const rTop = y0 + headerH + 1.5;
      const rBot = trimH - m.bottom - Number(ruling.margin_bottom_offset_mm || 14);
      const rh = Math.max(20, rBot - rTop);

      if (pt === "financial_daily") {
        const topH = rh * 0.44;
        body += `<text x="${rLeft.toFixed(2)}" y="${(rTop + 3).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">COMPROMISSOS &amp; TAREFAS</text>`;
        body += svgRulingArea(rLeft, rTop + 4.5, rw, topH - 5, config);
        const finY = rTop + topH + 2;
        const finH = rh - topH - 2;
        body += `<rect x="${rLeft.toFixed(2)}" y="${finY.toFixed(2)}" width="${rw.toFixed(2)}" height="5.5" fill="${tintHex(colors.decorative_color, 0.18)}" />`;
        body += `<text x="${(rLeft + 2).toFixed(2)}" y="${(finY + 3.9).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(6.8).toFixed(2)}">DESCRIÇÃO / MOVIMENTAÇÃO</text>`;
        body += `<text x="${(rLeft + rw * 0.78).toFixed(2)}" y="${(finY + 3.9).toFixed(2)}" text-anchor="end" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(6.8).toFixed(2)}">ENTRADA</text>`;
        body += `<text x="${(rLeft + rw - 2).toFixed(2)}" y="${(finY + 3.9).toFixed(2)}" text-anchor="end" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(6.8).toFixed(2)}">SAÍDA</text>`;
        const sp = Number(ruling.line_spacing_mm || 7);
        for (let yy = finY + 5.5 + sp; yy <= finY + finH - 8; yy += sp) {
          body += `<line x1="${rLeft.toFixed(2)}" y1="${yy.toFixed(2)}" x2="${(rLeft + rw).toFixed(2)}" y2="${yy.toFixed(2)}" stroke="${getHex(colors.ruling_line_color)}" stroke-width="0.18" />`;
        }
        body += `<line x1="${(rLeft + rw * 0.6).toFixed(2)}" y1="${finY.toFixed(2)}" x2="${(rLeft + rw * 0.6).toFixed(2)}" y2="${(finY + finH - 8).toFixed(2)}" stroke="${decoCol}" stroke-width="0.2" />`;
        body += `<line x1="${(rLeft + rw * 0.8).toFixed(2)}" y1="${finY.toFixed(2)}" x2="${(rLeft + rw * 0.8).toFixed(2)}" y2="${(finY + finH - 8).toFixed(2)}" stroke="${decoCol}" stroke-width="0.2" />`;
        const sumY = finY + finH - 7;
        body += `<rect x="${rLeft.toFixed(2)}" y="${sumY.toFixed(2)}" width="${rw.toFixed(2)}" height="6.5" rx="1.5" fill="${tintHex(colors.highlight_color, 0.15)}" />`;
        const sumCols = ["SALDO ANT.: R$ ___", "ENTRADAS: R$ ___", "SAÍDAS: R$ ___", "SALDO: R$ ___"];
        const sumColW = rw / 4;
        sumCols.forEach((lbl, sci) => {
          const sx = rLeft + sci * sumColW + 1.8;
          body += `<text x="${sx.toFixed(2)}" y="${(sumY + 4.3).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(6.2).toFixed(2)}">${lbl}</text>`;
        });
      } else if (pt === "corporate_daily") {
        const prioH = 24;
        body += `<rect x="${rLeft.toFixed(2)}" y="${rTop.toFixed(2)}" width="${rw.toFixed(2)}" height="${prioH}" rx="2" fill="none" stroke="${decoCol}" stroke-width="0.22" />`;
        body += `<text x="${(rLeft + 2.5).toFixed(2)}" y="${(rTop + 4).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">PRIORIDADES DO DIA / TOP 3</text>`;
        body += svgRulingArea(rLeft + 2, rTop + 5.5, rw - 4, prioH - 6.5, config, { showTimes: false, showChecks: true });
        const by = rTop + prioH + 3;
        const bh = rh - prioH - 3;
        const lw = rw * 0.62;
        const rgtW = rw - lw - 4;
        body += `<text x="${rLeft.toFixed(2)}" y="${(by + 3).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">HORÁRIOS &amp; REUNIÕES</text>`;
        body += svgRulingArea(rLeft, by + 4.5, lw, bh - 5, config, { showTimes: true, showChecks: false });
        body += `<text x="${(rLeft + lw + 4).toFixed(2)}" y="${(by + 3).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">DELEGAR / FOLLOW-UP</text>`;
        body += svgRulingArea(rLeft + lw + 4, by + 4.5, rgtW, bh - 5, config, { showTimes: false, showChecks: true });
      } else if (pt === "planner_daily") {
        const lw = rw * 0.56;
        const rgtW = rw - lw - 4;
        body += `<text x="${rLeft.toFixed(2)}" y="${(rTop + 3).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7.2).toFixed(2)}">CRONOGRAMA DO DIA</text>`;
        body += svgRulingArea(rLeft, rTop + 4.5, lw, rh - 5, config, { showTimes: true, showChecks: false });
        const rx = rLeft + lw + 4;
        const b1H = rh * 0.45;
        body += `<rect x="${rx.toFixed(2)}" y="${rTop.toFixed(2)}" width="${rgtW.toFixed(2)}" height="${b1H.toFixed(2)}" rx="2" fill="none" stroke="${decoCol}" stroke-width="0.2" />`;
        body += `<text x="${(rx + 2).toFixed(2)}" y="${(rTop + 3.8).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">TAREFAS &amp; CHECKLIST</text>`;
        body += svgRulingArea(rx + 1.5, rTop + 5, rgtW - 3, b1H - 6, config, { showTimes: false, showChecks: true });
        const b2Y = rTop + b1H + 3;
        const b2H = rh - b1H - 3;
        body += `<rect x="${rx.toFixed(2)}" y="${b2Y.toFixed(2)}" width="${rgtW.toFixed(2)}" height="${b2H.toFixed(2)}" rx="2" fill="none" stroke="${decoCol}" stroke-width="0.2" />`;
        body += `<text x="${(rx + 2).toFixed(2)}" y="${(b2Y + 3.8).toFixed(2)}" fill="${titleCol}" font-family="${escXml(bodyFont)}" font-weight="700" font-size="${ptToMm(7).toFixed(2)}">NOTAS &amp; GRATIDÃO</text>`;
        body += svgRulingArea(rx + 1.5, b2Y + 5, rgtW - 3, b2H - 6, config, { showTimes: false, showChecks: false });
      } else {
        body += svgRulingArea(rLeft, rTop, rw, rh, config);
      }
    }
  }

  body += svgFooter(page, trimW, trimH, config);

  // Modo thumbnail (Conferência) também desenha elementos diretamente no SVG com recorte seguro na caixa
  if (options.includeElementsInSvg) {
    (page.active_elements || []).forEach((el, elIdx) => {
      const ex = Number(el.x_mm || 0);
      const ey = Number(el.y_mm || 0);
      const ew = Number(el.width_mm || 50);
      const eh = Number(el.height_mm || 12);
      const rot = Number(el.rotation_deg || 0);
      const cx = ex + ew / 2;
      const cy = ey + eh / 2;
      const transform = Math.abs(rot) > 0.01 ? ` transform="rotate(${rot.toFixed(2)} ${cx.toFixed(2)} ${cy.toFixed(2)})"` : "";
      const op = Number(el.opacity ?? 1).toFixed(2);
      const clipId = `eg_el_clip_${page.page_number || 0}_${elIdx}`;
      body += `<defs><clipPath id="${clipId}"><rect x="${ex.toFixed(2)}" y="${ey.toFixed(2)}" width="${ew.toFixed(2)}" height="${eh.toFixed(2)}" /></clipPath></defs>`;
      if (el.type === "image" && el.image_url) {
        body += `<g opacity="${op}"${transform} clip-path="url(#${clipId})"><image href="${escXml(el.image_url)}" x="${ex.toFixed(2)}" y="${ey.toFixed(2)}" width="${ew.toFixed(2)}" height="${eh.toFixed(2)}" preserveAspectRatio="xMidYMid meet" /></g>`;
      } else if (el.type === "shape") {
        const fill = el.bg_color ? getHex(el.bg_color) : "none";
        const stroke = getHex(el.border_color || el.color, "#1E3A5F");
        body += `<g opacity="${op}"${transform}><rect x="${ex.toFixed(2)}" y="${ey.toFixed(2)}" width="${ew.toFixed(2)}" height="${eh.toFixed(2)}" rx="${el.shape_type === "rounded_rect" ? 2.5 : 0}" fill="${fill}" stroke="${stroke}" stroke-width="${Math.max(0.2, ptToMm(el.border_width_pt || 1)).toFixed(2)}" /></g>`;
      } else {
        const txt = el.resolved_text ?? el.text ?? "";
        const col = getHex(el.color, "#1E293B");
        const fsMm = ptToMm(Number(el.font_size_pt || 10));
        const anchor = el.alignment === "left" ? "start" : (el.alignment === "right" ? "end" : "middle");
        const tx = el.alignment === "left" ? ex + 1.5 : (el.alignment === "right" ? ex + ew - 1.5 : cx);
        body += `<g opacity="${op}"${transform} clip-path="url(#${clipId})">`;
        if (el.bg_color) body += `<rect x="${ex.toFixed(2)}" y="${ey.toFixed(2)}" width="${ew.toFixed(2)}" height="${eh.toFixed(2)}" rx="1.5" fill="${getHex(el.bg_color)}" />`;
        body += `<text x="${tx.toFixed(2)}" y="${(cy + fsMm * 0.35).toFixed(2)}" text-anchor="${anchor}" fill="${col}" font-family="${escXml(el.font_family || "Georgia")}" font-weight="${el.bold ? 700 : 400}" font-style="${el.italic ? "italic" : "normal"}" font-size="${fsMm.toFixed(2)}">${escXml(txt)}</text></g>`;
      }
    });
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${trimW} ${trimH}" width="100%" height="100%" style="display:block;">${body}</svg>`;
}
