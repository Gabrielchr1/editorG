/* Catálogo Editorial e Página de Produto — EditorGráfica Atelier */

import {
  api,
  esc,
  money,
  navigate,
  openStoreModal,
  startCustomizationFlow,
  stState,
  stToast,
} from "../core/api.js";
import { icon } from "../core/icons.js";
import { bindProductCardEvents, renderHeaderAuth, renderProductCardHtml } from "../components/header_footer.js";

async function loadCatalogProducts() {
  const f = stState.filters;
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  if (f.category && f.category !== "all") params.set("category", f.category);
  if (f.format_filter) params.set("format_filter", f.format_filter);
  if (f.layout_type) params.set("layout_type", f.layout_type);
  if (f.orientation) params.set("orientation", f.orientation);
  if (f.min_price) params.set("min_price", f.min_price);
  if (f.max_price) params.set("max_price", f.max_price);
  if (f.only_customizable) params.set("only_customizable", "true");
  params.set("sort", f.sort || "relevance");
  params.set("page", String(f.page || 1));
  params.set("page_size", "24");

  stState.catalogData = await api(`/api/store/products?${params.toString()}`);
}

export async function renderCatalogView(main) {
  if (!stState.categories.length) {
    const res = await api("/api/store/categories");
    stState.categories = res.categories || [];
  }
  await loadCatalogProducts();
  const f = stState.filters;
  const data = stState.catalogData;
  const activeCat = stState.categories.find((c) => c.slug === f.category);
  const titleTxt = f.only_customizable
    ? "Edições Personalizáveis"
    : activeCat
      ? activeCat.name
      : "Catálogo Editorial Completo";
  const descTxt = activeCat?.description
    || (f.only_customizable
      ? "Modelos habilitados para personalização de miolos, cores CMYK e marca no estúdio online."
      : "Agendas diárias, permanentes, planners, cadernos e cadernetas de alto padrão prontos ou personalizáveis.");

  main.innerHTML = `
    <section class="st-section-compact">
      <div class="st-container">
        <nav class="st-breadcrumb" aria-label="Caminho">
          <button type="button" id="cat-bc-home">Início</button>
          <span>/</span>
          <span>Catálogo</span>
          ${activeCat ? `<span>/</span><strong>${esc(activeCat.name)}</strong>` : ""}
        </nav>

        <div class="st-section-head">
          <div>
            <h1 class="st-section-title">${esc(titleTxt)}</h1>
            <p class="st-section-desc">${esc(descTxt)} <strong>(${data.total} ${data.total === 1 ? "edição" : "edições"})</strong></p>
          </div>
          <div style="width:230px;max-width:100%;">
            <select id="cat-sort" class="st-select" aria-label="Ordenar catálogo">
              <option value="relevance" ${f.sort === "relevance" ? "selected" : ""}>Ordenar: Relevância</option>
              <option value="bestsellers" ${f.sort === "bestsellers" ? "selected" : ""}>Mais Vendidos</option>
              <option value="newest" ${f.sort === "newest" ? "selected" : ""}>Lançamentos</option>
              <option value="price_asc" ${f.sort === "price_asc" ? "selected" : ""}>Menor Preço</option>
              <option value="price_desc" ${f.sort === "price_desc" ? "selected" : ""}>Maior Preço</option>
            </select>
          </div>
        </div>

        <div class="st-catalog-layout">
          <aside class="st-filter-box">
            <h3>Refinar Seleção</h3>
            <div class="st-filter-group">
              <label class="st-filter-label" for="cat-f-q">Palavra-chave</label>
              <input id="cat-f-q" class="st-input" type="search" value="${esc(f.q)}" placeholder="Nome, SKU ou tema..." />
            </div>
            <div class="st-filter-group">
              <label class="st-filter-label" for="cat-f-cat">Coleção</label>
              <select id="cat-f-cat" class="st-select">
                <option value="all">Todas as coleções</option>
                ${stState.categories.map((c) => `<option value="${esc(c.slug)}" ${f.category === c.slug ? "selected" : ""}>${esc(c.name)}</option>`).join("")}
              </select>
            </div>
            <div class="st-filter-group">
              <label class="st-filter-label" for="cat-f-fmt">Formato</label>
              <select id="cat-f-fmt" class="st-select">
                <option value="">Todos os formatos</option>
                <option value="15 x 21" ${f.format_filter === "15 x 21" ? "selected" : ""}>A5 (15 × 21 cm)</option>
                <option value="14 x 21" ${f.format_filter === "14 x 21" ? "selected" : ""}>Moleskine Clássico (14 × 21 cm)</option>
                <option value="9 x 14" ${f.format_filter === "9 x 14" ? "selected" : ""}>Pocket (9 × 14 cm)</option>
                <option value="19 x 25" ${f.format_filter === "19 x 25" ? "selected" : ""}>Executivo (19 × 25 cm)</option>
              </select>
            </div>
            <div class="st-filter-group">
              <label class="st-filter-label" for="cat-f-layout">Pauta &amp; Miolo</label>
              <select id="cat-f-layout" class="st-select">
                <option value="">Qualquer diagramação</option>
                <option value="horizontal" ${f.layout_type === "horizontal" ? "selected" : ""}>Pautado Horizontal</option>
                <option value="pontilhado" ${f.layout_type === "pontilhado" ? "selected" : ""}>Pontilhado</option>
                <option value="semanal" ${f.layout_type === "semanal" ? "selected" : ""}>Semanal / Planner</option>
                <option value="financeiro" ${f.layout_type === "financeiro" ? "selected" : ""}>Financeiro</option>
              </select>
            </div>
            <div class="st-filter-group">
              <label class="st-filter-label">Faixa de Valor (R$)</label>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <input id="cat-f-min" class="st-input" type="number" min="0" placeholder="Mín" value="${esc(f.min_price)}" />
                <input id="cat-f-max" class="st-input" type="number" min="0" placeholder="Máx" value="${esc(f.max_price)}" />
              </div>
            </div>
            <label style="display:flex;align-items:center;gap:9px;font-size:13px;margin:16px 0;cursor:pointer;">
              <input id="cat-f-custom" type="checkbox" ${f.only_customizable ? "checked" : ""} />
              Somente personalizáveis
            </label>
            <div style="display:grid;grid-template-columns:1fr auto;gap:8px;">
              <button id="cat-btn-apply" class="st-btn st-btn-dark st-btn-sm">Aplicar</button>
              <button id="cat-btn-clear" class="st-btn st-btn-outline st-btn-sm">Limpar</button>
            </div>
          </aside>

          <div>
            <div class="st-products-grid cols-3" id="st-catalog-grid">
              ${(data.products || []).length ? data.products.map(renderProductCardHtml).join("") : `<div class="st-panel-card" style="grid-column:1/-1;">Nenhum modelo corresponde aos filtros selecionados.</div>`}
            </div>
          </div>
        </div>
      </div>
    </section>
  `;

  const applyFilters = () => {
    stState.filters.q = document.getElementById("cat-f-q").value.trim();
    stState.filters.category = document.getElementById("cat-f-cat").value;
    stState.filters.format_filter = document.getElementById("cat-f-fmt").value;
    stState.filters.layout_type = document.getElementById("cat-f-layout").value;
    stState.filters.min_price = document.getElementById("cat-f-min").value;
    stState.filters.max_price = document.getElementById("cat-f-max").value;
    stState.filters.only_customizable = document.getElementById("cat-f-custom").checked;
    stState.filters.sort = document.getElementById("cat-sort").value;
    stState.filters.page = 1;
    renderCatalogView(main);
  };

  main.querySelector("#cat-bc-home")?.addEventListener("click", () => navigate("home"));
  main.querySelector("#cat-btn-apply")?.addEventListener("click", applyFilters);
  main.querySelector("#cat-sort")?.addEventListener("change", applyFilters);
  main.querySelector("#cat-btn-clear")?.addEventListener("click", () => {
    stState.filters = { q: "", category: "all", format_filter: "", layout_type: "", orientation: "", min_price: "", max_price: "", only_customizable: false, sort: "relevance", page: 1 };
    renderCatalogView(main);
  });
  bindProductCardEvents(main);
}

