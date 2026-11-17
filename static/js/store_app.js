/* Orquestrador SPA Modular da Loja EditorGráfica Atelier */

import {
  api,
  onAuthRefresh,
  refreshUserAndCart,
  registerAuthModalOpener,
  registerRouter,
  stState,
  stToast,
} from "./core/api.js";
import { openMobileDrawer, renderHeaderAuth } from "./components/header_footer.js";
import { renderHomeView } from "./views/home_view.js";
import { renderCatalogView, renderProductDetailView } from "./views/catalog_view.js";
import { renderCartView, renderCheckoutView } from "./views/checkout_view.js";
import { renderAccountView } from "./views/account_view.js";
import { openAuthModal, renderAdminView } from "./views/admin_view.js";

async function navigate(route, param = null) {
  stState.route = route;
  stState.routeParam = param;
  renderHeaderAuth();
  const viewStore = document.getElementById("view-store");
  if (viewStore) viewStore.scrollTo({ top: 0, behavior: "smooth" });

  const main = document.getElementById("store-main");
  if (!main) return;

  if (route === "home") await renderHomeView(main);
  else if (route === "catalog") await renderCatalogView(main);
  else if (route === "product") await renderProductDetailView(main, param);
  else if (route === "cart") await renderCartView(main);
  else if (route === "checkout") await renderCheckoutView(main);
  else if (route === "account") await renderAccountView(main);
  else if (route === "admin") await renderAdminView(main);
}

async function addCustomizedProjectToCart({ productId, variationId, projectId, selectedOptions }) {
  try {
    const res = await api("/api/cart/items", {
      method: "POST",
      body: JSON.stringify({
        product_id: productId,
        variation_id: variationId || null,
        project_id: projectId,
        is_customized: true,
        selected_options: selectedOptions || {},
        quantity: 1,
      }),
    });
    stState.cart = res;
    renderHeaderAuth();
    stToast("Projeto personalizado adicionado à sacola.", "success");
    return true;
  } catch (err) {
    stToast(err.message, "error");
    return false;
  }
}

function bindStoreHeader() {
  document.getElementById("st-brand-home")?.addEventListener("click", () => navigate("home"));

  document.querySelectorAll("#st-main-nav [data-st-route]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.stRoute === "catalog") {
        stState.filters.category = "all";
        stState.filters.only_customizable = false;
      }
      navigate(btn.dataset.stRoute);
    });
  });
  document.querySelectorAll("#st-main-nav [data-st-cat]").forEach((btn) => {
    btn.addEventListener("click", () => {
      stState.filters.category = btn.dataset.stCat;
      stState.filters.only_customizable = false;
      navigate("catalog");
    });
  });
  document.getElementById("st-nav-studio")?.addEventListener("click", () => window.EGEditor?.openStudioDashboard());
  document.getElementById("st-btn-mobile-menu")?.addEventListener("click", openMobileDrawer);

  // Busca retrátil discreta no Header
  const searchToggleBtn = document.getElementById("st-btn-search-toggle");
  const searchPanel = document.getElementById("st-search-bar-panel");
  const searchInput = document.getElementById("st-quick-search");
  const closeSearchPanel = () => {
    searchPanel?.classList.add("hidden");
    searchToggleBtn?.setAttribute("aria-expanded", "false");
  };
  const runQuickSearch = () => {
    if (!searchInput) return;
    stState.filters.q = searchInput.value.trim();
    closeSearchPanel();
    navigate("catalog");
  };

  searchToggleBtn?.addEventListener("click", () => {
    const isHidden = searchPanel?.classList.contains("hidden");
    if (isHidden) {
      searchPanel.classList.remove("hidden");
      searchToggleBtn.setAttribute("aria-expanded", "true");
      setTimeout(() => searchInput?.focus(), 40);
    } else {
      closeSearchPanel();
    }
  });
  document.getElementById("st-btn-search-close")?.addEventListener("click", closeSearchPanel);
  document.getElementById("st-btn-search-submit")?.addEventListener("click", runQuickSearch);
  searchInput?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") runQuickSearch();
    else if (ev.key === "Escape") closeSearchPanel();
  });

  // Tab bar fixa estilo App Nativo no Mobile
  document.querySelectorAll("#st-mobile-tabbar [data-mobtab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const t = btn.dataset.mobtab;
      if (t === "home") navigate("home");
      else if (t === "catalog") {
        stState.filters.category = "all";
        stState.filters.only_customizable = false;
        navigate("catalog");
      } else if (t === "customizable") {
        stState.filters.category = "all";
        stState.filters.only_customizable = true;
        navigate("catalog");
      } else if (t === "cart") {
        navigate("cart");
      } else if (t === "account") {
        if (stState.user) navigate("account");
        else openAuthModal("login");
      }
    });
  });

  document.getElementById("st-btn-fav")?.addEventListener("click", () => {
    if (!stState.user) {
      stState.pendingActionAfterAuth = () => {
        stState.accountTab = "favorites";
        navigate("account");
      };
      openAuthModal("login");
      return;
    }
    stState.accountTab = "favorites";
    navigate("account");
  });

  document.getElementById("st-btn-account")?.addEventListener("click", () => {
    if (stState.user) navigate("account");
    else openAuthModal("login");
  });
  document.getElementById("st-btn-cart")?.addEventListener("click", () => navigate("cart"));

  window.addEventListener("eg-store-return", async (ev) => {
    await refreshUserAndCart();
    const target = ev.detail?.targetRoute;
    if (target) await navigate(target);
    else renderHeaderAuth();
  });
}

async function initStoreApp() {
  registerRouter(navigate);
  registerAuthModalOpener(openAuthModal);
  onAuthRefresh(renderHeaderAuth);

  window.EGStore = {
    addCustomizedProjectToCart,
    navigate,
    openAuthModal,
  };

  bindStoreHeader();
  await refreshUserAndCart();
  await navigate("home");
}

initStoreApp();
