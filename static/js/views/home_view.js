/* Página Inicial Editorial — EditorGráfica Atelier */

import { api, esc, navigate, stState } from "../core/api.js";
import { icon } from "../core/icons.js";
import { bindProductCardEvents, renderFooter, renderHeaderAuth, renderProductCardHtml } from "../components/header_footer.js";

const CAT_MOCKUP_BY_SLUG = {
  "agendas-diarias": "/uploads/demo/mockups/mockup_agenda.svg?v=5",
  "agendas-semanais": "/uploads/demo/mockups/mockup_semanal.svg?v=5",
  "agendas-permanentes": "/uploads/demo/mockups/mockup_permanente.svg?v=5",
  "agendas-financeiras": "/uploads/demo/mockups/mockup_financeiro.svg?v=5",
  "agendas-empresariais": "/uploads/demo/mockups/mockup_empresarial.svg?v=5",
  "agendas-medicas": "/uploads/demo/mockups/mockup_medica.svg?v=5",
  "planners": "/uploads/demo/mockups/mockup_planner.svg?v=5",
  "cadernetas": "/uploads/demo/mockups/mockup_moleskine.svg?v=5",
  "cadernos": "/uploads/demo/mockups/mockup_caderno.svg?v=5",
  "modelos-especiais": "/uploads/demo/mockups/mockup_organizador.svg?v=5",
  "planners-financeiros": "/uploads/demo/mockups/mockup_financeiro.svg?v=5",
  "semanais": "/uploads/demo/mockups/mockup_semanal.svg?v=5",
  "organizadores-pessoais": "/uploads/demo/mockups/mockup_organizador.svg?v=5",
};

function renderMiniStars(count = 5) {
  const starSvg = `<svg width="11" height="11" viewBox="0 0 24 24" fill="#0ABCBF" aria-hidden="true"><path d="M12 2.4l2.85 5.78 6.38.93-4.61 4.5 1.09 6.35L12 16.95l-5.71 3.01 1.09-6.35-4.61-4.5 6.38-.93L12 2.4z"/></svg>`;
  return `<span class="st-testi-stars" aria-label="${count} de 5 estrelas">${starSvg.repeat(count)}</span>`;
}