async function refreshProductPriceCalc() {
  const prod = stState.currentProduct;
  if (!prod) return;
  const sel = stState.detailSel;
  try {
    const calc = await api("/api/store/calculate-price", {
      method: "POST",
      body: JSON.stringify({
        product_id: prod.id,
        variation_id: sel.variationId,
        quantity: sel.quantity,
        is_customized: false,
        selected_options: { paper_option: sel.paper, finish_option: sel.finish },
      }),
    });
    sel.priceCalc = calc;
    const unitEl = document.getElementById("pd-live-unit");
    const totEl = document.getElementById("pd-live-total");
    const descEl = document.getElementById("pd-live-breakdown");
    if (unitEl) unitEl.textContent = money(calc.unit_price);
    if (totEl) totEl.textContent = money(calc.total_price);
    if (descEl) {
      const custFee = Number(prod.pricing_rules?.customization_fee || 0);
      descEl.textContent = `${sel.quantity} un. • ${calc.volume_discount_pct ? `Desconto atacado ${calc.volume_discount_pct}% aplicado` : "Valor unitário configurado"}${prod.is_customizable && custFee ? ` • Personalização online (+${money(custFee)}/un.)` : ""}`;
    }
  } catch { /* ignore */ }
}

export async function renderProductDetailView(main, slugOrId) {
  const data = await api(`/api/store/products/${encodeURIComponent(slugOrId)}`);
  const p = data.product;
  stState.currentProduct = p;
  stState.toolLabels = data.tool_labels || {};

  const paperOpts = p.pricing_rules?.paper_options || [];
  const finishOpts = p.pricing_rules?.finish_options || [];
  const volTiers = p.pricing_rules?.volume_discounts || [];
  const imgs = [...(p.images || []), ...(p.mockups || [])]
    .filter((v, i, a) => v && a.indexOf(v) === i)
    .map((u) => (u.includes("/uploads/demo/mockups/") && !u.includes("?") ? `${u}?v=5` : u));
  if (!imgs.length) imgs.push("/uploads/demo/mockups/mockup_agenda.svg?v=5");

  stState.detailSel = {
    variationId: p.variations?.[0]?.id || null,
    paper: paperOpts[0]?.name || "",
    finish: finishOpts[0]?.name || "",
    quantity: 1,
    priceCalc: null,
    activeImgIdx: 0,
  };

  const allowedList = Object.entries(p.allowed_tools || {})
    .filter(([, ok]) => Boolean(ok))
    .map(([k]) => stState.toolLabels[k] || k);

  main.innerHTML = `
    <section class="st-section-compact">
      <div class="st-container">
        <nav class="st-breadcrumb" aria-label="Caminho">
          <button type="button" id="pd-bc-home">Início</button>
          <span>/</span>
          <button type="button" id="pd-bc-cat">${esc(p.category_name || "Catálogo")}</button>
          <span>/</span>
          <strong>${esc(p.name)}</strong>
        </nav>

        <div class="st-detail-grid">
          <div>
            <div class="st-gallery-main" id="pd-gallery-stage" title="Clique para ampliar">
              <img id="pd-main-img" src="${esc(imgs[0])}" alt="${esc(p.name)}" />
              <button type="button" class="st-zoom-pill" id="pd-zoom-btn">
                ${icon("zoom-in", 14)} Ampliar
              </button>
            </div>
            ${imgs.length > 1 ? `
              <div class="st-thumb-row">
                ${imgs.map((src, idx) => `
                  <button type="button" class="st-thumb-btn ${idx === 0 ? "active" : ""}" data-pd-thumb="${idx}">
                    <img src="${esc(src)}" alt="Vista ${idx + 1}" />
                  </button>
                `).join("")}
              </div>
            ` : ""}

            <div class="st-panel-card" style="margin-top:24px;">
              <h3 style="font-family:var(--font-editorial);font-size:21px;margin:0 0 12px;">Especificações Técnicas</h3>
              <table class="st-specs-table">
                <tbody>
                  <tr><td>Dimensões Finais</td><td><strong>${esc(p.specs?.dimensions || "15 × 21 cm (A5)")}</strong></td></tr>
                  <tr><td>Papel &amp; Gramatura</td><td>${esc(p.specs?.paper_type || "Pólen Soft / Offset")} • ${esc(p.specs?.gsm || "90 g/m²")}</td></tr>
                  <tr><td>Quantidade de Páginas</td><td>${esc(p.specs?.page_count || 334)} páginas</td></tr>
                  <tr><td>Padrão Cromático</td><td>${esc(p.specs?.colors_info || "4×4 cores CMYK nativo")}</td></tr>
                  <tr><td>Encadernação</td><td>${esc(p.specs?.binding || "Wire-o / Costura")}</td></tr>
                  <tr><td>Produção Estimada</td><td>${esc(p.specs?.production_days || "3 a 5 dias úteis")}</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <p class="st-eyebrow">${esc(p.category_name)} • SKU ${esc(p.sku)}</p>
            <h1 style="font-family:var(--font-editorial);font-size:clamp(30px,3.2vw,42px);line-height:1.1;margin:0 0 14px;">${esc(p.name)}</h1>
            <p style="font-size:14.5px;color:var(--st-ink-muted);line-height:1.68;margin:0 0 18px;">${esc(p.full_description || p.short_description)}</p>

            <div class="st-price-card">
              <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:12px;">
                <div>
                  <span style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--st-ink-muted);font-weight:600;">Valor Unitário</span>
                  <div id="pd-live-unit" style="font-family:var(--font-editorial);font-size:34px;font-weight:600;color:var(--st-ink);line-height:1.1;">${money(p.effective_price)}</div>
                </div>
                <div style="text-align:right;">
                  <span style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--st-ink-muted);font-weight:600;">Total Estimado</span>
                  <div id="pd-live-total" style="font-size:20px;font-weight:600;color:var(--st-ink);">${money(p.effective_price)}</div>
                </div>
              </div>
              <div id="pd-live-breakdown" style="font-size:12px;color:var(--st-ink-muted);margin-top:8px;">Valores calculados em tempo real no servidor.</div>
            </div>

            ${(p.variations || []).length ? `
              <div class="st-filter-group">
                <label class="st-filter-label" for="pd-var">Formato / Edição do Miolo</label>
                <select id="pd-var" class="st-select">
                  ${p.variations.map((v) => `<option value="${v.id}">${esc(v.name)} — ${esc(v.format_label)} ${v.price_delta ? `(${v.price_delta > 0 ? "+" : ""}${money(v.price_delta)})` : ""}</option>`).join("")}
                </select>
              </div>
            ` : ""}

            ${paperOpts.length ? `
              <div class="st-filter-group">
                <label class="st-filter-label" for="pd-paper">Gramatura do Papel</label>
                <select id="pd-paper" class="st-select">
                  ${paperOpts.map((o) => `<option value="${esc(o.name)}">${esc(o.name)} ${o.price_delta ? `(+${money(o.price_delta)})` : ""}</option>`).join("")}
                </select>
              </div>
            ` : ""}

            ${finishOpts.length ? `
              <div class="st-filter-group">
                <label class="st-filter-label" for="pd-finish">Acabamento &amp; Capa</label>
                <select id="pd-finish" class="st-select">
                  ${finishOpts.map((o) => `<option value="${esc(o.name)}">${esc(o.name)} ${o.price_delta ? `(+${money(o.price_delta)})` : ""}</option>`).join("")}
                </select>
              </div>
            ` : ""}

            <div class="st-filter-group">
              <label class="st-filter-label" for="pd-qty">Quantidade</label>
              <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;">
                <input id="pd-qty" class="st-input" type="number" min="1" max="5000" value="1" style="width:128px;" />
                <div style="font-size:12px;color:var(--st-ink-muted);">
                  ${volTiers.map((t) => `${t.min_qty}+ un: <strong>-${t.discount_pct}%</strong>`).join(" • ")}
                </div>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:10px;margin:24px 0;">
              ${p.is_customizable ? `
                <button id="pd-btn-customize" class="st-btn st-btn-gold st-btn-lg" style="width:100%;">
                  ${icon("sliders", 16)} Personalizar este Modelo no Estúdio
                </button>
              ` : ""}
              <button id="pd-btn-buy-ready" class="st-btn st-btn-dark st-btn-lg" style="width:100%;">
                ${icon("bag", 16)} Comprar Edição Pronta
              </button>
            </div>

            ${p.is_customizable ? `
              <details class="st-faq-item">
                <summary>
                  <span>Ferramentas liberadas no Estúdio (${allowedList.length} recursos)</span>
                  ${icon("chevron-down", 15)}
                </summary>
                <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;">
                  ${allowedList.map((lbl) => `<span class="badge">${esc(lbl)}</span>`).join("")}
                </div>
              </details>
            ` : ""}
          </div>
        </div>
      </div>
    </section>
  `;

  main.querySelector("#pd-bc-home")?.addEventListener("click", () => navigate("home"));
  main.querySelector("#pd-bc-cat")?.addEventListener("click", () => {
    stState.filters.category = p.category_slug || "all";
    navigate("catalog");
  });

  const stageEl = main.querySelector("#pd-gallery-stage");
  const mainImg = main.querySelector("#pd-main-img");
  const openLightbox = () => {
    openStoreModal(`
      <div class="modal" style="max-width:780px;">
        <div class="modal-head">
          <h2>${esc(p.name)}</h2>
          <button class="btn btn-ghost btn-sm btn-icon" data-st-close>${icon("close", 16)}</button>
        </div>
        <div class="modal-body" style="background:var(--st-surface-soft);display:flex;justify-content:center;padding:28px;">
          <img src="${esc(mainImg.src)}" alt="${esc(p.name)}" style="max-height:70vh;width:100%;object-fit:contain;" />
        </div>
      </div>
    `);
  };
  stageEl?.addEventListener("click", openLightbox);
  stageEl?.addEventListener("mousemove", (ev) => {
    if (!stageEl.classList.contains("is-zoomed")) return;
    const rect = stageEl.getBoundingClientRect();
    const x = ((ev.clientX - rect.left) / rect.width) * 100;
    const y = ((ev.clientY - rect.top) / rect.height) * 100;
    mainImg.style.transformOrigin = `${x}% ${y}%`;
  });

  main.querySelectorAll("[data-pd-thumb]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.pdThumb);
      if (mainImg && imgs[idx]) mainImg.src = imgs[idx];
      main.querySelectorAll(".st-thumb-btn").forEach((b) => b.classList.toggle("active", b === btn));
    });
  });

  const syncSelections = () => {
    const vEl = document.getElementById("pd-var");
    const pEl = document.getElementById("pd-paper");
    const fEl = document.getElementById("pd-finish");
    const qEl = document.getElementById("pd-qty");
    if (vEl) stState.detailSel.variationId = Number(vEl.value) || null;
    if (pEl) stState.detailSel.paper = pEl.value;
    if (fEl) stState.detailSel.finish = fEl.value;
    if (qEl) stState.detailSel.quantity = Math.max(1, parseInt(qEl.value || "1", 10) || 1);
    refreshProductPriceCalc();
  };

  ["pd-var", "pd-paper", "pd-finish", "pd-qty"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", syncSelections);
  });
  document.getElementById("pd-qty")?.addEventListener("input", syncSelections);

  main.querySelector("#pd-btn-buy-ready")?.addEventListener("click", async () => {
    try {
      const res = await api("/api/cart/items", {
        method: "POST",
        body: JSON.stringify({
          product_id: p.id,
          variation_id: stState.detailSel.variationId,
          is_customized: false,
          selected_options: { paper_option: stState.detailSel.paper, finish_option: stState.detailSel.finish },
          quantity: stState.detailSel.quantity,
        }),
      });
      stState.cart = res;
      renderHeaderAuth();
      stToast("Adicionado à sacola.", "success");
      navigate("cart");
    } catch (err) {
      stToast(err.message, "error");
    }
  });

  main.querySelector("#pd-btn-customize")?.addEventListener("click", async () => {
    await startCustomizationFlow(p.id, {
      variationId: stState.detailSel.variationId,
      selectedOptions: { paper_option: stState.detailSel.paper, finish_option: stState.detailSel.finish },
    });
  });

  await refreshProductPriceCalc();
}
