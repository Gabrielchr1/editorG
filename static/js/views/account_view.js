/* Área do Cliente Editorial — Pedidos, Aprovação de Arte, Projetos, Arquivos e LGPD */

import {
  api,
  downloadWithAuth,
  esc,
  money,
  navigate,
  refreshUserAndCart,
  statusPillHtml,
  stState,
  stToast,
  triggerAuthModal,
} from "../core/api.js";
import { icon } from "../core/icons.js";
import { bindProductCardEvents, renderProductCardHtml } from "../components/header_footer.js";

export async function renderAccountView(main) {
  if (!stState.user) {
    triggerAuthModal("login");
    main.innerHTML = `
      <section class="st-section-compact">
        <div class="st-container"><div class="st-panel-card">Entre na sua conta para acessar seus pedidos, projetos e aprovações.</div></div>
      </section>
    `;
    return;
  }

  const tabs = [
    ["overview", "Resumo da Conta", "user"],
    ["orders", "Meus Pedidos & Arte", "bag"],
    ["projects", "Projetos Salvos", "sliders"],
    ["files", "Meus Arquivos", "file-text"],
    ["favorites", "Favoritos", "heart"],
    ["addresses", "Endereços", "mappin"],
    ["notifications", "Notificações", "bell"],
    ["support", "Atendimento", "help"],
    ["lgpd", "Privacidade (LGPD)", "shield"],
  ];

  main.innerHTML = `
    <section class="st-section-compact">
      <div class="st-container">
        <div class="st-section-head" style="margin-bottom:28px;">
          <div>
            <p class="st-eyebrow">Área do Cliente</p>
            <h1 class="st-section-title">Olá, ${esc(stState.user.name)}</h1>
            <p class="st-section-desc">${esc(stState.user.email)} • Perfil ${esc(stState.user.role_name)}</p>
          </div>
          <button id="acc-logout" class="st-btn st-btn-outline st-btn-sm">Sair da Conta</button>
        </div>

        <div class="st-account-shell">
          <aside class="st-side-menu">
            ${tabs.map(([id, lbl, ico]) => `
              <button class="st-side-btn ${stState.accountTab === id ? "active" : ""}" data-acc-tab="${id}">
                ${icon(ico, 15)} <span>${esc(lbl)}</span>
              </button>
            `).join("")}
          </aside>
          <div id="acc-content"></div>
        </div>
      </div>
    </section>
  `;

  main.querySelector("#acc-logout").addEventListener("click", async () => {
    stState.token = "";
    stState.user = null;
    localStorage.removeItem("eg_token");
    await refreshUserAndCart();
    navigate("home");
  });

  main.querySelectorAll("[data-acc-tab]").forEach((b) => {
    b.addEventListener("click", () => {
      stState.accountTab = b.dataset.accTab;
      stState.selectedOrderDetail = null;
      renderAccountView(main);
    });
  });

  await renderAccountTabContent(main.querySelector("#acc-content"));
}