function getInitials(name = "") {
  const clean = String(name).replace(/\b(Dra\.|Dr\.|Sr\.|Sra\.)\s*/gi, "").trim();
  const parts = clean.split(/\s+/).filter(Boolean);
  if (!parts.length) return "EG";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export async function renderHomeView(main) {
  if (!stState.homeData) {
    stState.homeData = await api("/api/store/home");
    stState.categories = stState.homeData.categories || [];
    renderFooter();
    renderHeaderAuth();
  }
  const h = stState.homeData;
  const hc = h.home_content || {};
  const bannerImg = "/static/js/imgs/imgag.png?v=2";

  // Exibe 10 coleções completas (2 linhas equilibradas de 5 no desktop)
  const cats = (h.categories || []).slice(0, 10);
  const benefitIcons = ["award", "layers", "eye", "printer"];

  main.innerHTML = `
    <!-- 5.2 BANNER HERO PRINCIPAL (1672x941 PROPORÇÃO 16:9 NATIVA) -->
    <section class="st-hero st-hero-banner-section" aria-label="Destaque Principal EditorGráfica Pro">
      <div class="st-container">
        <div class="st-hero-banner-wrap">
          <img
            src="${esc(bannerImg)}"
            alt="EditorGráfica Pro — Agendas, Planners e Cadernetas Personalizadas"
            class="st-hero-banner-img"
            width="1672"
            height="941"
            fetchpriority="high"
          />
          <button
            type="button"
            class="st-banner-hotspot st-banner-hotspot-primary"
            id="st-hero-cta-primary"
            aria-label="Personalizar Agora"
            title="Personalizar Agora"
          ></button>
          <button
            type="button"
            class="st-banner-hotspot st-banner-hotspot-secondary"
            id="st-hero-cta-secondary"
            aria-label="Explorar Catálogo"
            title="Explorar Catálogo"
          ></button>
        </div>
        <div class="st-hero-mobile-actions">
          <button type="button" class="st-btn st-btn-gold" data-go-custom="1">
            Personalizar Agora ${icon("arrow-right", 15)}
          </button>
          <button type="button" class="st-btn st-btn-outline" data-go-cat="all">
            Explorar Catálogo
          </button>
        </div>
      </div>
    </section>

    <!-- FAIXA DE ACESSO RÁPIDO (ESTILO APP EM MOBILE & ATALHOS EDITORIAL NO DESKTOP) -->
    <section class="st-app-chips-bar" aria-label="Acesso rápido por coleção">
      <div class="st-container">
        <div class="st-app-chips">
          <button class="st-app-chip active" data-go-cat="all">Todas as Edições</button>
          <button class="st-app-chip" data-go-custom="1">Personalizáveis</button>
          ${(h.categories || []).slice(0, 6).map((c) => `
            <button class="st-app-chip" data-go-cat="${esc(c.slug)}">${esc(c.name)}</button>
          `).join("")}
        </div>
      </div>
    </section>

    <!-- 5.3 CATEGORIAS COM PROPORÇÕES PADRONIZADAS -->
    <section class="st-section">
      <div class="st-container">
        <div class="st-section-head">
          <div>
            <p class="st-eyebrow">Curadoria por Linha</p>
            <h2 class="st-section-title">Coleções do Atelier</h2>
            <p class="st-section-desc">Explore nossas linhas de papelaria profissional com opções prontas ou configuráveis.</p>
          </div>
          <button class="st-btn st-btn-outline st-btn-sm" data-go-cat="all">
            Ver Catálogo Completo ${icon("arrow-right", 14)}
          </button>
        </div>

        <div class="st-cat-grid">
          ${cats.map((c) => {
            const rawImgUrl = c.image_url || CAT_MOCKUP_BY_SLUG[c.slug] || "/uploads/demo/mockups/mockup_agenda.svg";
            const imgUrl = rawImgUrl.includes("/uploads/demo/mockups/") && !rawImgUrl.includes("?") ? `${rawImgUrl}?v=5` : rawImgUrl;
            return `
              <article class="st-cat-card" data-go-cat="${esc(c.slug)}">
                <div class="st-cat-thumb">
                  <img src="${esc(imgUrl)}" alt="${esc(c.name)}" loading="lazy" />
                </div>
                <div class="st-cat-body">
                  <h3>${esc(c.name)}</h3>
                  <p>${esc(c.description || "Acabamento editorial em papel nobre e impressão de alta precisão.")}</p>
                  <span class="st-cat-link">Explorar ${icon("arrow-right", 13)}</span>
                </div>
              </article>
            `;
          }).join("")}
        </div>
      </div>
    </section>

    <!-- 5.4 MAIS VENDIDOS & DESTAQUES DE CATÁLOGO -->
    <section class="st-section st-section-alt">
      <div class="st-container">
        <div class="st-section-head">
          <div>
            <p class="st-eyebrow">Seleção Editorial</p>
            <h2 class="st-section-title">Mais Vendidos &amp; Destaques</h2>
            <p class="st-section-desc">Modelos favoritos de clínicas, escritórios e profissionais que exigem acabamento impecável.</p>
          </div>
          <button class="st-btn st-btn-soft st-btn-sm" data-go-custom="1">
            Somente Personalizáveis ${icon("sliders", 14)}
          </button>
        </div>

        <div class="st-products-grid" id="st-home-featured">
          ${(h.featured_products || []).slice(0, 8).map(renderProductCardHtml).join("")}
        </div>
      </div>
    </section>

    <!-- 5.5 SEÇÃO ESPECIAL: UMA AGENDA COM A SUA IDENTIDADE -->
    <section class="st-section">
      <div class="st-container">
        <div class="st-identity-grid">
          <div class="st-identity-showcase">
            <div class="st-identity-thumbs">
              <img src="/uploads/demo/mockups/mockup_agenda.svg?v=5" alt="Agenda Executiva Personalizada" />
              <img src="/uploads/demo/mockups/mockup_moleskine.svg?v=5" alt="Caderneta Corporativa com Marca" />
            </div>
            <div class="st-swatch-strip">
              <span>Cartela CMYK &amp; Revestimentos Selecionados</span>
              <div class="st-swatches" aria-hidden="true">
                <span style="background:#0ABCBF;" title="Ciano Atelier"></span>
                <span style="background:#089E9F;" title="Teal Studio"></span>
                <span style="background:#0E5A63;" title="Petróleo Editorial"></span>
                <span style="background:#E5C17B;" title="Foil Dourado"></span>
                <span style="background:#182228;" title="Grafite Neutro"></span>
              </div>
            </div>
          </div>

          <div>
            <p class="st-eyebrow">Estúdio Gráfico Integrado</p>
            <h2 class="st-section-title" style="font-size:clamp(32px,3.6vw,44px);">Uma agenda com a sua identidade.</h2>
            <p class="st-section-desc" style="margin-top:14px;">
              Configure o miolo conforme sua rotina ou marca: escolha datas de início, feriados regionais, paletas cromáticas CMYK, pauta escrita, frases inspiracionais e logotipo no rodapé com conferência em tempo real.
            </p>

            <div class="st-identity-pillars">
              <div class="st-identity-pillar">
                <span class="st-identity-pillar-ico">${icon("book", 17)}</span>
                <div>
                  <strong>Calendário &amp; Pauta Sob Medida</strong>
                  <span>Diário 1 DPP, semanal, permanente ou financeiro sem datas duplicadas.</span>
                </div>
              </div>
              <div class="st-identity-pillar">
                <span class="st-identity-pillar-ico">${icon("sliders", 17)}</span>
                <div>
                  <strong>Paletas CMYK &amp; Marca no Rodapé</strong>
                  <span>Insira logotipo e ajuste cores de títulos, linhas e feriados antes de imprimir.</span>
                </div>
              </div>
              <div class="st-identity-pillar">
                <span class="st-identity-pillar-ico">${icon("shield", 17)}</span>
                <div>
                  <strong>Validação Pré-Impressão &amp; Aprovação Online</strong>
                  <span>Verificação automática de margens de segurança, sangria de 3 mm e prévia fiel em PDF.</span>
                </div>
              </div>
            </div>

            <div style="display:flex;gap:12px;flex-wrap:wrap;">
              <button class="st-btn st-btn-dark st-btn-lg" id="st-identity-cta">
                Abrir Modelos Personalizáveis ${icon("arrow-right", 16)}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 5.6 INSTITUCIONAL: DIFERENCIAIS DA MARCA -->
    <section class="st-section st-section-alt">
      <div class="st-container">
        <div class="st-section-head">
          <div>
            <p class="st-eyebrow">Padrão Gráfico</p>
            <h2 class="st-section-title">Por que o Atelier EditorGráfica</h2>
            <p class="st-section-desc">Tecnologia de pré-impressão combinada ao cuidado artesanal de papelarias europeias.</p>
          </div>
        </div>

        <div class="st-benefits-grid">
          ${(hc.benefits || []).slice(0, 4).map((b, idx) => `
            <div class="st-benefit-card">
              <span class="st-benefit-ico">${icon(benefitIcons[idx % benefitIcons.length], 18)}</span>
              <h3>${esc(b.title)}</h3>
              <p>${esc(b.desc)}</p>
            </div>
          `).join("")}
        </div>
      </div>
    </section>

    <!-- RELATOS DE CLIENTES DISCRETOS & PERGUNTAS FREQUENTES -->
    <section class="st-section st-section-compact">
      <div class="st-container">
        <div class="st-testi-minimal-block">
          <div class="st-testi-minimal-head">
            <div>
              <span class="st-testi-kicker">Confiança Profissional</span>
              <h2 class="st-testi-minimal-title">Relatos de Clientes</h2>
            </div>
            <div class="st-testi-rating-chip">
              ${renderMiniStars(5)}
              <span><strong>4.9/5</strong> • Avaliação Verificada</span>
            </div>
          </div>

          <div class="st-testi-minimal-grid">
            ${(hc.testimonials || []).map((t) => `
              <article class="st-testi-card">
                <div class="st-testi-card-top">
                  ${renderMiniStars(5)}
                  <span class="st-testi-verified">Verificado</span>
                </div>
                <p class="st-testi-quote">${esc(t.quote)}</p>
                <footer class="st-testi-author">
                  <span class="st-testi-avatar" aria-hidden="true">${esc(getInitials(t.author))}</span>
                  <div class="st-testi-author-info">
                    <strong>${esc(t.author)}</strong>
                    <span>${esc(t.role)}</span>
                  </div>
                </footer>
              </article>
            `).join("")}
          </div>
        </div>

        <div class="st-faq-block">
          <div class="st-testi-minimal-head" style="margin-bottom:18px;">
            <div>
              <span class="st-testi-kicker">Esclarecimentos</span>
              <h2 class="st-testi-minimal-title">Perguntas Frequentes</h2>
            </div>
          </div>
          <div class="st-faq-grid">
            ${(hc.faqs || []).map((f, idx) => `
              <details class="st-faq-item" ${idx === 0 ? "open" : ""}>
                <summary>
                  <span>${esc(f.q)}</span>
                  ${icon("chevron-down", 15)}
                </summary>
                <p>${esc(f.a)}</p>
              </details>
            `).join("")}
          </div>
        </div>
      </div>
    </section>
  `;

  main.querySelector("#st-hero-cta-primary")?.addEventListener("click", () => {
    stState.filters.only_customizable = true;
    stState.filters.category = "all";
    navigate("catalog");
  });
  main.querySelector("#st-hero-cta-secondary")?.addEventListener("click", () => {
    stState.filters.only_customizable = false;
    stState.filters.category = "all";
    navigate("catalog");
  });
  main.querySelector("#st-identity-cta")?.addEventListener("click", () => {
    stState.filters.only_customizable = true;
    stState.filters.category = "all";
    navigate("catalog");
  });
  main.querySelectorAll("[data-go-cat]").forEach((el) => {
    el.addEventListener("click", () => {
      stState.filters.category = el.dataset.goCat;
      stState.filters.only_customizable = false;
      navigate("catalog");
    });
  });
  main.querySelectorAll("[data-go-custom]").forEach((el) => {
    el.addEventListener("click", () => {
      stState.filters.only_customizable = true;
      stState.filters.category = "all";
      navigate("catalog");
    });
  });
  bindProductCardEvents(main);
}
