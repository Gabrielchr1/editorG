// Editor Visual Interativo em escala milimétrica real (Zoom, Réguas, Guias, Drag, Resize e Rotação)

import { cmykToHex, escXml, getTrimDimsMm, renderPageSVG } from "./calendar_client.js";

const BASE_PX_PER_MM = 3.2;

export function getPxPerMm(zoomPct = 100) {
  return BASE_PX_PER_MM * (Number(zoomPct) / 100);
}

function rotatedBoundsMm(el) {
  const x = Number(el.x_mm || 0);
  const y = Number(el.y_mm || 0);
  const w = Number(el.width_mm || 10);
  const h = Number(el.height_mm || 10);
  const rad = ((Number(el.rotation_deg || 0)) * Math.PI) / 180;
  const cx = x + w / 2;
  const cy = y + h / 2;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const hw = w / 2;
  const hh = h / 2;
  const corners = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]];
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  corners.forEach(([dx, dy]) => {
    const rx = cx + dx * cos - dy * sin;
    const ry = cy + dx * sin + dy * cos;
    if (rx < minX) minX = rx;
    if (ry < minY) minY = ry;
    if (rx > maxX) maxX = rx;
    if (ry > maxY) maxY = ry;
  });
  return { minX, minY, maxX, maxY };
}

export function isElementOutOfSafety(el, config) {
  const { w: trimW, h: trimH } = getTrimDimsMm(config);
  const safety = Number(config.page_setup?.safety_margin_mm ?? 5);
  const b = rotatedBoundsMm(el);
  return b.minX < safety || b.minY < safety || b.maxX > trimW - safety || b.maxY > trimH - safety;
}

function buildRulerTicks(lengthMm, pxPerMm, bleedPx, isHorizontal) {
  let html = "";
  const step = 5;
  for (let m = 0; m <= lengthMm; m += step) {
    const pos = (bleedPx + m * pxPerMm).toFixed(1);
    const isMajor = m % 10 === 0;
    if (isHorizontal) {
      html += `<div class="ruler-tick" style="left:${pos}px;bottom:0;width:1px;height:${isMajor ? 10 : 5}px;"></div>`;
      if (isMajor && m < lengthMm - 3) {
        html += `<span class="ruler-label" style="left:${Number(pos) + 3}px;top:3px;">${m}</span>`;
      }
    } else {
      html += `<div class="ruler-tick" style="top:${pos}px;right:0;height:1px;width:${isMajor ? 10 : 5}px;"></div>`;
      if (isMajor && m < lengthMm - 3) {
        html += `<span class="ruler-label" style="top:${Number(pos) + 2}px;left:2px;">${m}</span>`;
      }
    }
  }
  return html;
}

export class CanvasEditorController {
  constructor({
    stageEl,
    onSelectElement,
    onElementDragStart,
    onElementMutate,
    onElementCommit,
    onDoubleClickText,
  }) {
    this.stageEl = stageEl;
    this.onSelectElement = onSelectElement;
    this.onElementDragStart = onElementDragStart;
    this.onElementMutate = onElementMutate;
    this.onElementCommit = onElementCommit;
    this.onDoubleClickText = onDoubleClickText;
    this.dragState = null;

    this._onPointerMove = this._onPointerMove.bind(this);
    this._onPointerUp = this._onPointerUp.bind(this);
    window.addEventListener("pointermove", this._onPointerMove);
    window.addEventListener("pointerup", this._onPointerUp);
  }

  destroy() {
    window.removeEventListener("pointermove", this._onPointerMove);
    window.removeEventListener("pointerup", this._onPointerUp);
  }

  render({ config, pages, currentIndex, zoomPct, showRulers, spreadMode, selectedId, permissions = null }) {
    if (!pages || !pages.length) {
      this.stageEl.innerHTML = `<div class="badge badge-warning">Nenhuma página gerada. Verifique as datas.</div>`;
      return;
    }

    this.config = config;
    this.zoomPct = zoomPct;
    this.pxPerMm = getPxPerMm(zoomPct);
    this.selectedId = selectedId;
    this.permissions = permissions;

    const page = pages[currentIndex] || pages[0];
    const pagesToRender = [];
    if (spreadMode && currentIndex + 1 < pages.length) {
      pagesToRender.push(page, pages[currentIndex + 1]);
    } else {
      pagesToRender.push(page);
    }

    this.stageEl.innerHTML = "";
    pagesToRender.forEach((pg, idx) => {
      const box = this._buildSinglePageStage(pg, config, showRulers, idx === 0);
      this.stageEl.appendChild(box);
    });
  }

