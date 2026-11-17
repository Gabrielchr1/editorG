/* Sacola, Checkout em Etapas & Confirmação Pix / Mercado Pago */

import {
  api,
  esc,
  money,
  navigate,
  refreshUserAndCart,
  stState,
  stToast,
  triggerAuthModal,
} from "../core/api.js";
import { icon } from "../core/icons.js";
import { renderHeaderAuth } from "../components/header_footer.js";

function renderStepsBar(activeStep) {
  const steps = [
    [1, "Revisão da Sacola"],
    [2, "Entrega & Pagamento"],
    [3, "Pedido Confirmado"],
  ];
  return `
    <div class="st-steps-bar" aria-label="Etapas do pedido">
      ${steps.map(([num, lbl]) => {
        const cls = num < activeStep ? "done" : num === activeStep ? "active" : "";
        return `
          <div class="st-step-pill ${cls}">
            <span class="st-step-num">${num < activeStep ? icon("check", 12) : num}</span>
            <span>${esc(lbl)}</span>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

export async function renderCartView(main) {
  stState.cart = await api("/api/cart");
  renderHeaderAuth();
  const c = stState.cart;

  main.innerHTML = `
    <section class="st-section-compact">
      <div class="st-container">
        <div class="st-section-head" style="margin-bottom:22px;">
          <div>
            <p class="st-eyebrow">Etapa 1 de 3</p>
            <h1 class="st-section-title">Sua Sacola Editorial</h1>
          </div>
          <button class="st-btn st-btn-outline st-btn-sm" id="cart-cont-shop">
            ${icon("arrow-left", 14)} Continuar Escolhendo
          </button>
        </div>

        ${renderStepsBar(1)}

        ${!c.items?.length ? `
          <div class="st-panel-card" style="text-align:center;padding:56px 24px;">
            <h3 style="font-family:var(--font-editorial);font-size:26px;margin:0 0 8px;">Sua sacola está vazia</h3>
            <p style="color:var(--st-ink-muted);margin:0 0 22px;">Explore nossas edições prontas ou personalize um miolo exclusivo no estúdio online.</p>
            <button class="st-btn st-btn-gold" id="cart-go-cat">Explorar Catálogo</button>
          </div>
        ` : `
          <div class="st-checkout-grid">
            <div style="display:flex;flex-direction:column;gap:14px;">
              ${c.items.map((it) => `
                <div class="st-panel-card" style="margin-bottom:0;display:grid;grid-template-columns:88px 1fr auto;gap:18px;align-items:center;">
                  <img src="${esc(it.image_url || "/uploads/demo/mockups/mockup_agenda.svg")}" alt="${esc(it.product_name)}" style="width:88px;height:94px;object-fit:contain;background:var(--st-surface-soft);border:1px solid var(--st-border);border-radius:4px;padding:6px;" />
                  <div style="min-width:0;">
                    <div style="font-family:var(--font-editorial);font-size:20px;font-weight:600;line-height:1.2;">${esc(it.product_name)}</div>
                    <div style="font-size:12.5px;color:var(--st-ink-muted);margin-top:4px;">
                      ${it.variation_name ? esc(it.variation_name) : "Padrão"}
                      ${(it.selected_options?.paper_option || it.selected_options?.paper) ? ` • ${esc(it.selected_options.paper_option || it.selected_options.paper)}` : ""}
                      ${(it.selected_options?.finish_option || it.selected_options?.finish) ? ` • ${esc(it.selected_options.finish_option || it.selected_options.finish)}` : ""}
                    </div>
                    <div style="display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap;">
                      ${it.is_customized && it.project_id ? `
                        <span class="st-status-pill info">Personalizado v${it.project_version || 1}</span>
                        <button class="st-btn st-btn-soft st-btn-xs" data-cart-edit-proj="${it.project_id}" data-prod-id="${it.product_id}">
                          ${icon("edit", 12)} Reabrir no Estúdio
                        </button>
                      ` : `<span class="st-status-pill">Edição Pronta</span>`}
                    </div>
                  </div>
                  <div style="text-align:right;display:flex;flex-direction:column;gap:8px;align-items:flex-end;">
                    <div style="font-size:17px;font-weight:600;">${money(it.total_price)}</div>
                    <div style="font-size:11.5px;color:var(--st-ink-muted);">${money(it.unit_price)} / un.</div>
                    <div style="display:flex;gap:6px;align-items:center;">
                      <input type="number" min="1" max="5000" value="${it.quantity}" class="st-input" data-cart-qty="${it.id}" style="width:74px;height:32px;padding:0 8px;text-align:center;" />
                      <button class="st-icon-btn" style="width:32px;height:32px;" data-cart-del="${it.id}" title="Remover item" aria-label="Remover item">${icon("trash", 14)}</button>
                    </div>
                  </div>
                </div>
              `).join("")}
            </div>

            <aside class="st-panel-card" style="position:sticky;top:96px;">
              <h3 style="font-family:var(--font-editorial);font-size:23px;margin:0 0 18px;">Resumo do Pedido</h3>
              <div class="st-filter-group">
                <label class="st-filter-label" for="cart-zip">Frete (CEP)</label>
                <div style="display:flex;gap:8px;">
                  <input id="cart-zip" class="st-input" type="text" placeholder="01310-100" value="${esc(c.zip_code || "")}" />
                  <button id="cart-btn-zip" class="st-btn st-btn-soft st-btn-sm" style="height:42px;">Calcular</button>
                </div>
              </div>
              <div class="st-filter-group">
                <label class="st-filter-label" for="cart-coupon">Cupom (ex: BEMVINDO10)</label>
                <div style="display:flex;gap:8px;">
                  <input id="cart-coupon" class="st-input" type="text" placeholder="Código" value="${esc(c.coupon_code || "")}" />
                  <button id="cart-btn-coupon" class="st-btn st-btn-soft st-btn-sm" style="height:42px;">Aplicar</button>
                </div>
                ${(c.coupon_info?.reason || c.coupon_info?.message) && c.coupon_code ? `<div style="font-size:11.5px;margin-top:6px;color:${c.coupon_info.valid ? "var(--st-ok)" : "var(--st-danger)"};">${esc(c.coupon_info.reason || c.coupon_info.message)}</div>` : ""}
              </div>

              <div style="border-top:1px solid var(--st-border);padding-top:14px;display:flex;flex-direction:column;gap:9px;font-size:14px;">
                <div style="display:flex;justify-content:space-between;"><span style="color:var(--st-ink-muted);">Subtotal</span><strong>${money(c.subtotal)}</strong></div>
                <div style="display:flex;justify-content:space-between;"><span style="color:var(--st-ink-muted);">Descontos</span><strong>- ${money(c.discount_total)}</strong></div>
                <div style="display:flex;justify-content:space-between;"><span style="color:var(--st-ink-muted);">Frete</span><strong>${c.shipping_total === 0 ? "Grátis" : money(c.shipping_total)}</strong></div>
                <div style="display:flex;justify-content:space-between;font-family:var(--font-editorial);font-size:24px;font-weight:600;padding-top:10px;border-top:1px solid var(--st-border);"><span>Total</span><span>${money(c.total_amount)}</span></div>
              </div>
              <button id="cart-btn-checkout" class="st-btn st-btn-gold st-btn-lg" style="width:100%;margin-top:18px;">
                Prosseguir para Entrega ${icon("arrow-right", 16)}
              </button>
            </aside>
          </div>
        `}
      </div>
    </section>
  `;

  main.querySelector("#cart-cont-shop")?.addEventListener("click", () => navigate("catalog"));
  main.querySelector("#cart-go-cat")?.addEventListener("click", () => navigate("catalog"));

  main.querySelectorAll("[data-cart-qty]").forEach((inp) => {
    inp.addEventListener("change", async () => {
      const id = Number(inp.dataset.cartQty);
      const qty = Math.max(1, parseInt(inp.value || "1", 10) || 1);
      stState.cart = await api(`/api/cart/items/${id}`, { method: "PATCH", body: JSON.stringify({ quantity: qty }) });
      renderCartView(main);
    });
  });

  main.querySelectorAll("[data-cart-del]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      stState.cart = await api(`/api/cart/items/${Number(btn.dataset.cartDel)}`, { method: "DELETE" });
      renderCartView(main);
    });
  });

  main.querySelectorAll("[data-cart-edit-proj]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const pid = Number(btn.dataset.cartEditProj);
      if (window.EGEditor?.openCustomerProjectInEditor) {
        await window.EGEditor.openCustomerProjectInEditor(pid, {
          productId: Number(btn.dataset.prodId),
          onReturn: async () => navigate("cart"),
        });
      }
    });
  });

  main.querySelector("#cart-btn-zip")?.addEventListener("click", async () => {
    const zip_code = document.getElementById("cart-zip").value.trim();
    stState.cart = await api("/api/cart/shipping", { method: "POST", body: JSON.stringify({ zip_code }) });
    renderCartView(main);
  });

  main.querySelector("#cart-btn-coupon")?.addEventListener("click", async () => {
    const coupon_code = document.getElementById("cart-coupon").value.trim();
    try {
      const res = await api("/api/cart/coupon", { method: "POST", body: JSON.stringify({ coupon_code }) });
      stState.cart = res.cart || res;
      stToast(coupon_code ? "Cupom aplicado com sucesso." : "Cupom removido.", "success");
    } catch (err) {
      stToast(err.message, "error");
    }
    renderCartView(main);
  });

  main.querySelector("#cart-btn-checkout")?.addEventListener("click", () => {
    if (!stState.user) {
      stState.pendingActionAfterAuth = () => navigate("checkout");
      triggerAuthModal("login");
      stToast("Entre na sua conta para concluir o pedido.", "info");
      return;
    }
    stState.checkoutResult = null;
    navigate("checkout");
  });
}

