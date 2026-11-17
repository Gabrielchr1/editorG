/* Painel Administrativo RBAC, Fila de Produção CMYK & Modal de Autenticação */

import {
  api,
  canPerm,
  closeStoreModal,
  downloadWithAuth,
  esc,
  money,
  navigate,
  openStoreModal,
  refreshUserAndCart,
  statusPillHtml,
  stState,
  stToast,
} from "../core/api.js";
import { icon } from "../core/icons.js";

export async function renderAdminView(main) {
  if (!stState.user?.is_staff) {
    main.innerHTML = `
      <section class="st-section-compact"><div class="st-container"><div class="st-panel-card">Acesso restrito à equipe da gráfica.</div></div></section>
    `;
    return;
  }

  const allTabs = [
    ["overview", "Dashboard & Vendas", () => canPerm("reports", "read")],
    ["production", "Fila de Produção CMYK", () => canPerm("production", "read")],
    ["products", "Produtos & Ferramentas", () => canPerm("products", "read")],
    ["categories", "Categorias", () => canPerm("categories", "read")],
    ["templates", "Modelos Versionados", () => canPerm("templates", "read")],
    ["coupons", "Cupons & Descontos", () => canPerm("coupons", "read")],
    ["users", "Usuários & Overrides", () => canPerm("users", "read")],
    ["roles", "Cargos & Matriz RBAC", () => canPerm("permissions", "read")],
    ["settings", "Identidade & Home", () => canPerm("settings", "read")],
    ["reports", "Relatórios & Exportação", () => canPerm("reports", "read")],
    ["support", "Chamados", () => canPerm("support", "read")],
    ["audit", "Auditoria & Mídia", () => canPerm("audit", "read") || canPerm("files", "read")],
  ];
  const visibleTabs = allTabs.filter((t) => t[2]());
  if (!visibleTabs.length) {
    main.innerHTML = `<section class="st-section-compact"><div class="st-container"><div class="st-panel-card">Seu cargo não possui módulos administrativos habilitados.</div></div></section>`;
    return;
  }
  if (!visibleTabs.some((t) => t[0] === stState.adminTab)) stState.adminTab = visibleTabs[0][0];

  main.innerHTML = `
    <section class="st-section-compact">
      <div class="st-container">
        <div class="st-section-head" style="margin-bottom:26px;">
          <div>
            <p class="st-eyebrow">Operação &amp; Controle RBAC</p>
            <h1 class="st-section-title">Painel Administrativo</h1>
            <p class="st-section-desc">Logado como <strong>${esc(stState.user.name)}</strong> • Cargo: ${esc(stState.user.role_name)}</p>
          </div>
          <button id="adm-open-studio" class="st-btn st-btn-gold st-btn-sm">
            ${icon("sliders", 14)} Abrir Editor Studio Livre
          </button>
        </div>

        <div class="st-account-shell">
          <aside class="st-side-menu">
            ${visibleTabs.map(([id, lbl]) => `<button class="st-side-btn ${stState.adminTab === id ? "active" : ""}" data-adm-tab="${id}">${esc(lbl)}</button>`).join("")}
          </aside>
          <div id="adm-content"></div>
        </div>
      </div>
    </section>
  `;

  main.querySelector("#adm-open-studio")?.addEventListener("click", () => window.EGEditor?.openStudioDashboard());
  main.querySelectorAll("[data-adm-tab]").forEach((b) => {
    b.addEventListener("click", () => {
      stState.adminTab = b.dataset.admTab;
      renderAdminView(main);
    });
  });

  await renderAdminTabContent(main.querySelector("#adm-content"));
}

