/* Componentes reutilizáveis da Loja: Header, Menu Mobile, Footer Editorial e Card de Produto */

import {
  api,
  esc,
  money,
  navigate,
  openStoreModal,
  startCustomizationFlow,
  stState,
  stToast,
  triggerAuthModal,
} from "../core/api.js";
import { icon } from "../core/icons.js";

export function renderHeaderAuth() {
  const itemCount = Number(stState.cart?.item_count || 0);
  const badge = document.getElementById("st-cart-badge");
  if (badge) badge.textContent = String(itemCount);

  const mobBadge = document.getElementById("st-mob-cart-badge");
  if (mobBadge) {
    mobBadge.textContent = String(itemCount);
    mobBadge.classList.toggle("hidden", itemCount === 0);
  }

  const favBadge = document.getElementById("st-fav-badge");
  if (favBadge) {
    const cnt = stState.favoritesSet?.size || 0;
    favBadge.textContent = String(cnt);
    favBadge.classList.toggle("hidden", cnt === 0);
  }

  const accLbl = document.getElementById("st-btn-account-lbl");
  if (accLbl) {
    if (stState.user) {
      accLbl.textContent = (stState.user.name || "Conta").split(" ")[0];
    } else {
      accLbl.textContent = "Entrar";
    }
  }

  const isStaff = Boolean(stState.user?.is_staff);
  document.getElementById("st-nav-studio")?.classList.toggle("hidden", !isStaff);
  document.getElementById("st-nav-admin")?.classList.toggle("hidden", !isStaff);

  const id = stState.homeData?.store_identity;
  if (id) {
    const tEl = document.getElementById("st-brand-title");
    if (tEl && id.store_name) tEl.textContent = id.store_name;
  }

  document.querySelectorAll("#st-main-nav .st-nav-link").forEach((b) => {
    const r = b.dataset.stRoute;
    const cat = b.dataset.stCat;
    let active = false;
    if (r === "home" && stState.route === "home") active = true;
    else if (r === "catalog" && stState.route === "catalog" && (!stState.filters.category || stState.filters.category === "all")) active = true;
    else if (r && r !== "catalog" && r === stState.route) active = true;
    if (cat && stState.route === "catalog" && stState.filters.category === cat) active = true;
    b.classList.toggle("active", active);
  });

  document.querySelectorAll("#st-mobile-tabbar [data-mobtab]").forEach((btn) => {
    const t = btn.dataset.mobtab;
    let isActive = false;
    if (t === "home" && stState.route === "home") isActive = true;
    else if (t === "catalog" && stState.route === "catalog" && !stState.filters.only_customizable) isActive = true;
    else if (t === "customizable" && stState.route === "catalog" && stState.filters.only_customizable) isActive = true;
    else if (t === "cart" && (stState.route === "cart" || stState.route === "checkout")) isActive = true;
    else if (t === "account" && (stState.route === "account" || stState.route === "admin")) isActive = true;
    btn.classList.toggle("active", isActive);
  });
}

export function openMobileDrawer() {
  const existing = document.getElementById("st-mobile-drawer");
  if (existing) existing.remove();

  const isStaff = Boolean(stState.user?.is_staff);
  const drawer = document.createElement("div");
  drawer.id = "st-mobile-drawer";
  drawer.className = "st-mobile-drawer";
  drawer.innerHTML = `
    <div class="st-mobile-drawer-panel">
      <div style="display:flex;align-items:center;justify-content:space-between;padding-bottom:12px;border-bottom:1px solid var(--st-border);">
        <strong style="font-family:var(--font-editorial);font-size:22px;">Menu Atelier</strong>
        <button class="st-icon-btn" id="mob-close" aria-label="Fechar menu">${icon("close", 18)}</button>
      </div>
      <div style="position:relative;display:flex;align-items:center;width:100%;">
        <span style="position:absolute;left:12px;color:var(--st-ink-muted);pointer-events:none;display:inline-flex;">${icon("search", 15)}</span>
        <input id="mob-search" class="st-input" style="padding-left:36px;" type="search" placeholder="Buscar modelos e temas..." value="${esc(stState.filters.q)}" />
      </div>
      <div style="display:flex;flex-direction:column;gap:4px;margin-top:6px;">
        <button class="st-side-btn" data-mob-route="home">Início</button>
        <button class="st-side-btn" data-mob-route="catalog">Catálogo Completo</button>
        <button class="st-side-btn" data-mob-cat="agendas-diarias">Agendas</button>
        <button class="st-side-btn" data-mob-cat="planners">Planners</button>
        <button class="st-side-btn" data-mob-cat="cadernetas">Cadernetas Moleskine</button>
        <button class="st-side-btn" data-mob-cat="cadernos">Cadernos Personalizados</button>
        <button class="st-side-btn" data-mob-custom="1">Produtos Personalizáveis</button>
        ${isStaff ? `<button class="st-side-btn" id="mob-studio">Editor Studio Interno</button>` : ""}
        ${isStaff ? `<button class="st-side-btn" data-mob-route="admin">Painel Administrativo</button>` : ""}
      </div>
      <div style="margin-top:auto;padding-top:16px;border-top:1px solid var(--st-border);display:flex;flex-direction:column;gap:8px;">
        <button class="st-btn st-btn-outline st-btn-sm" id="mob-theme">Alternar Tema Claro / Escuro</button>
        <button class="st-btn st-btn-dark st-btn-sm" id="mob-account">${stState.user ? "Minha Conta" : "Entrar / Cadastrar"}</button>
      </div>
    </div>
  `;
  document.body.appendChild(drawer);

  const close = () => drawer.remove();
  drawer.addEventListener("click", (ev) => {
    if (ev.target === drawer || ev.target.closest("#mob-close")) close();
  });
  drawer.querySelector("#mob-search")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      stState.filters.q = ev.target.value.trim();
      close();
      navigate("catalog");
    }
  });
  drawer.querySelectorAll("[data-mob-route]").forEach((b) => {
    b.addEventListener("click", () => {
      close();
      navigate(b.dataset.mobRoute);
    });
  });
  drawer.querySelectorAll("[data-mob-cat]").forEach((b) => {
    b.addEventListener("click", () => {
      stState.filters.category = b.dataset.mobCat;
      stState.filters.only_customizable = false;
      close();
      navigate("catalog");
    });
  });
  drawer.querySelector("[data-mob-custom]")?.addEventListener("click", () => {
    stState.filters.category = "all";
    stState.filters.only_customizable = true;
    close();
    navigate("catalog");
  });
  drawer.querySelector("#mob-studio")?.addEventListener("click", () => {
    close();
    window.EGEditor?.openStudioDashboard();
  });
  drawer.querySelector("#mob-theme")?.addEventListener("click", () => {
    window.EGEditor?.toggleTheme();
  });
  drawer.querySelector("#mob-account")?.addEventListener("click", () => {
    close();
    if (stState.user) navigate("account");
    else triggerAuthModal("login");
  });
}