export async function renderCheckoutView(main) {
  if (!stState.user) {
    triggerAuthModal("login");
    return;
  }

  if (stState.checkoutResult) {
    const cr = stState.checkoutResult;
    main.innerHTML = `
      <section class="st-section-compact">
        <div class="st-container" style="max-width:860px;">
          ${renderStepsBar(3)}
          <div class="st-panel-card">
            <span class="st-status-pill ok" style="margin-bottom:12px;">${icon("check", 13)} Pedido Registrado</span>
            <h1 class="st-section-title">Pedido ${esc(cr.order.order_number)}</h1>
            <p class="st-section-desc" style="margin-bottom:20px;">Valor total: <strong>${money(cr.order.total_amount)}</strong> via <strong>${esc(cr.payment.provider.toUpperCase())}</strong>.</p>
            ${cr.payment.qr_code_payload ? `
              <div class="st-filter-group">
                <label class="st-filter-label">Código Pix Copia e Cola</label>
                <textarea class="st-textarea" readonly>${esc(cr.payment.qr_code_payload)}</textarea>
              </div>
            ` : `
              <div style="margin-bottom:20px;">
                <a href="${esc(cr.payment.checkout_url)}" target="_blank" class="st-btn st-btn-gold">Abrir Pagamento Mercado Pago</a>
              </div>
            `}
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">
              <button id="chk-go-orders" class="st-btn st-btn-dark">Acompanhar Meus Pedidos</button>
              ${stState.user?.is_staff ? `<button id="chk-sandbox-pay" class="st-btn st-btn-outline">Confirmar Pagamento (Sandbox Admin)</button>` : ""}
            </div>
          </div>
        </div>
      </section>
    `;
    main.querySelector("#chk-go-orders")?.addEventListener("click", () => {
      stState.accountTab = "orders";
      navigate("account");
    });
    main.querySelector("#chk-sandbox-pay")?.addEventListener("click", async () => {
      await api(`/api/admin/payments/${cr.payment.external_id}/sandbox-confirm?status=approved`, { method: "POST" });
      stToast("Pagamento aprovado no sandbox. Pedido avançou na fila.", "success");
      stState.accountTab = "orders";
      navigate("account");
    });
    return;
  }

  const [cart, addrRes] = await Promise.all([api("/api/cart"), api("/api/account/addresses")]);
  stState.cart = cart;
  const addrs = addrRes.addresses || [];
  if (!cart.items?.length) {
    navigate("cart");
    return;
  }

  main.innerHTML = `
    <section class="st-section-compact">
      <div class="st-container">
        <div class="st-section-head" style="margin-bottom:22px;">
          <div>
            <p class="st-eyebrow">Etapa 2 de 3</p>
            <h1 class="st-section-title">Entrega &amp; Pagamento</h1>
          </div>
          <button class="st-btn st-btn-outline st-btn-sm" id="chk-back-cart">
            ${icon("arrow-left", 14)} Voltar à Sacola
          </button>
        </div>

        ${renderStepsBar(2)}

        <form id="chk-form" class="st-checkout-grid">
          <div class="st-panel-card">
            <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0 0 16px;">1. Endereço de Entrega</h3>
            ${addrs.length ? `
              <div class="st-filter-group">
                <label class="st-filter-label" for="chk-addr-id">Endereços Salvos</label>
                <select id="chk-addr-id" class="st-select">
                  ${addrs.map((a) => `<option value="${a.id}">${esc(a.label)}: ${esc(a.street)}, ${esc(a.number)} - ${esc(a.city)}/${esc(a.state)} (${esc(a.zip_code)})</option>`).join("")}
                  <option value="">Cadastrar novo endereço abaixo</option>
                </select>
              </div>
            ` : ""}
            <div id="chk-new-addr" class="${addrs.length ? "hidden" : ""}" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:18px;">
              <input id="chk-rec" class="st-input" placeholder="Destinatário" value="${esc(stState.user.name || "")}" />
              <input id="chk-cep" class="st-input" placeholder="CEP" value="${esc(cart.zip_code || "")}" />
              <input id="chk-street" class="st-input" placeholder="Logradouro / Rua" />
              <input id="chk-num" class="st-input" placeholder="Número" />
              <input id="chk-neigh" class="st-input" placeholder="Bairro" />
              <input id="chk-comp" class="st-input" placeholder="Complemento" />
              <input id="chk-city" class="st-input" placeholder="Cidade" />
              <input id="chk-uf" class="st-input" placeholder="UF (ex: SP)" maxlength="2" />
            </div>

            <h3 style="font-family:var(--font-editorial);font-size:22px;margin:22px 0 12px;">2. Forma de Pagamento</h3>
            <div style="display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap;">
              <label class="st-pay-option">
                <input type="radio" name="pay_method" value="pix" checked style="margin-top:3px;" />
                <div>
                  <strong>Pix Instantâneo</strong>
                  <div style="font-size:12px;color:var(--st-ink-muted);margin-top:2px;">Aprovação imediata por QR Code ou Copia e Cola.</div>
                </div>
              </label>
              <label class="st-pay-option">
                <input type="radio" name="pay_method" value="mercadopago" style="margin-top:3px;" />
                <div>
                  <strong>Mercado Pago</strong>
                  <div style="font-size:12px;color:var(--st-ink-muted);margin-top:2px;">Cartão de crédito em parcelas ou boleto.</div>
                </div>
              </label>
            </div>

            <div class="st-filter-group" style="margin-bottom:0;">
              <label class="st-filter-label" for="chk-notes">Observações para a Gráfica</label>
              <textarea id="chk-notes" class="st-textarea" placeholder="Detalhes adicionais de envio ou produção..."></textarea>
            </div>
          </div>

          <aside class="st-panel-card" style="position:sticky;top:96px;">
            <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0 0 14px;">Conferência do Pedido</h3>
            ${cart.items.map((it) => `
              <div style="display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:8px 0;border-bottom:1px solid var(--st-border-subtle);">
                <span>${it.quantity}× ${esc(it.product_name)}</span>
                <strong>${money(it.total_price)}</strong>
              </div>
            `).join("")}
            <div style="margin-top:16px;display:flex;flex-direction:column;gap:8px;font-size:13.5px;">
              <div style="display:flex;justify-content:space-between;"><span style="color:var(--st-ink-muted);">Subtotal</span><span>${money(cart.subtotal)}</span></div>
              <div style="display:flex;justify-content:space-between;"><span style="color:var(--st-ink-muted);">Desconto</span><span>- ${money(cart.discount_total)}</span></div>
              <div style="display:flex;justify-content:space-between;"><span style="color:var(--st-ink-muted);">Frete</span><span>${cart.shipping_total === 0 ? "Grátis" : money(cart.shipping_total)}</span></div>
              <div style="display:flex;justify-content:space-between;font-family:var(--font-editorial);font-size:24px;font-weight:600;padding-top:10px;border-top:1px solid var(--st-border);"><span>Total</span><span>${money(cart.total_amount)}</span></div>
            </div>
            <button type="submit" class="st-btn st-btn-gold st-btn-lg" style="width:100%;margin-top:18px;">
              ${icon("lock", 15)} Confirmar Pedido &amp; Pagar
            </button>
          </aside>
        </form>
      </div>
    </section>
  `;

  main.querySelector("#chk-back-cart")?.addEventListener("click", () => navigate("cart"));
  const addrSel = main.querySelector("#chk-addr-id");
  const newBox = main.querySelector("#chk-new-addr");
  addrSel?.addEventListener("change", () => newBox.classList.toggle("hidden", Boolean(addrSel.value)));

  main.querySelector("#chk-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const addrIdVal = addrSel?.value ? Number(addrSel.value) : null;
    const payMethod = main.querySelector('input[name="pay_method"]:checked')?.value || "pix";
    const body = {
      address_id: addrIdVal,
      payment_method: payMethod,
      customer_notes: document.getElementById("chk-notes").value.trim(),
    };
    if (!addrIdVal) {
      const street = document.getElementById("chk-street").value.trim();
      const city = document.getElementById("chk-city").value.trim();
      const state = document.getElementById("chk-uf").value.trim();
      const zip = document.getElementById("chk-cep").value.trim();
      if (!street || !city || !state || !zip) {
        stToast("Preencha o endereço de entrega completo.", "warning");
        return;
      }
      body.address = {
        recipient_name: document.getElementById("chk-rec").value.trim() || stState.user.name,
        street,
        number: document.getElementById("chk-num").value.trim() || "S/N",
        complement: document.getElementById("chk-comp").value.trim(),
        neighborhood: document.getElementById("chk-neigh").value.trim(),
        city,
        state: state.toUpperCase(),
        zip_code: zip,
      };
    }
    try {
      stState.checkoutResult = await api("/api/checkout", { method: "POST", body: JSON.stringify(body) });
      await refreshUserAndCart();
      renderCheckoutView(main);
    } catch (err) {
      stToast(err.message, "error");
    }
  });
}