async function renderAdminTabContent(box) {
  const tab = stState.adminTab;
  if (tab === "overview") {
    const d = await api("/api/admin/dashboard?days=30");
    const k = d.kpis || {};
    box.innerHTML = `
      <div class="st-kpi-grid">
        <div class="st-kpi-card"><div class="st-kpi-lbl">Faturamento (30d)</div><div class="st-kpi-val">${money(k.revenue)}</div></div>
        <div class="st-kpi-card"><div class="st-kpi-lbl">Pedidos no Período</div><div class="st-kpi-val">${k.total_orders}</div></div>
        <div class="st-kpi-card"><div class="st-kpi-lbl">Em Produção</div><div class="st-kpi-val">${k.in_production}</div></div>
        <div class="st-kpi-card"><div class="st-kpi-lbl">Conversão</div><div class="st-kpi-val">${k.conversion_rate}%</div></div>
      </div>
      <div class="st-editorial-two" style="gap:20px;">
        <div class="st-panel-card">
          <h3 style="font-family:var(--font-editorial);font-size:21px;margin:0 0 12px;">Mais Vendidos</h3>
          ${(d.top_products || []).map((p) => `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--st-border-subtle);"><span>${esc(p.name)}</span><strong>${p.sales_count} un.</strong></div>`).join("")}
        </div>
        <div class="st-panel-card">
          <h3 style="font-family:var(--font-editorial);font-size:21px;margin:0 0 12px;">Rentabilidade Estimada</h3>
          ${(d.profitability || []).map((p) => `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--st-border-subtle);"><span>${esc(p.product_name)} (${p.qty}×)</span><strong>Lucro ${money(p.profit)}</strong></div>`).join("") || `<p style="color:var(--st-ink-muted);margin:0;">Sem itens faturados ainda.</p>`}
        </div>
      </div>
    `;
  } else if (tab === "production") {
    const q = await api("/api/production/queue");
    const statuses = q.status_options || {};
    const editors = q.editors || [];
    box.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:14px;">
        ${(q.orders || []).map((o) => `
          <div class="st-panel-card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
              <div>
                <strong>${esc(o.order_number)}</strong> • ${esc(o.customer_name)} (${esc(o.customer_email)})
                <div style="font-size:12px;color:var(--st-ink-muted);">Total ${money(o.total_amount)} • Pagamento: ${esc(o.payment_status)} • Editor: ${esc(o.assigned_editor_name || "Não atribuído")}</div>
              </div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
                ${statusPillHtml(o.status)}
                ${canPerm("production", "edit") ? `
                  <select class="st-select" style="width:165px;height:34px;" data-assign-ord="${o.id}">
                    <option value="">Atribuir editor...</option>
                    ${editors.map((e) => `<option value="${e.id}" ${o.assigned_editor_id === e.id ? "selected" : ""}>${esc(e.name)}</option>`).join("")}
                  </select>
                ` : ""}
                ${canPerm("orders", "edit") ? `
                  <select class="st-select" style="width:205px;height:34px;" data-status-ord="${o.id}">
                    ${Object.entries(statuses).map(([k, lbl]) => `<option value="${k}" ${o.status === k ? "selected" : ""}>${esc(lbl)}</option>`).join("")}
                  </select>
                ` : ""}
              </div>
            </div>
            ${(o.items || []).map((it) => `
              <div style="padding:12px;background:var(--st-surface-soft);border:1px solid var(--st-border-subtle);border-radius:4px;margin-top:8px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div><strong>${it.quantity}× ${esc(it.product_name)}</strong> ${it.is_customized ? `(Arte v${it.project_version || 1} • ${esc(it.artwork_status)})` : ""}</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                  ${canPerm("production", "export") ? `<button class="st-btn st-btn-gold st-btn-xs" data-gen-oid="${o.id}" data-gen-iid="${it.id}">${icon("printer", 13)} Gerar PDF CMYK + Preflight</button>` : ""}
                  ${it.preview_file_id ? `<a class="st-btn st-btn-outline st-btn-xs" href="/api/files/${it.preview_file_id}/download?inline=true&token=${encodeURIComponent(stState.token)}" target="_blank">${icon("eye", 13)} Prévia</a>` : ""}
                  ${it.final_file_id ? `<button class="st-btn st-btn-dark st-btn-xs" data-dl-final="${it.final_file_id}" data-dl-fn="producao_${o.order_number}_item${it.id}.pdf">${icon("download", 13)} Baixar CMYK Final</button>` : ""}
                </div>
              </div>
            `).join("")}
          </div>
        `).join("") || `<div class="st-panel-card">Nenhum pedido na fila de produção.</div>`}
      </div>
    `;

    box.querySelectorAll("[data-assign-ord]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        if (!sel.value) return;
        await api(`/api/production/orders/${sel.dataset.assignOrd}/assign`, { method: "POST", body: JSON.stringify({ editor_user_id: Number(sel.value) }) });
        stToast("Editor atribuído.", "success");
      });
    });
    box.querySelectorAll("[data-status-ord]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        await api(`/api/production/orders/${sel.dataset.statusOrd}/status`, { method: "POST", body: JSON.stringify({ status: sel.value }) });
        stToast("Status atualizado.", "success");
        renderAdminTabContent(box);
      });
    });
    box.querySelectorAll("[data-gen-oid]").forEach((b) => {
      b.addEventListener("click", async () => {
        b.disabled = true;
        b.textContent = "Gerando CMYK...";
        try {
          await api(`/api/production/orders/${b.dataset.genOid}/items/${b.dataset.genIid}/generate-files?include_bleed=true&include_crop_marks=true`, { method: "POST" });
          stToast("Arquivos de prévia e impressão CMYK gerados.", "success");
          renderAdminTabContent(box);
        } catch (err) {
          stToast(err.message, "error");
        }
      });
    });
    box.querySelectorAll("[data-dl-final]").forEach((b) => {
      b.addEventListener("click", () => downloadWithAuth(`/api/files/${b.dataset.dlFinal}/download`, b.dataset.dlFn));
    });
  } else if (tab === "products") {
    const [pRes, cRes, tRes] = await Promise.all([
      api("/api/admin/products"),
      api("/api/store/categories"),
      canPerm("templates", "read") ? api("/api/admin/templates").catch(() => ({ templates: [] })) : Promise.resolve({ templates: [] }),
    ]);
    const toolLabels = pRes.editor_tool_labels || {};
    box.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0;">Produtos &amp; Permissões (${(pRes.products || []).length})</h3>
        ${canPerm("products", "create") ? `<button id="adm-new-prod" class="st-btn st-btn-gold st-btn-sm">${icon("plus", 14)} Novo Produto</button>` : ""}
      </div>
      <div class="st-table-wrap">
        <table class="st-table">
          <thead><tr><th>Produto</th><th>SKU</th><th>Valor Base</th><th>Tipo</th><th>Permissões</th><th>Ações</th></tr></thead>
          <tbody>
            ${(pRes.products || []).map((p) => {
              const cnt = Object.values(p.allowed_tools || {}).filter(Boolean).length;
              return `
                <tr>
                  <td><strong>${esc(p.name)}</strong><div style="font-size:11px;color:var(--st-ink-muted);">${esc(p.category_name)}</div></td>
                  <td>${esc(p.sku)}</td>
                  <td>${money(p.effective_price)}</td>
                  <td>${p.is_customizable ? "Personalizável" : "Pronto"}</td>
                  <td><span class="st-status-pill">${cnt} / 21 ferramentas</span></td>
                  <td>${canPerm("products", "edit") ? `<button class="st-btn st-btn-outline st-btn-xs" data-edit-prod="${p.id}">Editar</button>` : "-"}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;

    const openProductEditorModal = (prod = null) => {
      const cats = cRes.categories || [];
      const tpls = tRes.templates || [];
      const tools = prod?.allowed_tools || {};
      openStoreModal(`
        <div class="modal" style="max-width:780px;max-height:90vh;overflow:auto;">
          <div class="modal-head"><h2>${prod ? `Editar: ${esc(prod.name)}` : "Novo Produto"}</h2><button class="btn btn-ghost btn-sm btn-icon" data-st-close>${icon("close", 16)}</button></div>
          <form id="adm-prod-form" class="modal-body" style="display:flex;flex-direction:column;gap:12px;">
            <div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;">
              <input id="ap-name" class="st-input" placeholder="Nome" value="${esc(prod?.name || "")}" required />
              <input id="ap-sku" class="st-input" placeholder="SKU" value="${esc(prod?.sku || `EG-${Date.now().toString().slice(-4)}`)}" required />
              <input id="ap-price" class="st-input" type="number" step="0.01" placeholder="Preço Base" value="${prod?.base_price || 99.9}" required />
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
              <select id="ap-cat" class="st-select">${cats.map((c) => `<option value="${c.id}" ${prod?.category_id === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
              <select id="ap-tpl" class="st-select"><option value="">Template Base...</option>${tpls.map((t) => `<option value="${t.id}" ${prod?.template_id === t.id ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select>
              <label style="display:flex;align-items:center;gap:6px;font-size:13px;"><input id="ap-cust" type="checkbox" ${prod ? (prod.is_customizable ? "checked" : "") : "checked"} /> Permitir personalização</label>
            </div>
            <input id="ap-sdesc" class="st-input" placeholder="Descrição curta" value="${esc(prod?.short_description || "")}" />
            <div style="font-size:12px;font-weight:700;margin-top:6px;">21 Permissões Granulares do Editor:</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
              ${Object.entries(toolLabels).map(([k, lbl]) => `
                <label style="display:flex;align-items:center;gap:6px;font-size:12px;">
                  <input type="checkbox" data-ap-tool="${k}" ${tools[k] ? "checked" : ""} /> ${esc(lbl)}
                </label>
              `).join("")}
            </div>
            <div class="modal-foot" style="padding:12px 0 0;"><button type="submit" class="st-btn st-btn-gold btn-sm">Salvar Produto</button></div>
          </form>
        </div>
      `);
      document.getElementById("adm-prod-form").addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const allowed_tools = {};
        document.querySelectorAll("[data-ap-tool]").forEach((cb) => { allowed_tools[cb.dataset.apTool] = cb.checked; });
        const payload = {
          name: document.getElementById("ap-name").value.trim(),
          sku: document.getElementById("ap-sku").value.trim(),
          category_id: Number(document.getElementById("ap-cat").value),
          base_price: Number(document.getElementById("ap-price").value),
          short_description: document.getElementById("ap-sdesc").value.trim(),
          full_description: prod?.full_description || document.getElementById("ap-sdesc").value.trim(),
          images: prod?.images || ["/uploads/demo/mockups/mockup_agenda.svg"],
          mockups: prod?.mockups || ["/uploads/demo/mockups/mockup_agenda.svg"],
          is_customizable: document.getElementById("ap-cust").checked,
          template_id: Number(document.getElementById("ap-tpl").value) || null,
          allowed_tools,
          pricing_rules: prod?.pricing_rules || {},
          specs: prod?.specs || {},
          variations: (prod?.variations || []).map((v) => ({
            name: v.name, sku_suffix: v.sku_suffix, format_label: v.format_label,
            width_mm: v.width_mm, height_mm: v.height_mm, is_dated: v.is_dated,
            price_delta: v.price_delta, page_count_override: v.page_count_override,
          })),
        };
        if (prod) await api(`/api/admin/products/${prod.id}`, { method: "PUT", body: JSON.stringify(payload) });
        else await api("/api/admin/products", { method: "POST", body: JSON.stringify(payload) });
        closeStoreModal();
        stState.homeData = null;
        stToast("Produto salvo.", "success");
        renderAdminTabContent(box);
      });
    };

    box.querySelector("#adm-new-prod")?.addEventListener("click", () => openProductEditorModal(null));
    box.querySelectorAll("[data-edit-prod]").forEach((b) => {
      b.addEventListener("click", () => {
        const prod = (pRes.products || []).find((x) => x.id === Number(b.dataset.editProd));
        if (prod) openProductEditorModal(prod);
      });
    });
  } else if (tab === "categories") {
    const res = await api("/api/admin/categories");
    box.innerHTML = `
      <form id="adm-cat-form" class="st-panel-card" style="display:flex;gap:10px;flex-wrap:wrap;">
        <input id="ac-name" class="st-input" placeholder="Nova Categoria" style="flex:1;" required />
        <input id="ac-desc" class="st-input" placeholder="Descrição" style="flex:2;" />
        <button type="submit" class="st-btn st-btn-gold btn-sm">Adicionar</button>
      </form>
      <div class="st-table-wrap"><table class="st-table"><thead><tr><th>Nome</th><th>Slug</th><th>Descrição</th></tr></thead><tbody>
        ${(res.categories || []).map((c) => `<tr><td><strong>${esc(c.name)}</strong></td><td>${esc(c.slug)}</td><td>${esc(c.description)}</td></tr>`).join("")}
      </tbody></table></div>
    `;
    box.querySelector("#adm-cat-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      await api("/api/admin/categories", { method: "POST", body: JSON.stringify({ name: document.getElementById("ac-name").value, description: document.getElementById("ac-desc").value }) });
      stToast("Categoria criada.", "success");
      renderAdminTabContent(box);
    });
  } else if (tab === "templates") {
    const res = await api("/api/admin/templates");
    box.innerHTML = `
      <div class="st-table-wrap"><table class="st-table">
        <thead><tr><th>Modelo</th><th>Versão</th><th>Status</th><th>Histórico</th><th>Ações</th></tr></thead>
        <tbody>
          ${(res.templates || []).map((t) => `
            <tr>
              <td><strong>${esc(t.name)}</strong><div style="font-size:11px;color:var(--st-ink-muted);">${esc(t.base_layout_mode)}</div></td>
              <td>v${t.current_version}</td>
              <td><span class="st-status-pill">${esc(t.status)}</span></td>
              <td>${(t.versions || []).length} versões</td>
              <td style="display:flex;gap:6px;flex-wrap:wrap;">
                ${canPerm("templates", "edit") ? `<button class="st-btn st-btn-soft st-btn-xs" data-tpl-ver="${t.id}">Nova Versão</button>` : ""}
                ${canPerm("templates", "publish") ? `<button class="st-btn st-btn-outline st-btn-xs" data-tpl-st="${t.id}" data-next="${t.status === "published" ? "draft" : "published"}">${t.status === "published" ? "Despublicar" : "Publicar"}</button>` : ""}
                ${canPerm("templates", "create") ? `<button class="st-btn st-btn-soft st-btn-xs" data-tpl-dup="${t.id}">Duplicar</button>` : ""}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table></div>
    `;
    box.querySelectorAll("[data-tpl-ver]").forEach((b) => {
      b.addEventListener("click", async () => {
        const note = prompt("Descrição das alterações da nova versão:", "Atualização editorial");
        if (note === null) return;
        const tpl = (res.templates || []).find((x) => x.id === Number(b.dataset.tplVer));
        await api(`/api/admin/templates/${b.dataset.tplVer}/versions`, {
          method: "POST",
          body: JSON.stringify({ name: tpl.name, allowed_tools: tpl.allowed_tools, changelog: note || "Nova versão" }),
        });
        stToast("Nova versão criada.", "success");
        renderAdminTabContent(box);
      });
    });
    box.querySelectorAll("[data-tpl-st]").forEach((b) => {
      b.addEventListener("click", async () => {
        await api(`/api/admin/templates/${b.dataset.tplSt}/status?status=${b.dataset.next}`, { method: "POST" });
        renderAdminTabContent(box);
      });
    });
    box.querySelectorAll("[data-tpl-dup]").forEach((b) => {
      b.addEventListener("click", async () => {
        await api(`/api/admin/templates/${b.dataset.tplDup}/duplicate`, { method: "POST" });
        stToast("Template duplicado.", "success");
        renderAdminTabContent(box);
      });
    });
  } else if (tab === "coupons") {
    const res = await api("/api/admin/coupons");
    box.innerHTML = `
      <form id="adm-cup-form" class="st-panel-card" style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:8px;">
        <input id="cp-code" class="st-input" placeholder="CÓDIGO" required />
        <select id="cp-type" class="st-select"><option value="percent">% Percentual</option><option value="fixed">R$ Fixo</option><option value="free_shipping">Frete Grátis</option></select>
        <input id="cp-val" class="st-input" type="number" step="0.01" value="15" />
        <input id="cp-min" class="st-input" type="number" step="0.01" placeholder="Mínimo R$" value="0" />
        <button type="submit" class="st-btn st-btn-gold">Criar</button>
      </form>
      <div class="st-table-wrap"><table class="st-table">
        <thead><tr><th>Código</th><th>Tipo</th><th>Valor</th><th>Mínimo</th><th>Usos</th><th>Status</th><th>Ação</th></tr></thead>
        <tbody>
          ${(res.coupons || []).map((c) => `
            <tr>
              <td><strong>${esc(c.code)}</strong></td>
              <td>${esc(c.discount_type)}</td>
              <td>${c.discount_value}</td>
              <td>${money(c.min_order_value)}</td>
              <td>${c.used_count}${c.max_uses ? ` / ${c.max_uses}` : ""}</td>
              <td>${c.is_active ? "Ativo" : "Inativo"}</td>
              <td><button class="st-btn st-btn-outline st-btn-xs" data-tog-cup="${c.id}">Alternar</button></td>
            </tr>
          `).join("")}
        </tbody>
      </table></div>
    `;
    box.querySelector("#adm-cup-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      await api("/api/admin/coupons", {
        method: "POST",
        body: JSON.stringify({
          code: document.getElementById("cp-code").value,
          discount_type: document.getElementById("cp-type").value,
          discount_value: Number(document.getElementById("cp-val").value),
          min_order_value: Number(document.getElementById("cp-min").value || 0),
        }),
      });
      stToast("Cupom criado.", "success");
      renderAdminTabContent(box);
    });
    box.querySelectorAll("[data-tog-cup]").forEach((b) => {
      b.addEventListener("click", async () => {
        await api(`/api/admin/coupons/${b.dataset.togCup}`, { method: "DELETE" });
        renderAdminTabContent(box);
      });
    });
  } else if (tab === "users") {
    const [uRes, rRes] = await Promise.all([api("/api/admin/users"), api("/api/admin/roles")]);
    const roles = rRes.roles || [];
    box.innerHTML = `
      <form id="adm-usr-form" class="st-panel-card" style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:8px;">
        <input id="au-name" class="st-input" placeholder="Nome" required />
        <input id="au-email" class="st-input" type="email" placeholder="E-mail" required />
        <input id="au-pass" class="st-input" type="password" placeholder="Senha" required />
        <select id="au-role" class="st-select">${roles.map((r) => `<option value="${r.id}">${esc(r.name)}</option>`).join("")}</select>
        <button type="submit" class="st-btn st-btn-gold">Criar</button>
      </form>
      <div class="st-table-wrap"><table class="st-table">
        <thead><tr><th>Usuário</th><th>E-mail</th><th>Cargo</th><th>Status</th><th>Alterar Cargo</th></tr></thead>
        <tbody>
          ${(uRes.users || []).map((u) => `
            <tr>
              <td><strong>${esc(u.name)}</strong></td>
              <td>${esc(u.email)}</td>
              <td>${esc(u.role_name)}</td>
              <td>${u.is_active ? "Ativo" : "Inativo"}</td>
              <td>
                <select class="st-select" style="height:34px;" data-usr-role="${u.id}">
                  ${roles.map((r) => `<option value="${r.id}" ${u.role_id === r.id ? "selected" : ""}>${esc(r.name)}</option>`).join("")}
                </select>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table></div>
    `;
    box.querySelector("#adm-usr-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          name: document.getElementById("au-name").value,
          email: document.getElementById("au-email").value,
          password: document.getElementById("au-pass").value,
          role_id: Number(document.getElementById("au-role").value),
        }),
      });
      stToast("Usuário criado.", "success");
      renderAdminTabContent(box);
    });
    box.querySelectorAll("[data-usr-role]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        await api(`/api/admin/users/${sel.dataset.usrRole}`, { method: "PUT", body: JSON.stringify({ role_id: Number(sel.value) }) });
        stToast("Cargo atualizado.", "success");
        renderAdminTabContent(box);
      });
    });
  } else if (tab === "roles") {
    const res = await api("/api/admin/roles");
    const modules = res.modules || {};
    const roles = res.roles || [];
    box.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:14px;">
        ${roles.map((r) => `
          <div class="st-panel-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
              <div><strong>${esc(r.name)}</strong> <span class="st-status-pill">${esc(r.slug)}</span><div style="font-size:12px;color:var(--st-ink-muted);margin-top:3px;">${esc(r.description)}</div></div>
              <div style="display:flex;gap:8px;">
                ${canPerm("permissions", "create") ? `<button class="st-btn st-btn-outline st-btn-xs" data-role-clone="${r.id}">Clonar</button>` : ""}
                ${canPerm("permissions", "edit") ? `<button class="st-btn st-btn-gold st-btn-xs" data-role-save="${r.id}">Salvar Matriz</button>` : ""}
              </div>
            </div>
            <div class="st-perm-matrix" data-role-box="${r.id}">
              ${Object.entries(modules).map(([modKey, meta]) => `
                <div class="st-perm-card">
                  <div style="font-size:12px;font-weight:600;margin-bottom:6px;">${esc(meta.label)}</div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    ${(meta.actions || []).map((act) => {
                      const chk = (r.permissions?.[modKey] || []).includes(act);
                      return `<label style="font-size:11.5px;display:flex;align-items:center;gap:4px;"><input type="checkbox" data-rmod="${modKey}" data-ract="${act}" ${chk ? "checked" : ""} />${esc(act)}</label>`;
                    }).join("")}
                  </div>
                </div>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </div>
    `;
    box.querySelectorAll("[data-role-clone]").forEach((b) => {
      b.addEventListener("click", async () => {
        const nm = prompt("Nome do novo cargo clonado:", "Supervisor Customizado");
        if (!nm) return;
        await api(`/api/admin/roles/${b.dataset.roleClone}/clone?new_name=${encodeURIComponent(nm)}`, { method: "POST" });
        stToast("Cargo clonado.", "success");
        renderAdminTabContent(box);
      });
    });
    box.querySelectorAll("[data-role-save]").forEach((b) => {
      b.addEventListener("click", async () => {
        const rid = Number(b.dataset.roleSave);
        const role = roles.find((x) => x.id === rid);
        const container = box.querySelector(`[data-role-box="${rid}"]`);
        const permissions = {};
        container.querySelectorAll("input[type=checkbox]:checked").forEach((cb) => {
          permissions[cb.dataset.rmod] = permissions[cb.dataset.rmod] || [];
          permissions[cb.dataset.rmod].push(cb.dataset.ract);
        });
        await api(`/api/admin/roles/${rid}`, { method: "PUT", body: JSON.stringify({ name: role.name, slug: role.slug, description: role.description, permissions }) });
        stToast("Matriz RBAC atualizada.", "success");
      });
    });
  } else if (tab === "settings") {
    const res = await api("/api/admin/settings");
    const s = res.settings || {};
    const id = s.store_identity || {};
    const hc = s.home_content || {};
    box.innerHTML = `
      <form id="adm-set-form" class="st-panel-card" style="display:flex;flex-direction:column;gap:12px;">
        <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0;">Identidade &amp; Textos da Home</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <input id="as-sname" class="st-input" value="${esc(id.store_name || "")}" placeholder="Nome da Loja" />
          <input id="as-tag" class="st-input" value="${esc(id.tagline || "")}" placeholder="Subtítulo" />
        </div>
        <input id="as-htitle" class="st-input" value="${esc(hc.hero_title || "")}" placeholder="Título Hero" />
        <textarea id="as-hsub" class="st-textarea" placeholder="Subtítulo Hero">${esc(hc.hero_subtitle || "")}</textarea>
        <button type="submit" class="st-btn st-btn-gold st-btn-sm" style="width:fit-content;">Salvar Configurações</button>
      </form>
    `;
    box.querySelector("#adm-set-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      await api("/api/admin/settings/store_identity", { method: "PUT", body: JSON.stringify({ ...id, store_name: document.getElementById("as-sname").value, tagline: document.getElementById("as-tag").value }) });
      await api("/api/admin/settings/home_content", { method: "PUT", body: JSON.stringify({ ...hc, hero_title: document.getElementById("as-htitle").value, hero_subtitle: document.getElementById("as-hsub").value }) });
      stState.homeData = null;
      stToast("Configurações atualizadas.", "success");
    });
  } else if (tab === "reports") {
    const res = await api("/api/admin/reports?export_format=json");
    const sum = res.summary || {};
    box.innerHTML = `
      <div class="st-panel-card" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
        <div><strong>Receita:</strong> ${money(sum.total_revenue)} • <strong>Pedidos:</strong> ${sum.total_orders} • <strong>Aprovação:</strong> ${sum.artwork_approval_rate}%</div>
        <div style="display:flex;gap:8px;">
          <button id="rep-csv" class="st-btn st-btn-outline st-btn-sm">${icon("download", 14)} Exportar CSV</button>
          <button id="rep-xlsx" class="st-btn st-btn-dark st-btn-sm">${icon("download", 14)} Exportar XLSX</button>
        </div>
      </div>
      <div class="st-table-wrap"><table class="st-table">
        <thead><tr><th>Pedido</th><th>Cliente</th><th>Status</th><th>Total</th><th>Cupom</th><th>Data</th></tr></thead>
        <tbody>${(res.rows || []).map((r) => `<tr><td>${esc(r.pedido)}</td><td>${esc(r.cliente)}</td><td>${esc(r.status)}</td><td>${money(r.total)}</td><td>${esc(r.cupom || "-")}</td><td>${esc(r.data)}</td></tr>`).join("")}</tbody>
      </table></div>
    `;
    box.querySelector("#rep-csv")?.addEventListener("click", () => downloadWithAuth("/api/admin/reports?export_format=csv", "relatorio_vendas.csv"));
    box.querySelector("#rep-xlsx")?.addEventListener("click", () => downloadWithAuth("/api/admin/reports?export_format=xlsx", "relatorio_vendas.xlsx"));
  } else if (tab === "support") {
    const res = await api("/api/admin/support");
    box.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:10px;">
        ${(res.tickets || []).map((t) => `
          <div class="st-panel-card">
            <strong>${esc(t.subject)}</strong> • ${esc(t.user_email)} <span class="st-status-pill">${esc(t.status)}</span>
            <p style="font-size:13px;margin:8px 0;">${esc(t.message)}</p>
            <div style="display:flex;gap:8px;margin-top:8px;">
              <input class="st-input" id="t-rep-${t.id}" placeholder="Responder ao cliente..." value="${esc(t.admin_reply || "")}" />
              <button class="st-btn st-btn-dark st-btn-sm" data-reply-tid="${t.id}">Responder</button>
            </div>
          </div>
        `).join("") || `<div class="st-panel-card">Nenhum chamado aberto.</div>`}
      </div>
    `;
    box.querySelectorAll("[data-reply-tid]").forEach((b) => {
      b.addEventListener("click", async () => {
        const reply = document.getElementById(`t-rep-${b.dataset.replyTid}`).value.trim();
        await api(`/api/admin/support/${b.dataset.replyTid}`, { method: "PUT", body: JSON.stringify({ status: "resolved", admin_reply: reply }) });
        stToast("Resposta enviada.", "success");
        renderAdminTabContent(box);
      });
    });
  } else if (tab === "audit") {
    const [aRes, mRes] = await Promise.all([
      canPerm("audit", "read") ? api("/api/admin/audit-logs") : Promise.resolve({ logs: [] }),
      canPerm("files", "read") ? api("/api/admin/media") : Promise.resolve({ files: [] }),
    ]);
    box.innerHTML = `
      <div class="st-panel-card">
        <h3 style="font-family:var(--font-editorial);font-size:21px;margin:0 0 10px;">Arquivos &amp; Mídia (${(mRes.files || []).length})</h3>
        <input id="adm-media-up" type="file" accept=".png,.jpg,.jpeg,.svg,.pdf" />
      </div>
      <div class="st-table-wrap"><table class="st-table">
        <thead><tr><th>Data</th><th>Ator</th><th>Ação</th><th>Recurso</th><th>Detalhes</th></tr></thead>
        <tbody>${(aRes.logs || []).slice(0, 40).map((l) => `<tr><td>${l.created_at ? new Date(l.created_at).toLocaleString("pt-BR") : ""}</td><td>${esc(l.actor_email)}</td><td>${esc(l.action)}</td><td>${esc(l.resource_type)} #${l.resource_id || ""}</td><td style="font-size:11px;">${esc(JSON.stringify(l.details))}</td></tr>`).join("")}</tbody>
      </table></div>
    `;
    box.querySelector("#adm-media-up")?.addEventListener("change", async (ev) => {
      const f = ev.target.files?.[0];
      if (!f) return;
      const fd = new FormData();
      fd.append("file", f);
      await api("/api/admin/media/upload?folder=store&is_private=false", { method: "POST", body: fd });
      stToast("Arquivo enviado.", "success");
      renderAdminTabContent(box);
    });
  }
}

export function openAuthModal(defaultTab = "login") {
  openStoreModal(`
    <div class="modal" style="max-width:460px;">
      <div class="modal-head">
        <h2>EditorGráfica Atelier</h2>
        <button class="btn btn-ghost btn-sm btn-icon" data-st-close>${icon("close", 16)}</button>
      </div>
      <div class="modal-body">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:18px;">
          <button class="st-btn st-btn-sm ${defaultTab === "login" ? "st-btn-dark" : "st-btn-soft"}" id="auth-tab-login">Entrar</button>
          <button class="st-btn st-btn-sm ${defaultTab === "register" ? "st-btn-dark" : "st-btn-soft"}" id="auth-tab-reg">Criar Conta</button>
        </div>

        <form id="auth-login-form" class="${defaultTab === "login" ? "" : "hidden"}" style="display:flex;flex-direction:column;gap:10px;">
          <input id="al-email" class="st-input" type="email" placeholder="Seu e-mail" required />
          <input id="al-pass" class="st-input" type="password" placeholder="Sua senha" required />
          <button type="submit" class="st-btn st-btn-gold" style="margin-top:4px;">Entrar na Conta</button>
          <div style="font-size:11.5px;color:var(--st-ink-muted);margin-top:8px;padding-top:12px;border-top:1px solid var(--st-border-subtle);">
            Acesso rápido de demonstração:
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
              <button type="button" class="st-btn st-btn-outline st-btn-xs" data-demo-login="cliente@editorgrafica.com.br|Cliente@2026">Cliente</button>
              <button type="button" class="st-btn st-btn-outline st-btn-xs" data-demo-login="admin@editorgrafica.com.br|Admin@2026">Admin</button>
              <button type="button" class="st-btn st-btn-outline st-btn-xs" data-demo-login="editor1@editorgrafica.com.br|Editor@2026">Editor N1</button>
              <button type="button" class="st-btn st-btn-outline st-btn-xs" data-demo-login="editor3@editorgrafica.com.br|Editor@2026">Editor N3</button>
            </div>
          </div>
        </form>

        <form id="auth-reg-form" class="${defaultTab === "register" ? "" : "hidden"}" style="display:flex;flex-direction:column;gap:10px;">
          <input id="ar-name" class="st-input" placeholder="Nome completo ou Empresa" required />
          <input id="ar-email" class="st-input" type="email" placeholder="E-mail" required />
          <input id="ar-pass" class="st-input" type="password" placeholder="Senha (mín. 6 caracteres)" minlength="6" required />
          <input id="ar-phone" class="st-input" placeholder="WhatsApp / Telefone" />
          <label style="font-size:12px;display:flex;gap:8px;align-items:flex-start;line-height:1.45;">
            <input id="ar-lgpd" type="checkbox" checked required style="margin-top:3px;" />
            Li e concordo com os Termos de Uso e Política de Privacidade (LGPD).
          </label>
          <button type="submit" class="st-btn st-btn-gold" style="margin-top:4px;">Cadastrar e Entrar</button>
        </form>
      </div>
    </div>
  `);

  const loginForm = document.getElementById("auth-login-form");
  const regForm = document.getElementById("auth-reg-form");
  const tLogin = document.getElementById("auth-tab-login");
  const tReg = document.getElementById("auth-tab-reg");

  tLogin?.addEventListener("click", () => {
    loginForm.classList.remove("hidden");
    regForm.classList.add("hidden");
    tLogin.className = "st-btn st-btn-sm st-btn-dark";
    tReg.className = "st-btn st-btn-sm st-btn-soft";
  });
  tReg?.addEventListener("click", () => {
    regForm.classList.remove("hidden");
    loginForm.classList.add("hidden");
    tReg.className = "st-btn st-btn-sm st-btn-dark";
    tLogin.className = "st-btn st-btn-sm st-btn-soft";
  });

  document.querySelectorAll("[data-demo-login]").forEach((b) => {
    b.addEventListener("click", () => {
      const [em, pw] = b.dataset.demoLogin.split("|");
      document.getElementById("al-email").value = em;
      document.getElementById("al-pass").value = pw;
    });
  });

  const completeAuth = async (data) => {
    stState.token = data.access_token;
    localStorage.setItem("eg_token", stState.token);
    closeStoreModal();
    await refreshUserAndCart();
    stToast(`Bem-vindo(a), ${stState.user?.name || ""}.`, "success");
    if (stState.pendingActionAfterAuth) {
      const fn = stState.pendingActionAfterAuth;
      stState.pendingActionAfterAuth = null;
      await fn();
    } else {
      await navigate(stState.route === "admin" && !stState.user?.is_staff ? "home" : stState.route, stState.routeParam);
    }
  };

  loginForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: document.getElementById("al-email").value, password: document.getElementById("al-pass").value }),
      });
      await completeAuth(data);
    } catch (err) {
      stToast(err.message, "error");
    }
  });

  regForm?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name: document.getElementById("ar-name").value,
          email: document.getElementById("ar-email").value,
          password: document.getElementById("ar-pass").value,
          phone: document.getElementById("ar-phone").value,
          lgpd_consent: document.getElementById("ar-lgpd").checked,
        }),
      });
      await completeAuth(data);
    } catch (err) {
      stToast(err.message, "error");
    }
  });
}