export function renderFooter() {
  const footer = document.getElementById("store-footer");
  if (!footer) return;
  const id = stState.homeData?.store_identity || {};
  const pol = stState.homeData?.policies || {};
  footer.innerHTML = `
    <div class="st-container">
      <div class="st-footer-grid">
        <div>
          <h4>${esc(id.store_name || "EditorGráfica Atelier")}</h4>
          <p>${esc(id.tagline || "Papelaria Fina, Agendas Sob Medida & Impressão CMYK")}</p>
          <p style="margin-top:10px;">Prazo padrão de produção: ${esc(id.production_lead_time || "3 a 5 dias úteis")}</p>
          <p>${esc(id.address || "Atendimento nacional para clientes e empresas")}</p>
        </div>
        <div>
          <h4>Coleções</h4>
          <button class="st-footer-link" data-ft-cat="agendas-diarias">Agendas Personalizadas</button>
          <button class="st-footer-link" data-ft-cat="planners">Planners Editoriais</button>
          <button class="st-footer-link" data-ft-cat="cadernetas">Cadernetas Estilo Moleskine</button>
          <button class="st-footer-link" data-ft-cat="cadernos">Cadernos &amp; Blocos</button>
          <button class="st-footer-link" data-ft-route="catalog">Catálogo Completo</button>
        </div>
        <div>
          <h4>Institucional</h4>
          <button class="st-footer-link" data-ft-custom="1">Estúdio de Personalização</button>
          <button class="st-footer-link" id="st-ft-terms">Termos de Produção CMYK</button>
          <button class="st-footer-link" id="st-ft-privacy">Privacidade &amp; LGPD</button>
          <button class="st-footer-link" id="st-ft-account">Área do Cliente</button>
        </div>
        <div>
          <h4>Atendimento</h4>
          <p>${esc(id.contact_email || "contato@editorgrafica.com.br")}</p>
          <p>${esc(id.whatsapp || id.contact_phone || "")}</p>
          <p style="margin-top:8px;">Segunda a Sexta, 09h às 18h</p>
        </div>
      </div>

      <div class="st-footer-bottom">
        <span>© ${new Date().getFullYear()} ${esc(id.store_name || "EditorGráfica Atelier")}. Todos os direitos reservados.</span>
        <span>Arquivos vetoriais em CMYK • Pix &amp; Mercado Pago</span>
      </div>
    </div>
  `;

  footer.querySelectorAll("[data-ft-cat]").forEach((a) => {
    a.addEventListener("click", () => {
      stState.filters.category = a.dataset.ftCat;
      stState.filters.only_customizable = false;
      navigate("catalog");
    });
  });
  footer.querySelectorAll("[data-ft-route]").forEach((a) => {
    a.addEventListener("click", () => navigate(a.dataset.ftRoute));
  });
  footer.querySelectorAll("[data-ft-custom]").forEach((a) => {
    a.addEventListener("click", () => {
      stState.filters.category = "all";
      stState.filters.only_customizable = true;
      navigate("catalog");
    });
  });
  footer.querySelector("#st-ft-account")?.addEventListener("click", () => {
    if (stState.user) navigate("account");
    else triggerAuthModal("login");
  });
  footer.querySelector("#st-ft-terms")?.addEventListener("click", () => {
    openStoreModal(`
      <div class="modal" style="max-width:620px;">
        <div class="modal-head"><h2>Termos de Produção Gráfica</h2><button class="btn btn-ghost btn-sm btn-icon" data-st-close>${icon("close", 16)}</button></div>
        <div class="modal-body"><p style="line-height:1.7;">${esc(pol.terms || "Os produtos personalizados são produzidos após prévia digital em CMYK e aprovação formal do cliente.")}</p></div>
      </div>
    `);
  });
  footer.querySelector("#st-ft-privacy")?.addEventListener("click", () => {
    openStoreModal(`
      <div class="modal" style="max-width:620px;">
        <div class="modal-head"><h2>Privacidade &amp; LGPD</h2><button class="btn btn-ghost btn-sm btn-icon" data-st-close>${icon("close", 16)}</button></div>
        <div class="modal-body"><p style="line-height:1.7;">${esc(pol.privacy || "Seus dados pessoais, projetos e arquivos são isolados por conta conforme a LGPD, com exportação e anonimização disponíveis na Área do Cliente.")}</p></div>
      </div>
    `);
  });
}