  _buildSinglePageStage(page, config, showRulers, interactive) {
    const ps = config.page_setup || {};
    const { w: trimW, h: trimH } = getTrimDimsMm(config);
    const pxMm = this.pxPerMm;
    const bleed = ps.show_bleed_guide ? Number(ps.bleed_mm ?? 3) : 0;
    const safety = Number(ps.safety_margin_mm ?? 5);
    const m = page.effective_margins || { left: 18, right: 10, top: 12, bottom: 12 };

    const trimWpx = trimW * pxMm;
    const trimHpx = trimH * pxMm;
    const bleedPx = bleed * pxMm;

    const wrapper = document.createElement("div");
    wrapper.className = showRulers ? "page-ruler-box" : "page-plain-box";
    wrapper.style.position = "relative";

    if (showRulers) {
      const corner = document.createElement("div");
      corner.className = "ruler-corner";
      corner.textContent = "mm";
      wrapper.appendChild(corner);

      const rulerH = document.createElement("div");
      rulerH.className = "ruler-h";
      rulerH.style.width = `${trimWpx + 2 * bleedPx}px`;
      rulerH.style.left = "22px";
      rulerH.innerHTML = buildRulerTicks(trimW, pxMm, bleedPx, true);
      wrapper.appendChild(rulerH);

      const rulerV = document.createElement("div");
      rulerV.className = "ruler-v";
      rulerV.style.height = `${trimHpx + 2 * bleedPx}px`;
      rulerV.style.top = "22px";
      rulerV.innerHTML = buildRulerTicks(trimH, pxMm, bleedPx, false);
      wrapper.appendChild(rulerV);
    }

    const bleedFrame = document.createElement("div");
    bleedFrame.className = "paper-bleed-frame";
    bleedFrame.style.padding = `${bleedPx}px`;
    const bgHex = config.colors?.background_color?.hex || "#FFFFFF";
    bleedFrame.style.background = bgHex;

    if (bleed > 0) {
      const bleedGuide = document.createElement("div");
      bleedGuide.className = "guide-overlay guide-bleed";
      bleedGuide.style.inset = "0";
      bleedFrame.appendChild(bleedGuide);
    }

    const trimArea = document.createElement("div");
    trimArea.className = "paper-trim-area";
    trimArea.style.width = `${trimWpx}px`;
    trimArea.style.height = `${trimHpx}px`;

    // Camada SVG vetorial do miolo
    const svgLayer = document.createElement("div");
    svgLayer.className = "page-svg-layer";
    svgLayer.innerHTML = renderPageSVG(page, config, { includeElementsInSvg: false });
    trimArea.appendChild(svgLayer);

    // Grade auxiliar
    if (ps.show_grid) {
      const gPx = Math.max(2, Number(ps.grid_size_mm || 5) * pxMm);
      const gridDiv = document.createElement("div");
      gridDiv.className = "guide-overlay";
      gridDiv.style.inset = "0";
      gridDiv.style.backgroundImage = `linear-gradient(to right, rgba(59,130,246,0.14) 1px, transparent 1px), linear-gradient(to bottom, rgba(59,130,246,0.14) 1px, transparent 1px)`;
      gridDiv.style.backgroundSize = `${gPx}px ${gPx}px`;
      trimArea.appendChild(gridDiv);
    }

    // Linha de corte (Trim)
    const trimGuide = document.createElement("div");
    trimGuide.className = "guide-overlay guide-trim";
    trimGuide.style.inset = "0";
    trimArea.appendChild(trimGuide);

    // Área de segurança
    if (ps.show_safety_guide && safety > 0) {
      const sGuide = document.createElement("div");
      sGuide.className = "guide-overlay guide-safety";
      sGuide.style.left = `${safety * pxMm}px`;
      sGuide.style.top = `${safety * pxMm}px`;
      sGuide.style.right = `${safety * pxMm}px`;
      sGuide.style.bottom = `${safety * pxMm}px`;
      trimArea.appendChild(sGuide);
    }

    // Margens e Gutter de encadernação
    if (ps.show_margin_guide) {
      const mGuide = document.createElement("div");
      mGuide.className = "guide-overlay guide-margin";
      mGuide.style.left = `${m.left * pxMm}px`;
      mGuide.style.top = `${m.top * pxMm}px`;
      mGuide.style.right = `${m.right * pxMm}px`;
      mGuide.style.bottom = `${m.bottom * pxMm}px`;
      trimArea.appendChild(mGuide);

      const gutter = document.createElement("div");
      const isRightGutter = ps.mirror_margins && page.is_even;
      gutter.className = `guide-overlay ${isRightGutter ? "guide-gutter-right" : "guide-gutter"}`;
      gutter.style.top = "0";
      gutter.style.bottom = "0";
      gutter.style.width = `${(isRightGutter ? m.right : m.left) * pxMm}px`;
      if (isRightGutter) gutter.style.right = "0";
      else gutter.style.left = "0";
      trimArea.appendChild(gutter);
    }

    // Snap lines (visíveis durante arraste)
    const snapH = document.createElement("div");
    snapH.className = "snap-line-h hidden";
    const snapV = document.createElement("div");
    snapV.className = "snap-line-v hidden";
    trimArea.appendChild(snapH);
    trimArea.appendChild(snapV);

    // Camada de Elementos Interativos (Frases, Imagens, Formas)
    const elLayer = document.createElement("div");
    elLayer.className = "elements-layer";

    if (interactive) {
      elLayer.addEventListener("pointerdown", (ev) => {
        if (ev.target === elLayer) {
          this.onSelectElement(null);
        }
      });
    }

    (page.active_elements || []).forEach((el) => {
      const dom = this._createElementDom(el, config, pxMm, interactive, trimArea, snapH, snapV);
      elLayer.appendChild(dom);
    });

    trimArea.appendChild(elLayer);
    bleedFrame.appendChild(trimArea);
    wrapper.appendChild(bleedFrame);

    // Legenda da página abaixo
    const cap = document.createElement("div");
    cap.className = "page-stage-caption";
    cap.textContent = `Página ${page.page_number} (${page.is_even ? "Par / Verso" : "Ímpar / Frente"}) — ${page.title}`;
    wrapper.appendChild(cap);

    return wrapper;
  }