async function renderAccountTabContent(box) {
  const tab = stState.accountTab;
  if (tab === "overview") {
    const d = await api("/api/account/dashboard");
    const k = d.kpis || {};
    box.innerHTML = `
      <div class="st-kpi-grid">
        <div class="st-kpi-card"><div class="st-kpi-lbl">Total de Pedidos</div><div class="st-kpi-val">${k.total_orders || 0}</div></div>
        <div class="st-kpi-card"><div class="st-kpi-lbl">Em Andamento</div><div class="st-kpi-val">${k.orders_in_progress || 0}</div></div>
        <div class="st-kpi-card"><div class="st-kpi-lbl">Rascunhos Salvos</div><div class="st-kpi-val">${k.unfinished_projects || 0}</div></div>
        <div class="st-kpi-card"><div class="st-kpi-lbl">Concluídos</div><div class="st-kpi-val">${k.orders_completed || 0}</div></div>
      </div>
      <div class="st-panel-card">
        <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0 0 14px;">Pedidos Recentes</h3>
        ${(d.recent_orders || []).length ? d.recent_orders.map((o) => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--st-border-subtle);flex-wrap:wrap;gap:10px;">
            <div><strong>${esc(o.order_number)}</strong> • ${money(o.total_amount)}</div>
            <div style="display:flex;gap:10px;align-items:center;">
              ${statusPillHtml(o.status)}
              <button class="st-btn st-btn-outline st-btn-xs" data-acc-view-ord="${o.id}">Detalhes</button>
            </div>
          </div>
        `).join("") : `<p style="color:var(--st-ink-muted);margin:0;">Você ainda não possui pedidos registrados.</p>`}
      </div>
    `;
    box.querySelectorAll("[data-acc-view-ord]").forEach((b) => {
      b.addEventListener("click", () => {
        stState.selectedOrderDetail = Number(b.dataset.accViewOrd);
        stState.accountTab = "orders";
        renderAccountView(document.getElementById("store-main"));
      });
    });
  } else if (tab === "orders") {
    if (stState.selectedOrderDetail) {
      const ordRes = await api(`/api/account/orders/${stState.selectedOrderDetail}`);
      const o = ordRes.order || ordRes;
      box.innerHTML = `
        <div class="st-panel-card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:12px;">
            <div>
              <button id="ord-back-list" class="st-btn st-btn-soft st-btn-xs" style="margin-bottom:10px;">
                ${icon("arrow-left", 13)} Todos os Pedidos
              </button>
              <h2 style="font-family:var(--font-editorial);font-size:28px;margin:0;">Pedido ${esc(o.order_number)}</h2>
            </div>
            <div style="text-align:right;">
              ${statusPillHtml(o.status)}
              <div style="margin-top:6px;font-weight:600;font-size:17px;">${money(o.total_amount)}</div>
            </div>
          </div>

          ${(o.items || []).map((it) => `
            <div class="st-panel-card" style="margin-bottom:14px;background:var(--st-surface-soft);padding:18px;">
              <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;align-items:center;">
                <div>
                  <strong style="font-size:15px;">${it.quantity}× ${esc(it.product_name)}</strong> ${it.variation_name ? `(${esc(it.variation_name)})` : ""}
                  <div style="font-size:12px;color:var(--st-ink-muted);margin-top:3px;">
                    Arte: <strong>${esc(it.artwork_status)}</strong> ${it.project_version ? `• Versão v${it.project_version}` : ""}
                  </div>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
                  ${it.preview_file_id ? `<a class="st-btn st-btn-outline st-btn-xs" href="/api/files/${it.preview_file_id}/download?inline=true&token=${encodeURIComponent(stState.token)}" target="_blank">${icon("eye", 13)} Ver Prévia PDF</a>` : ""}
                  ${it.project_id ? `<button class="st-btn st-btn-soft st-btn-xs" data-reopen-proj="${it.project_id}">${icon("edit", 13)} Abrir no Estúdio</button>` : ""}
                  ${it.is_customized && it.artwork_status !== "approved" ? `
                    <button class="st-btn st-btn-gold st-btn-xs" data-art-approve="${it.id}">${icon("check", 13)} Aprovar Arte</button>
                    <button class="st-btn st-btn-outline st-btn-xs" data-art-reject="${it.id}">Solicitar Ajustes</button>
                  ` : ""}
                </div>
              </div>
              ${it.preflight_report?.summary ? `<div style="font-size:12px;margin-top:10px;color:var(--st-ink-muted);">Pré-impressão: ${it.preflight_report.ok ? "Aprovado tecnicamente" : "Com alertas"} (${esc(it.preflight_report.summary)})</div>` : ""}
            </div>
          `).join("")}

          <h4 style="font-family:var(--font-editorial);font-size:20px;margin:20px 0 12px;">Linha do Tempo de Produção</h4>
          <div class="st-timeline">
            ${(o.timeline || []).map((t) => `
              <div class="st-timeline-step">
                <div style="font-weight:600;font-size:13.5px;">${esc(t.to_label)}</div>
                <div style="font-size:12px;color:var(--st-ink-muted);">${esc(t.note)} • ${t.created_at ? new Date(t.created_at).toLocaleString("pt-BR") : ""}</div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
      box.querySelector("#ord-back-list")?.addEventListener("click", () => {
        stState.selectedOrderDetail = null;
        renderAccountTabContent(box);
      });
      box.querySelectorAll("[data-reopen-proj]").forEach((b) => {
        b.addEventListener("click", () => window.EGEditor?.openCustomerProjectInEditor(Number(b.dataset.reopenProj)));
      });
      box.querySelectorAll("[data-art-approve]").forEach((b) => {
        b.addEventListener("click", async () => {
          await api(`/api/account/orders/${o.id}/items/${Number(b.dataset.artApprove)}/artwork-decision`, {
            method: "POST",
            body: JSON.stringify({ decision: "approved", comments: "Arte conferida e aprovada pelo cliente." }),
          });
          stToast("Arte aprovada com sucesso.", "success");
          renderAccountTabContent(box);
        });
      });
      box.querySelectorAll("[data-art-reject]").forEach((b) => {
        b.addEventListener("click", async () => {
          const comments = prompt("Descreva os ajustes desejados na arte:");
          if (!comments) return;
          await api(`/api/account/orders/${o.id}/items/${Number(b.dataset.artReject)}/artwork-decision`, {
            method: "POST",
            body: JSON.stringify({ decision: "changes_requested", comments }),
          });
          stToast("Solicitação de correção registrada.", "info");
          renderAccountTabContent(box);
        });
      });
      return;
    }

    const res = await api("/api/account/orders");
    box.innerHTML = `
      <div class="st-table-wrap">
        <table class="st-table">
          <thead><tr><th>Pedido</th><th>Data</th><th>Status</th><th>Pagamento</th><th>Total</th><th>Ações</th></tr></thead>
          <tbody>
            ${(res.orders || []).length ? res.orders.map((o) => `
              <tr>
                <td><strong>${esc(o.order_number)}</strong></td>
                <td>${o.created_at ? new Date(o.created_at).toLocaleDateString("pt-BR") : "-"}</td>
                <td>${statusPillHtml(o.status)}</td>
                <td>${esc(o.payment_status)} (${esc(o.payment_method)})</td>
                <td><strong>${money(o.total_amount)}</strong></td>
                <td><button class="st-btn st-btn-outline st-btn-xs" data-ord-open="${o.id}">Acompanhar</button></td>
              </tr>
            `).join("") : `<tr><td colspan="6" style="color:var(--st-ink-muted);">Nenhum pedido encontrado.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
    box.querySelectorAll("[data-ord-open]").forEach((b) => {
      b.addEventListener("click", () => {
        stState.selectedOrderDetail = Number(b.dataset.ordOpen);
        renderAccountTabContent(box);
      });
    });
  } else if (tab === "projects") {
    const res = await api("/api/account/projects");
    box.innerHTML = `
      <div class="st-table-wrap">
        <table class="st-table">
          <thead><tr><th>Projeto</th><th>Formato</th><th>Páginas</th><th>Versão</th><th>Status</th><th>Ação</th></tr></thead>
          <tbody>
            ${(res.projects || []).length ? res.projects.map((p) => `
              <tr>
                <td><strong>${esc(p.name)}</strong></td>
                <td>${esc(p.format_name)}</td>
                <td>${p.page_count}</td>
                <td>v${p.version || 1}</td>
                <td>${esc(p.status)}</td>
                <td><button class="st-btn st-btn-gold st-btn-xs" data-open-cust-proj="${p.id}">Abrir no Estúdio</button></td>
              </tr>
            `).join("") : `<tr><td colspan="6" style="color:var(--st-ink-muted);">Você ainda não salvou projetos personalizados.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
    box.querySelectorAll("[data-open-cust-proj]").forEach((b) => {
      b.addEventListener("click", () => window.EGEditor?.openCustomerProjectInEditor(Number(b.dataset.openCustProj)));
    });
  } else if (tab === "files") {
    const res = await api("/api/account/files");
    box.innerHTML = `
      <div class="st-table-wrap">
        <table class="st-table">
          <thead><tr><th>Arquivo</th><th>Pasta</th><th>Versão</th><th>Tamanho</th><th>Download</th></tr></thead>
          <tbody>
            ${(res.files || []).length ? res.files.map((f) => `
              <tr>
                <td><strong>${esc(f.original_name)}</strong></td>
                <td>${esc(f.folder)}</td>
                <td>v${f.version}</td>
                <td>${Math.round((f.size_bytes || 0) / 1024)} KB</td>
                <td><button class="st-btn st-btn-outline st-btn-xs" data-dl-fid="${f.id}" data-dl-name="${esc(f.original_name)}">${icon("download", 13)} Baixar</button></td>
              </tr>
            `).join("") : `<tr><td colspan="5" style="color:var(--st-ink-muted);">Nenhum arquivo vinculado ainda.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
    box.querySelectorAll("[data-dl-fid]").forEach((b) => {
      b.addEventListener("click", async () => {
        try {
          await downloadWithAuth(`/api/files/${b.dataset.dlFid}/download`, b.dataset.dlName);
        } catch (err) {
          stToast(err.message, "error");
        }
      });
    });
  } else if (tab === "favorites") {
    const res = await api("/api/account/favorites");
    box.innerHTML = `<div class="st-products-grid cols-3">${(res.favorites || []).map(renderProductCardHtml).join("") || `<div class="st-panel-card" style="grid-column:1/-1;">Nenhum produto favoritado ainda.</div>`}</div>`;
    bindProductCardEvents(box);
  } else if (tab === "addresses") {
    const res = await api("/api/account/addresses");
    box.innerHTML = `
      <div class="st-panel-card">
        <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0 0 14px;">Endereços Cadastrados</h3>
        ${(res.addresses || []).map((a) => `<div style="padding:10px 0;border-bottom:1px solid var(--st-border-subtle);"><strong>${esc(a.label)}</strong> — ${esc(a.recipient_name)} • ${esc(a.street)}, ${esc(a.number)} - ${esc(a.city)}/${esc(a.state)} (${esc(a.zip_code)})</div>`).join("") || `<p style="color:var(--st-ink-muted);margin:0;">Nenhum endereço cadastrado.</p>`}
      </div>
      <form id="acc-addr-form" class="st-panel-card" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <input id="aa-lbl" class="st-input" placeholder="Apelido (Casa/Atelier)" value="Principal" />
        <input id="aa-rec" class="st-input" placeholder="Destinatário" required />
        <input id="aa-cep" class="st-input" placeholder="CEP" required />
        <input id="aa-st" class="st-input" placeholder="Rua / Logradouro" required />
        <input id="aa-num" class="st-input" placeholder="Número" required />
        <input id="aa-city" class="st-input" placeholder="Cidade" required />
        <input id="aa-uf" class="st-input" placeholder="UF" maxlength="2" required />
        <button type="submit" class="st-btn st-btn-dark">Salvar Endereço</button>
      </form>
    `;
    box.querySelector("#acc-addr-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      await api("/api/account/addresses", {
        method: "POST",
        body: JSON.stringify({
          label: document.getElementById("aa-lbl").value,
          recipient_name: document.getElementById("aa-rec").value,
          zip_code: document.getElementById("aa-cep").value,
          street: document.getElementById("aa-st").value,
          number: document.getElementById("aa-num").value,
          city: document.getElementById("aa-city").value,
          state: document.getElementById("aa-uf").value.toUpperCase(),
        }),
      });
      stToast("Endereço cadastrado.", "success");
      renderAccountTabContent(box);
    });
  } else if (tab === "notifications") {
    const res = await api("/api/account/notifications");
    box.innerHTML = `
      <div class="st-panel-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
          <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0;">Notificações</h3>
          <button id="not-read-all" class="st-btn st-btn-outline st-btn-xs">Marcar todas como lidas</button>
        </div>
        ${(res.notifications || []).map((n) => `
          <div style="padding:12px 0;border-bottom:1px solid var(--st-border-subtle);opacity:${n.is_read ? "0.62" : "1"};">
            <strong>${esc(n.title)}</strong>
            <div style="font-size:13px;color:var(--st-ink-muted);margin-top:2px;">${esc(n.message)}</div>
          </div>
        `).join("") || `<p style="color:var(--st-ink-muted);margin:0;">Nenhuma notificação.</p>`}
      </div>
    `;
    box.querySelector("#not-read-all")?.addEventListener("click", async () => {
      await api("/api/account/notifications/read-all", { method: "POST" });
      renderAccountTabContent(box);
    });
  } else if (tab === "support") {
    const res = await api("/api/account/support");
    box.innerHTML = `
      <form id="sup-form" class="st-panel-card" style="display:flex;flex-direction:column;gap:12px;">
        <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0;">Novo Chamado</h3>
        <input id="sup-sub" class="st-input" placeholder="Assunto (mín. 3 caracteres)" required />
        <textarea id="sup-msg" class="st-textarea" placeholder="Descreva sua dúvida sobre pedido ou personalização..." required></textarea>
        <button type="submit" class="st-btn st-btn-dark st-btn-sm" style="width:fit-content;">Enviar Mensagem</button>
      </form>
      <div class="st-panel-card">
        ${(res.tickets || []).map((t) => `
          <div style="padding:12px 0;border-bottom:1px solid var(--st-border-subtle);">
            <strong>${esc(t.subject)}</strong> <span class="st-status-pill">${esc(t.status)}</span>
            <p style="font-size:13px;margin:6px 0;">${esc(t.message)}</p>
            ${t.admin_reply ? `<div style="font-size:12.5px;color:var(--st-gold-deep);">Resposta: ${esc(t.admin_reply)}</div>` : ""}
          </div>
        `).join("") || `<p style="color:var(--st-ink-muted);margin:0;">Nenhum chamado aberto.</p>`}
      </div>
    `;
    box.querySelector("#sup-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      await api("/api/account/support", {
        method: "POST",
        body: JSON.stringify({ subject: document.getElementById("sup-sub").value, message: document.getElementById("sup-msg").value }),
      });
      stToast("Chamado registrado.", "success");
      renderAccountTabContent(box);
    });
  } else if (tab === "lgpd") {
    box.innerHTML = `
      <div class="st-panel-card">
        <h3 style="font-family:var(--font-editorial);font-size:22px;margin:0 0 10px;">Privacidade &amp; Direitos LGPD</h3>
        <p style="font-size:13.5px;color:var(--st-ink-muted);margin:0 0 18px;line-height:1.6;">Exporte todos os seus dados cadastrais, endereços, pedidos e projetos em JSON, ou solicite a anonimização definitiva da conta.</p>
        <div style="display:flex;gap:12px;flex-wrap:wrap;">
          <button id="lgpd-dl" class="st-btn st-btn-dark st-btn-sm">${icon("download", 14)} Exportar Meus Dados (JSON)</button>
          <button id="lgpd-anon" class="st-btn st-btn-outline st-btn-sm" style="color:var(--st-danger);border-color:var(--st-danger);">Anonimizar Minha Conta</button>
        </div>
      </div>
    `;
    box.querySelector("#lgpd-dl").addEventListener("click", () => downloadWithAuth("/api/lgpd/my-data", "meus_dados_lgpd.json"));
    box.querySelector("#lgpd-anon").addEventListener("click", async () => {
      if (!confirm("Confirma a anonimização permanente da sua conta conforme a LGPD?")) return;
      await api("/api/lgpd/anonymize", { method: "POST" });
      stState.token = "";
      stState.user = null;
      localStorage.removeItem("eg_token");
      await refreshUserAndCart();
      stToast("Dados anonimizados.", "success");
      navigate("home");
    });
  }
}