export function renderProductCardHtml(p) {
  const rawThumb = (p.images && p.images[0]) || (p.mockups && p.mockups[0]) || "/uploads/demo/mockups/mockup_agenda.svg";
  const thumb = rawThumb.includes("/uploads/demo/mockups/") && !rawThumb.includes("?") ? `${rawThumb}?v=5` : rawThumb;
  const isFav = stState.favoritesSet.has(p.id);
  const tagMap = { bestseller: "Mais Vendido", new: "Lançamento", launch: "Novidade", promo: "Edição Especial" };
  const tagTxt = p.commercial_tag ? (tagMap[p.commercial_tag] || p.commercial_tag) : "";
  const hasPromo = p.promo_price && Number(p.promo_price) < Number(p.base_price);

  return `
    <article class="st-product-card" data-prod-slug="${esc(p.slug)}">
      <div class="st-product-thumb">
        ${tagTxt ? `<span class="st-tag-float st-tag-gold">${esc(tagTxt)}</span>` : ""}
        <button class="st-fav-float ${isFav ? "is-fav" : ""}" data-fav-id="${p.id}" aria-label="Favoritar produto" title="Favoritar">
          ${icon(isFav ? "heart-filled" : "heart", 15)}
        </button>
        <img src="${esc(thumb)}" alt="${esc(p.name)}" loading="lazy" />
      </div>
      <div class="st-product-body">
        <div class="st-product-cat">${esc(p.category_name || "Papelaria")}${p.is_customizable ? " • Personalizável" : " • Pronto"}</div>
        <h3 class="st-product-title">${esc(p.name)}</h3>
        <p class="st-product-desc">${esc(p.short_description)}</p>
        <div class="st-product-footer">
          <div class="st-product-price-row">
            <div class="st-price-group">
              ${hasPromo ? `<span class="st-price-old">${money(p.base_price)}</span>` : ""}
              <span class="st-price">${money(p.effective_price)}</span>
            </div>
            <span class="st-prod-kind-tag">${p.is_customizable ? "Sob medida" : "Pronta entrega"}</span>
          </div>
          <div class="st-product-actions ${p.is_customizable ? "two-btns" : "one-btn"}">
            <button class="st-btn st-btn-outline st-btn-xs" data-open-prod="${esc(p.slug)}">Detalhes</button>
            ${p.is_customizable ? `<button class="st-btn st-btn-gold st-btn-xs" data-quick-custom="${p.id}">Personalizar</button>` : ""}
          </div>
        </div>
      </div>
    </article>
  `;
}

export function bindProductCardEvents(container) {
  container.querySelectorAll("[data-fav-id]").forEach((btn) => {
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      const pid = Number(btn.dataset.favId);
      if (!stState.user) {
        triggerAuthModal("login");
        return;
      }
      const res = await api(`/api/account/favorites/${pid}`, { method: "POST" });
      if (res.favorited) stState.favoritesSet.add(pid);
      else stState.favoritesSet.delete(pid);
      btn.classList.toggle("is-fav", Boolean(res.favorited));
      btn.innerHTML = icon(res.favorited ? "heart-filled" : "heart", 15);
      renderHeaderAuth();
      stToast(res.favorited ? "Adicionado aos favoritos." : "Removido dos favoritos.", "info");
    });
  });

  container.querySelectorAll("[data-open-prod], .st-product-thumb, .st-product-title").forEach((el) => {
    el.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-fav-id], [data-quick-custom]")) return;
      const card = el.closest("[data-prod-slug]");
      if (card) navigate("product", card.dataset.prodSlug);
    });
  });

  container.querySelectorAll("[data-quick-custom]").forEach((btn) => {
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      await startCustomizationFlow(Number(btn.dataset.quickCustom));
    });
  });
}