  _createElementDom(el, config, pxMm, interactive, trimArea, snapH, snapV) {
    const div = document.createElement("div");
    const isSelected = interactive && el.id === this.selectedId;
    const outSafety = isElementOutOfSafety(el, config);

    div.className = "canvas-el" + (isSelected ? " selected" : "") + (outSafety ? " out-of-safety" : "");
    div.dataset.elId = el.id;
    div.style.left = `${Number(el.x_mm || 0) * pxMm}px`;
    div.style.top = `${Number(el.y_mm || 0) * pxMm}px`;
    div.style.width = `${Number(el.width_mm || 40) * pxMm}px`;
    div.style.height = `${Number(el.height_mm || 12) * pxMm}px`;
    div.style.opacity = String(el.opacity ?? 1);
    div.style.zIndex = String(el.z_index ?? 10);
    div.style.transform = `rotate(${Number(el.rotation_deg || 0)}deg)`;

    if (el.bg_color) {
      div.style.background = el.bg_color.hex || cmykToHex(el.bg_color.c, el.bg_color.m, el.bg_color.y, el.bg_color.k);
    }
    if (Number(el.border_width_pt || 0) > 0) {
      const bCol = el.border_color || el.color;
      div.style.border = `${Math.max(1, (el.border_width_pt * 0.3528) * pxMm)}px solid ${bCol?.hex || "#1E3A5F"}`;
    }

    const contentBox = document.createElement("div");
    contentBox.className = "canvas-el-content";

    if (el.type === "image" && el.image_url) {
      const img = document.createElement("img");
      img.src = el.image_url;
      img.alt = el.label || "Imagem";
      contentBox.appendChild(img);
    } else if (el.type === "shape") {
      if (el.shape_type === "circle") div.style.borderRadius = "50%";
      else if (el.shape_type === "rounded_rect") div.style.borderRadius = `${2.5 * pxMm}px`;
      else if (el.shape_type === "line" || el.shape_type === "divider") {
        const lineBar = document.createElement("div");
        lineBar.style.width = "100%";
        lineBar.style.height = `${Math.max(1.5, (el.border_width_pt || 1) * 0.3528 * pxMm)}px`;
        lineBar.style.background = el.color?.hex || "#1E3A5F";
        contentBox.appendChild(lineBar);
      }
    } else {
      const span = document.createElement("div");
      span.className = "canvas-el-text";
      span.textContent = el.resolved_text ?? el.text ?? "";
      span.style.fontFamily = el.font_family || "Georgia";
      span.style.fontSize = `${Number(el.font_size_pt || 10) * 0.352778 * pxMm}px`;
      span.style.fontWeight = el.bold ? "700" : "400";
      span.style.fontStyle = el.italic ? "italic" : "normal";
      span.style.textDecoration = el.underline ? "underline" : "none";
      span.style.textAlign = el.alignment || "center";
      span.style.color = el.color?.hex || cmykToHex(el.color?.c, el.color?.m, el.color?.y, el.color?.k);
      contentBox.appendChild(span);
    }
    div.appendChild(contentBox);

    if (!interactive) return div;

    const p = this.permissions;
    const canMove = !p || Boolean(p.move_elements);
    const canResize = !p || Boolean(p.resize_elements);
    const canRotate = !p || Boolean(p.rotate_elements);
    if (!canMove) div.style.cursor = "pointer";

    div.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      this.onSelectElement(el.id);
      if (el.locked) return;
      const target = ev.target;
      if (target.classList.contains("resize-handle")) {
        if (!canResize) return;
        if (this.onElementDragStart) this.onElementDragStart();
        this._startResize(ev, el, target.dataset.dir, div, trimArea);
      } else if (target.classList.contains("rotate-handle")) {
        if (!canRotate) return;
        if (this.onElementDragStart) this.onElementDragStart();
        this._startRotate(ev, el, div);
      } else if (canMove) {
        if (this.onElementDragStart) this.onElementDragStart();
        this._startMove(ev, el, div, trimArea, snapH, snapV);
      }
    });

    div.addEventListener("dblclick", (ev) => {
      ev.stopPropagation();
      if (el.type === "phrase" && this.onDoubleClickText) {
        this.onDoubleClickText(el.id);
      }
    });

    if (isSelected && !el.locked) {
      if (canResize) {
        ["nw", "n", "ne", "e", "se", "s", "sw", "w"].forEach((dir) => {
          const h = document.createElement("div");
          h.className = `resize-handle rh-${dir}`;
          h.dataset.dir = dir;
          div.appendChild(h);
        });
      }
      if (canRotate) {
        const rotH = document.createElement("div");
        rotH.className = "rotate-handle";
        rotH.title = "Arraste para girar o elemento";
        div.appendChild(rotH);
      }
    }

    return div;
  }

  _startMove(ev, el, dom, trimArea, snapH, snapV) {
    this.dragState = {
      mode: "move",
      elId: el.id,
      startX: ev.clientX,
      startY: ev.clientY,
      origX: Number(el.x_mm),
      origY: Number(el.y_mm),
      w: Number(el.width_mm),
      h: Number(el.height_mm),
      dom,
      trimArea,
      snapH,
      snapV,
      moved: false,
    };
  }

  _startResize(ev, el, dir, dom, trimArea) {
    this.dragState = {
      mode: "resize",
      dir,
      elId: el.id,
      startX: ev.clientX,
      startY: ev.clientY,
      origX: Number(el.x_mm),
      origY: Number(el.y_mm),
      origW: Number(el.width_mm),
      origH: Number(el.height_mm),
      dom,
      trimArea,
      moved: false,
    };
  }

  _startRotate(ev, el, dom) {
    const rect = dom.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    this.dragState = {
      mode: "rotate",
      elId: el.id,
      cx,
      cy,
      dom,
      moved: false,
    };
  }

  _onPointerMove(ev) {
    if (!this.dragState) return;
    const st = this.dragState;
    const pxMm = this.pxPerMm;
    const { w: trimW, h: trimH } = getTrimDimsMm(this.config);

    if (st.mode === "move") {
      const dxMm = (ev.clientX - st.startX) / pxMm;
      const dyMm = (ev.clientY - st.startY) / pxMm;
      if (Math.abs(dxMm) > 0.2 || Math.abs(dyMm) > 0.2) st.moved = true;

      let nx = st.origX + dxMm;
      let ny = st.origY + dyMm;

      // Mantém dentro dos limites físicos da página
      nx = Math.max(0, Math.min(trimW - st.w, nx));
      ny = Math.max(0, Math.min(trimH - st.h, ny));

      // Guias magnéticas de centro
      const centerX = trimW / 2;
      const centerY = trimH / 2;
      const elCx = nx + st.w / 2;
      const elCy = ny + st.h / 2;
      let showV = false, showH = false;
      if (Math.abs(elCx - centerX) < 1.8) {
        nx = centerX - st.w / 2;
        showV = true;
      }
      if (Math.abs(elCy - centerY) < 1.8) {
        ny = centerY - st.h / 2;
        showH = true;
      }

      st.snapV.classList.toggle("hidden", !showV);
      if (showV) st.snapV.style.left = `${centerX * pxMm}px`;
      st.snapH.classList.toggle("hidden", !showH);
      if (showH) st.snapH.style.top = `${centerY * pxMm}px`;

      nx = Number(nx.toFixed(1));
      ny = Number(ny.toFixed(1));
      st.dom.style.left = `${nx * pxMm}px`;
      st.dom.style.top = `${ny * pxMm}px`;
      this.onElementMutate(st.elId, { x_mm: nx, y_mm: ny }, false);
    } else if (st.mode === "resize") {
      const dxMm = (ev.clientX - st.startX) / pxMm;
      const dyMm = (ev.clientY - st.startY) / pxMm;
      st.moved = true;
      let x = st.origX, y = st.origY, w = st.origW, h = st.origH;
      const d = st.dir;
      if (d.includes("e")) w = Math.max(6, st.origW + dxMm);
      if (d.includes("s")) h = Math.max(4, st.origH + dyMm);
      if (d.includes("w")) {
        const nw = Math.max(6, st.origW - dxMm);
        x = st.origX + (st.origW - nw);
        w = nw;
      }
      if (d.includes("n")) {
        const nh = Math.max(4, st.origH - dyMm);
        y = st.origY + (st.origH - nh);
        h = nh;
      }
      x = Number(Math.max(0, x).toFixed(1));
      y = Number(Math.max(0, y).toFixed(1));
      w = Number(Math.min(trimW - x, w).toFixed(1));
      h = Number(Math.min(trimH - y, h).toFixed(1));
      st.dom.style.left = `${x * pxMm}px`;
      st.dom.style.top = `${y * pxMm}px`;
      st.dom.style.width = `${w * pxMm}px`;
      st.dom.style.height = `${h * pxMm}px`;
      this.onElementMutate(st.elId, { x_mm: x, y_mm: y, width_mm: w, height_mm: h }, false);
    } else if (st.mode === "rotate") {
      st.moved = true;
      const angRad = Math.atan2(ev.clientY - st.cy, ev.clientX - st.cx);
      let deg = (angRad * 180) / Math.PI + 90;
      if (ev.shiftKey) deg = Math.round(deg / 15) * 15;
      if (deg > 180) deg -= 360;
      deg = Number(deg.toFixed(1));
      st.dom.style.transform = `rotate(${deg}deg)`;
      this.onElementMutate(st.elId, { rotation_deg: deg }, false);
    }
  }

  _onPointerUp() {
    if (!this.dragState) return;
    const st = this.dragState;
    if (st.snapH) st.snapH.classList.add("hidden");
    if (st.snapV) st.snapV.classList.add("hidden");
    this.dragState = null;
    if (st.moved) {
      this.onElementCommit();
    }
  }
}
