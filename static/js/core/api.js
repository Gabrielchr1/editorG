/* Estado global da Loja, cliente HTTP autenticado e utilitários compartilhados */

export const ORDER_STATUS_META = {
  aguardando_pagamento: { label: "Aguardando pagamento", tone: "neutral" },
  pagamento_aprovado: { label: "Pagamento aprovado", tone: "info" },
  aguardando_arquivos: { label: "Aguardando arquivos", tone: "info" },
  em_personalizacao: { label: "Em personalização", tone: "info" },
  aguardando_aprovacao: { label: "Aguardando aprovação do cliente", tone: "warn" },
  aprovado_cliente: { label: "Aprovado pelo cliente", tone: "ok" },
  em_pre_impressao: { label: "Em pré-impressão", tone: "info" },
  aguardando_correcao: { label: "Aguardando correção", tone: "warn" },
  liberado_producao: { label: "Liberado para produção", tone: "ok" },
  em_producao: { label: "Em produção", tone: "info" },
  finalizado: { label: "Finalizado", tone: "ok" },
  enviado: { label: "Enviado", tone: "info" },
  entregue: { label: "Entregue", tone: "ok" },
  cancelado: { label: "Cancelado", tone: "danger" },
};

export const stState = {
  token: localStorage.getItem("eg_token") || "",
  cartSession: localStorage.getItem("eg_cart_session") || `cs_${Math.random().toString(36).slice(2, 12)}`,
  user: null,
  homeData: null,
  categories: [],
  route: "home",
  routeParam: null,
  filters: {
    q: "",
    category: "all",
    format_filter: "",
    layout_type: "",
    orientation: "",
    min_price: "",
    max_price: "",
    only_customizable: false,
    sort: "relevance",
    page: 1,
  },
  catalogData: { total: 0, products: [] },
  currentProduct: null,
  toolLabels: {},
  detailSel: {
    variationId: null,
    paper: "",
    finish: "",
    quantity: 1,
    priceCalc: null,
    activeImgIdx: 0,
  },
  cart: { items: [], item_count: 0, subtotal: 0, discount_total: 0, shipping_total: 0, total_amount: 0 },
  favoritesSet: new Set(),
  checkoutStep: 1, // 1: Sacola, 2: Entrega & Pagamento, 3: Confirmação
  checkoutResult: null,
  accountTab: "overview",
  selectedOrderDetail: null,
  adminTab: "overview",
  pendingActionAfterAuth: null,
};

localStorage.setItem("eg_cart_session", stState.cartSession);

let _navigateFn = async () => {};
let _authChangeHooks = [];
let _openAuthModalFn = () => {};

export function registerRouter(fn) {
  _navigateFn = fn;
}

export function navigate(route, param = null) {
  return _navigateFn(route, param);
}

export function onAuthRefresh(cb) {
  _authChangeHooks.push(cb);
}

export function registerAuthModalOpener(fn) {
  _openAuthModalFn = fn;
}

export function triggerAuthModal(tab = "login") {
  _openAuthModalFn(tab);
}

export function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function money(val) {
  return Number(val || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function stToast(msg, type = "info") {
  let box = document.getElementById("toast-container");
  if (!box) {
    box = document.createElement("div");
    box.id = "toast-container";
    box.className = "toast-container";
    document.body.appendChild(box);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (stState.token) headers.Authorization = `Bearer ${stState.token}`;
  if (stState.cartSession) headers["X-Cart-Session"] = stState.cartSession;
  if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401 && stState.token && path !== "/api/auth/login") {
    stState.token = "";
    stState.user = null;
    localStorage.removeItem("eg_token");
    _authChangeHooks.forEach((fn) => fn());
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Erro HTTP ${res.status}`);
    return data;
  }
  if (!res.ok) throw new Error((await res.text()) || `Erro HTTP ${res.status}`);
  return res;
}

export async function downloadWithAuth(url, filename) {
  const res = await fetch(url, {
    headers: stState.token ? { Authorization: `Bearer ${stState.token}` } : {},
  });
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(a.href);
    a.remove();
  }, 800);
}

export function canPerm(mod, act = "read") {
  const perms = stState.user?.permissions || {};
  return Array.isArray(perms[mod]) && perms[mod].includes(act);
}

export function statusPillHtml(stKey) {
  const m = ORDER_STATUS_META[stKey] || { label: stKey || "-", tone: "neutral" };
  return `<span class="st-status-pill ${m.tone}">${esc(m.label)}</span>`;
}

export function closeStoreModal() {
  const root = document.getElementById("store-modal-root");
  if (root) root.innerHTML = "";
}

export function openStoreModal(innerHtml) {
  const root = document.getElementById("store-modal-root");
  if (!root) return;
  root.innerHTML = `<div class="modal-backdrop" id="st-modal-backdrop">${innerHtml}</div>`;
  document.getElementById("st-modal-backdrop")?.addEventListener("click", (ev) => {
    if (ev.target.id === "st-modal-backdrop" || ev.target.closest("[data-st-close]")) closeStoreModal();
  });
}

export async function refreshUserAndCart() {
  if (stState.token) {
    try {
      const me = await api("/api/auth/me");
      stState.user = me.user;
      const favRes = await api("/api/account/favorites").catch(() => ({ favorites: [] }));
      stState.favoritesSet = new Set((favRes.favorites || []).map((p) => p.id));
    } catch {
      stState.user = null;
      stState.token = "";
      localStorage.removeItem("eg_token");
    }
  } else {
    stState.user = null;
    stState.favoritesSet = new Set();
  }
  try {
    const c = await api("/api/cart");
    stState.cart = c;
    if (c.session_token) {
      stState.cartSession = c.session_token;
      localStorage.setItem("eg_cart_session", c.session_token);
    }
  } catch { /* ignore */ }
  _authChangeHooks.forEach((fn) => fn());
}

export async function startCustomizationFlow(productId, opts = {}) {
  if (!stState.user) {
    stState.pendingActionAfterAuth = () => startCustomizationFlow(productId, opts);
    _openAuthModalFn("login");
    stToast("Entre ou crie sua conta para personalizar e salvar seus projetos.", "info");
    return;
  }
  try {
    const res = await api("/api/customizer/start", {
      method: "POST",
      body: JSON.stringify({
        product_id: productId,
        variation_id: opts.variationId || null,
        selected_options: opts.selectedOptions || {},
      }),
    });
    if (window.EGEditor?.openCustomerProjectInEditor) {
      await window.EGEditor.openCustomerProjectInEditor(res.project.id, {
        productId,
        productName: res.project.name,
        variationId: opts.variationId || null,
        selectedOptions: opts.selectedOptions || {},
        onReturn: async ({ targetRoute }) => {
          await refreshUserAndCart();
          if (targetRoute === "cart") await navigate("cart");
          else if (stState.route === "product" && stState.currentProduct) await navigate("product", stState.currentProduct.slug);
          else await navigate(targetRoute || "account");
        },
      });
    } else {
      stToast("Editor gráfico não inicializado.", "error");
    }
  } catch (err) {
    stToast(err.message, "error");
  }
}
