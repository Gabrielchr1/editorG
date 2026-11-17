"""Suíte completa de testes de E-Commerce, RBAC, Segurança, Permissões e Fluxo de Produção."""

from __future__ import annotations

import copy
import hashlib
import hmac
import io
import json
import os
from pathlib import Path

os.environ["EG_DISABLE_RATE_LIMIT"] = "1"

import httpx
import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import ecommerce_routes
from backend.auth_rbac import EDITOR_TOOL_LABELS, get_webhook_secret
from backend.database import get_db, run_migrations
from backend.ecommerce_seed import seed_ecommerce_data
from backend.seed_data import seed_initial_data
from main import app


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch):
    """Fornece banco SQLite isolado e storage privado temporário sem poluir a base principal."""
    db_file = tmp_path / "ecommerce_test.db"
    eng = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    run_migrations(eng)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=eng)

    db = TestSession()
    try:
        seed_initial_data(db)
        seed_ecommerce_data(db)
    finally:
        db.close()

    def _override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    priv_dir = tmp_path / "storage_private"
    priv_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ecommerce_routes, "BASE_DIR", tmp_path)
    monkeypatch.setattr(ecommerce_routes, "PRIVATE_STORAGE_DIR", priv_dir)
    monkeypatch.setattr(ecommerce_routes, "SessionLocal", TestSession)
    app.dependency_overrides[get_db] = _override_get_db

    try:
        yield TestSession, priv_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        eng.dispose()


async def _login(client: httpx.AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _auth_hdr(token: str, extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if extra:
        h.update(extra)
    return h


def _sign_webhook(payload_dict: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(get_webhook_secret().encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, f"sha256={sig}"


@pytest.mark.asyncio
async def test_rbac_levels_role_cloning_user_overrides_and_audit(isolated_env):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        adm = await _login(client, "admin@editorgrafica.com.br", "Admin@2026")
        cust = await _login(client, "cliente@editorgrafica.com.br", "Cliente@2026")
        ed1 = await _login(client, "editor1@editorgrafica.com.br", "Editor@2026")
        ed2 = await _login(client, "editor2@editorgrafica.com.br", "Editor@2026")
        ed3 = await _login(client, "editor3@editorgrafica.com.br", "Editor@2026")
        ed4 = await _login(client, "editor4@editorgrafica.com.br", "Editor@2026")

        # Cliente bloqueado em rotas administrativas e produção
        assert (await client.get("/api/admin/roles", headers=_auth_hdr(cust["access_token"]))).status_code == 403
        assert (await client.get("/api/admin/products", headers=_auth_hdr(cust["access_token"]))).status_code == 403
        assert (await client.get("/api/production/queue", headers=_auth_hdr(cust["access_token"]))).status_code == 403

        # Editor 1 lê fila, mas não lê cupons nem matriz RBAC
        assert (await client.get("/api/production/queue", headers=_auth_hdr(ed1["access_token"]))).status_code == 200
        assert (await client.get("/api/admin/coupons", headers=_auth_hdr(ed1["access_token"]))).status_code == 403
        assert (await client.get("/api/admin/roles", headers=_auth_hdr(ed1["access_token"]))).status_code == 403

        # Editor 2 publica templates, mas não cria produtos nem acessa relatórios
        assert (await client.post("/api/admin/templates/1/status?status=published", headers=_auth_hdr(ed2["access_token"]))).status_code == 200
        assert (await client.get("/api/admin/reports", headers=_auth_hdr(ed2["access_token"]))).status_code == 403

        # Editor 3 tem categorias/produtos/suporte, Editor 4 tem relatórios e cupons
        assert (await client.get("/api/admin/support", headers=_auth_hdr(ed3["access_token"]))).status_code == 200
        assert (await client.get("/api/admin/reports", headers=_auth_hdr(ed3["access_token"]))).status_code == 403
        assert (await client.get("/api/admin/reports", headers=_auth_hdr(ed4["access_token"]))).status_code == 200

        # Clonagem de cargo pelo Admin
        roles_res = await client.get("/api/admin/roles", headers=_auth_hdr(adm["access_token"]))
        assert roles_res.status_code == 200
        roles = roles_res.json()["roles"]
        ed2_role = next(r for r in roles if r["slug"] == "editor_2")
        r_clone = await client.post(
            f"/api/admin/roles/{ed2_role['id']}/clone?new_name=Auditor%20Produção",
            headers=_auth_hdr(adm["access_token"]),
        )
        assert r_clone.status_code == 201
        assert r_clone.json()["name"] == "Auditor Produção"

        # Override individual: libera coupons:read para Editor 1
        ed1_uid = ed1["user"]["id"]
        r_ovr = await client.put(
            f"/api/admin/users/{ed1_uid}",
            headers=_auth_hdr(adm["access_token"]),
            json={"custom_permissions": {"grant": {"coupons": ["read"]}, "deny": {}}},
        )
        assert r_ovr.status_code == 200
        assert (await client.get("/api/admin/coupons", headers=_auth_hdr(ed1["access_token"]))).status_code == 200

        # Override deny: revoga reports:read de Editor 4
        r_deny = await client.put(
            f"/api/admin/users/{ed4['user']['id']}",
            headers=_auth_hdr(adm["access_token"]),
            json={"custom_permissions": {"grant": {}, "deny": {"reports": ["read"]}}},
        )
        assert r_deny.status_code == 200
        assert (await client.get("/api/admin/reports", headers=_auth_hdr(ed4["access_token"]))).status_code == 403

        # Logs de auditoria registraram ações RBAC
        logs_res = await client.get("/api/admin/audit-logs", headers=_auth_hdr(adm["access_token"]))
        assert logs_res.status_code == 200
        actions = {l["action"] for l in logs_res.json()["logs"]}
        assert "rbac.role_clone" in actions
        assert "user.update" in actions


@pytest.mark.asyncio
async def test_customer_isolation_and_template_version_immutability(isolated_env):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        adm = await _login(client, "admin@editorgrafica.com.br", "Admin@2026")
        reg_a = await client.post(
            "/api/auth/register",
            json={"name": "Cliente Alfa", "email": "alfa@teste.com", "password": "Password123", "lgpd_consent": True},
        )
        assert reg_a.status_code == 201
        tok_a = reg_a.json()["access_token"]

        reg_b = await client.post(
            "/api/auth/register",
            json={"name": "Cliente Beta", "email": "beta@teste.com", "password": "Password123", "lgpd_consent": True},
        )
        assert reg_b.status_code == 201
        tok_b = reg_b.json()["access_token"]

        prods = (await client.get("/api/store/products?only_customizable=true")).json()["products"]
        custom_prod = next(p for p in prods if p["template_id"])

        start_a = await client.post(
            "/api/customizer/start",
            headers=_auth_hdr(tok_a),
            json={"product_id": custom_prod["id"]},
        )
        assert start_a.status_code == 201
        proj_a = start_a.json()["project"]
        pid_a = proj_a["id"]
        orig_tpl_ver = proj_a["template_version"]
        orig_cfg = copy.deepcopy(proj_a["config"])

        # Isolamento estrito: Cliente B NÃO acessa nem altera projeto de Cliente A
        assert (await client.get(f"/api/customizer/projects/{pid_a}", headers=_auth_hdr(tok_b))).status_code == 403
        assert (await client.put(f"/api/customizer/projects/{pid_a}", headers=_auth_hdr(tok_b), json={"config": orig_cfg})).status_code == 403
        assert (await client.post(f"/api/customizer/projects/{pid_a}/preflight", headers=_auth_hdr(tok_b))).status_code == 403
        assert (await client.post(f"/api/customizer/projects/{pid_a}/preview-pdf?page_number=1", headers=_auth_hdr(tok_b))).status_code == 403

        # Imutabilidade do template: Admin cria v2 no template original com nova capa
        new_tpl_cfg = copy.deepcopy(orig_cfg)
        new_tpl_cfg["special_pages"]["cover_title"] = "CAPA V2 INDEPENDENTE"
        r_ver = await client.post(
            f"/api/admin/templates/{custom_prod['template_id']}/versions",
            headers=_auth_hdr(adm["access_token"]),
            json={"name": "Template v2", "config": new_tpl_cfg, "changelog": "Nova capa v2"},
        )
        assert r_ver.status_code == 201

        # Projeto já criado pelo Cliente A permanece intacto na versão em que nasceu
        check_a = await client.get(f"/api/customizer/projects/{pid_a}", headers=_auth_hdr(tok_a))
        assert check_a.status_code == 200
        assert check_a.json()["project"]["template_version"] == orig_tpl_ver
        assert check_a.json()["project"]["config"]["special_pages"]["cover_title"] == orig_cfg["special_pages"]["cover_title"]


@pytest.mark.asyncio
async def test_backend_pricing_engine_and_coupons(isolated_env):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        cust = await _login(client, "cliente@editorgrafica.com.br", "Cliente@2026")
        tok = cust["access_token"]
        prods = (await client.get("/api/store/products")).json()["products"]
        prod = next(p for p in prods if len(p["variations"]) >= 2 and p["is_customizable"])

        v0 = prod["variations"][0]
        paper_opts = prod["pricing_rules"].get("paper_options", [])
        finish_opts = prod["pricing_rules"].get("finish_options", [])
        sel_paper = paper_opts[-1]["name"] if paper_opts else ""
        sel_finish = finish_opts[-1]["name"] if finish_opts else ""

        p_single = await client.post(
            "/api/store/calculate-price",
            json={
                "product_id": prod["id"],
                "variation_id": v0["id"],
                "quantity": 1,
                "is_customized": True,
                "selected_options": {"paper_option": sel_paper, "finish_option": sel_finish},
            },
        )
        assert p_single.status_code == 200
        d1 = p_single.json()
        assert d1["customization_fee"] > 0
        assert d1["paper_delta"] >= 0
        assert d1["finish_delta"] >= 0

        # Quantidade 30 aplica desconto progressivo de atacado
        p_bulk = await client.post(
            "/api/store/calculate-price",
            json={
                "product_id": prod["id"],
                "variation_id": v0["id"],
                "quantity": 30,
                "is_customized": True,
                "selected_options": {"paper_option": sel_paper, "finish_option": sel_finish},
            },
        )
        assert p_bulk.status_code == 200
        d30 = p_bulk.json()
        assert d30["volume_discount_pct"] > 0
        assert d30["unit_price"] < d1["unit_price"]

        # Carrinho calcula no backend e valida cupons
        r_add = await client.post(
            "/api/cart/items",
            headers=_auth_hdr(tok),
            json={"product_id": prod["id"], "variation_id": v0["id"], "is_customized": False, "quantity": 2},
        )
        assert r_add.status_code == 201
        cart = r_add.json()
        assert cart["subtotal"] > 0

        r_cup_bad = await client.post("/api/cart/coupon", headers=_auth_hdr(tok), json={"coupon_code": "INVALIDO"})
        assert r_cup_bad.status_code == 400

        r_cup_ok = await client.post("/api/cart/coupon", headers=_auth_hdr(tok), json={"coupon_code": "BEMVINDO10"})
        assert r_cup_ok.status_code == 200
        cup_cart = r_cup_ok.json()
        assert cup_cart["discount_total"] > 0
        assert cup_cart["total_amount"] < cup_cart["subtotal"] + cup_cart["shipping_total"]


@pytest.mark.asyncio
async def test_21_editor_tool_permissions_enforcement(isolated_env):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        adm = await _login(client, "admin@editorgrafica.com.br", "Admin@2026")
        cust = await _login(client, "cliente@editorgrafica.com.br", "Cliente@2026")
        tok = cust["access_token"]

        # Admin configura um produto com apenas edit_text + edit_colors + export_preview liberados
        prods = (await client.get("/api/admin/products", headers=_auth_hdr(adm["access_token"]))).json()["products"]
        target = next(p for p in prods if p["is_customizable"])
        restricted_tools = {k: (k in {"edit_text", "edit_colors", "export_preview"}) for k in EDITOR_TOOL_LABELS}
        upd_prod = {
            "name": target["name"],
            "sku": target["sku"],
            "category_id": target["category_id"],
            "base_price": target["base_price"],
            "short_description": target["short_description"],
            "full_description": target["full_description"],
            "images": target["images"],
            "mockups": target["mockups"],
            "is_customizable": True,
            "template_id": target["template_id"],
            "allowed_tools": restricted_tools,
            "pricing_rules": target["pricing_rules"],
            "specs": target["specs"],
            "variations": target["variations"],
        }
        assert (await client.put(f"/api/admin/products/{target['id']}", headers=_auth_hdr(adm["access_token"]), json=upd_prod)).status_code == 200

        st = await client.post("/api/customizer/start", headers=_auth_hdr(tok), json={"product_id": target["id"]})
        assert st.status_code == 201
        pid = st.json()["project"]["id"]
        base_cfg = st.json()["project"]["config"]

        # Permitido: editar textos e cores CMYK e salvar versão 2
        ok_cfg = copy.deepcopy(base_cfg)
        ok_cfg["footer"]["company_name"] = "Studio Autorizado"
        ok_cfg["colors"]["title_color"] = {"c": 15, "m": 75, "y": 80, "k": 5, "hex": "#C93D2D"}
        r_ok = await client.put(
            f"/api/customizer/projects/{pid}",
            headers=_auth_hdr(tok),
            json={"config": ok_cfg, "create_version": True, "version_note": "Ajuste cor/texto"},
        )
        assert r_ok.status_code == 200, r_ok.text
        assert r_ok.json()["version"] == 2

        # Bloqueados no backend (devem retornar 403):
        forbidden_mutations = [
            ("modify_dimensions", lambda c: c["page_setup"].__setitem__("width_mm", 210.0)),
            ("modify_margins", lambda c: c["page_setup"].__setitem__("margin_top_mm", 28.0)),
            ("modify_binding", lambda c: c["page_setup"].__setitem__("margin_inner_mm", 30.0)),
            ("modify_bleed", lambda c: c["page_setup"].__setitem__("bleed_mm", 5.0)),
            ("modify_calendar", lambda c: c["calendar"].__setitem__("layout_mode", "weekly" if c["calendar"].get("layout_mode") != "weekly" else "monthly")),
            ("modify_holidays", lambda c: c["calendar"].__setitem__("state_code", "RJ")),
            ("add_decorative", lambda c: c["ruling"].__setitem__("ruling_type", "grid")),
            ("create_pages", lambda c: c["special_pages"].__setitem__("notes_end_pages", int(c["special_pages"].get("notes_end_pages", 0)) + 4)),
            ("delete_pages", lambda c: c["special_pages"].__setitem__("goals_page", False) if c["special_pages"].get("goals_page") else c["special_pages"].__setitem__("notes_end_pages", 0)),
            ("edit_fonts", lambda c: c["footer"].__setitem__("font_family", "Georgia" if c["footer"]["font_family"] != "Georgia" else "Arial")),
            ("edit_font_size", lambda c: c["footer"].__setitem__("font_size_pt", 13.0)),
            (
                "add_images",
                lambda c: c["elements"].append(
                    {"id": "img_forbid", "type": "image", "image_url": "/uploads/demo/mockups/mockup_agenda.svg", "x_mm": 30, "y_mm": 30, "width_mm": 20, "height_mm": 20}
                ),
            ),
        ]
        for tool_name, mutator in forbidden_mutations:
            bad_cfg = copy.deepcopy(ok_cfg)
            mutator(bad_cfg)
            r_bad = await client.put(f"/api/customizer/projects/{pid}", headers=_auth_hdr(tok), json={"config": bad_cfg})
            assert r_bad.status_code == 403, f"Esperava 403 para {tool_name}, recebeu {r_bad.status_code}"
            assert tool_name in r_bad.text

        # Restaurar versão 1 gera versão 3 com estado inicial
        r_rest = await client.post(f"/api/customizer/projects/{pid}/restore-version/1", headers=_auth_hdr(tok))
        assert r_rest.status_code == 200
        assert r_rest.json()["restored"] is True
        assert r_rest.json()["version"] == 3
        assert r_rest.json()["config"]["footer"]["company_name"] == base_cfg["footer"]["company_name"]


@pytest.mark.asyncio
async def test_full_11_step_ecommerce_webhook_pdf_approval_and_reports_e2e(isolated_env):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Registro de novo cliente com LGPD
        reg = await client.post(
            "/api/auth/register",
            json={
                "name": "Atelier Maria Helena",
                "email": "maria.helena@cliente.com",
                "password": "MinhaSenhaForte123",
                "phone": "11999990000",
                "document_cpf_cnpj": "12345678900",
                "lgpd_consent": True,
            },
        )
        assert reg.status_code == 201
        tok_cust = reg.json()["access_token"]

        # 2. Catálogo & Produto personalizável
        home = (await client.get("/api/store/home")).json()
        assert len(home["featured_products"]) >= 1
        prods = (await client.get("/api/store/products")).json()["products"]
        custom_prod = next(p for p in prods if p["is_customizable"])
        ready_prod = next(p for p in prods if not p["is_customizable"]) if any(not p["is_customizable"] for p in prods) else prods[-1]

        # 3. Inicia personalização, altera dados permitidos, salva v2 e roda preflight + preview PDF
        st = await client.post("/api/customizer/start", headers=_auth_hdr(tok_cust), json={"product_id": custom_prod["id"]})
        assert st.status_code == 201
        proj_id = st.json()["project"]["id"]
        cfg = st.json()["project"]["config"]
        cfg["footer"]["company_name"] = "Atelier Maria Helena"
        cfg["colors"]["title_color"] = {"c": 70, "m": 45, "y": 10, "k": 15, "hex": "#406E98"}
        r_save = await client.put(
            f"/api/customizer/projects/{proj_id}",
            headers=_auth_hdr(tok_cust),
            json={"config": cfg, "create_version": True, "version_note": "Versão aprovável"},
        )
        assert r_save.status_code == 200
        assert r_save.json()["version"] == 2

        r_pf = await client.post(f"/api/customizer/projects/{proj_id}/preflight", headers=_auth_hdr(tok_cust))
        assert r_pf.status_code == 200
        assert r_pf.json()["total_pages"] > 10

        r_cprev = await client.post(f"/api/customizer/projects/{proj_id}/preview-pdf?page_number=1", headers=_auth_hdr(tok_cust))
        assert r_cprev.status_code == 200
        assert r_cprev.content.startswith(b"%PDF-")

        # 4. Adiciona item personalizado + item pronto ao carrinho, calcula frete e aplica cupom
        await client.post(
            "/api/cart/items",
            headers=_auth_hdr(tok_cust),
            json={"product_id": custom_prod["id"], "project_id": proj_id, "is_customized": True, "quantity": 1},
        )
        await client.post(
            "/api/cart/items",
            headers=_auth_hdr(tok_cust),
            json={"product_id": ready_prod["id"], "is_customized": False, "quantity": 1},
        )
        await client.post("/api/cart/shipping", headers=_auth_hdr(tok_cust), json={"zip_code": "01310-100"})
        await client.post("/api/cart/coupon", headers=_auth_hdr(tok_cust), json={"coupon_code": "BEMVINDO10"})

        # 5. Checkout via Pix
        r_chk = await client.post(
            "/api/checkout",
            headers=_auth_hdr(tok_cust),
            json={
                "payment_method": "pix",
                "customer_notes": "Embalagem para presente",
                "address": {
                    "label": "Atelier",
                    "recipient_name": "Maria Helena",
                    "street": "Av. Paulista",
                    "number": "1000",
                    "neighborhood": "Bela Vista",
                    "city": "São Paulo",
                    "state": "SP",
                    "zip_code": "01310-100",
                },
            },
        )
        assert r_chk.status_code == 201, r_chk.text
        order_id = r_chk.json()["order"]["id"]
        ext_id = r_chk.json()["payment"]["external_id"]
        assert r_chk.json()["payment"]["qr_code_payload"]

        # 6. Webhook: assinatura inválida rejeitada (401); válida aprova e reenvio é idempotente
        wh_payload = {"external_id": ext_id, "status": "approved", "event_id": f"evt_{ext_id}_1"}
        r_bad_wh = await client.post("/api/webhooks/payment", json=wh_payload, headers={"X-Webhook-Signature": "sha256=invalida"})
        assert r_bad_wh.status_code == 401

        raw_wh, sig_wh = _sign_webhook(wh_payload)
        r_ok_wh = await client.post("/api/webhooks/payment", content=raw_wh, headers={"X-Webhook-Signature": sig_wh, "Content-Type": "application/json"})
        assert r_ok_wh.status_code == 200
        assert r_ok_wh.json()["idempotent"] is False
        assert r_ok_wh.json()["payment_status"] == "approved"

        r_dup_wh = await client.post("/api/webhooks/payment", content=raw_wh, headers={"X-Webhook-Signature": sig_wh, "Content-Type": "application/json"})
        assert r_dup_wh.status_code == 200
        assert r_dup_wh.json()["idempotent"] is True

        # 7. Equipe de produção atribui editor e gera PDF de Prévia + PDF Final CMYK + Preflight
        adm = await _login(client, "admin@editorgrafica.com.br", "Admin@2026")
        tok_adm = adm["access_token"]
        q_res = await client.get("/api/production/queue", headers=_auth_hdr(tok_adm))
        assert q_res.status_code == 200
        ord_data = next(o for o in q_res.json()["orders"] if o["id"] == order_id)
        custom_item = next(it for it in ord_data["items"] if it["is_customized"])
        ed_id = q_res.json()["editors"][0]["id"]

        assert (await client.post(f"/api/production/orders/{order_id}/assign", headers=_auth_hdr(tok_adm), json={"editor_user_id": ed_id})).status_code == 200

        r_gen = await client.post(
            f"/api/production/orders/{order_id}/items/{custom_item['id']}/generate-files?include_bleed=true&include_crop_marks=true",
            headers=_auth_hdr(tok_adm),
        )
        assert r_gen.status_code == 200, r_gen.text
        gen_data = r_gen.json()
        prev_fid = gen_data["preview_file_id"]
        fin_fid = gen_data["final_file_id"]
        assert prev_fid != fin_fid

        # 8. Controle de acesso em arquivos privados e Aprovação da Arte
        other = await _login(client, "cliente@editorgrafica.com.br", "Cliente@2026")
        assert (await client.get(f"/api/files/{prev_fid}/download", headers=_auth_hdr(other["access_token"]))).status_code == 403
        assert (await client.get(f"/api/files/{prev_fid}/download", headers=_auth_hdr(tok_cust))).status_code == 200
        # Arquivo final CMYK antes da aprovação fica bloqueado para o cliente
        assert (await client.get(f"/api/files/{fin_fid}/download", headers=_auth_hdr(tok_cust))).status_code == 403

        r_app = await client.post(
            f"/api/account/orders/{order_id}/items/{custom_item['id']}/artwork-decision",
            headers=_auth_hdr(tok_cust),
            json={"decision": "approved", "comments": "Cores e rodapé perfeitos!"},
        )
        assert r_app.status_code == 200
        assert r_app.json()["order"]["status"] == "aprovado_cliente"

        # 9. Staff avança etapas de produção até finalizado e verifica timeline completa
        for st_code in ("liberado_producao", "em_pre_impressao", "em_producao", "finalizado", "enviado", "entregue"):
            r_st = await client.post(
                f"/api/production/orders/{order_id}/status",
                headers=_auth_hdr(tok_adm),
                json={"status": st_code, "note": f"Etapa {st_code} concluída"},
            )
            assert r_st.status_code == 200

        ord_final = (await client.get(f"/api/account/orders/{order_id}", headers=_auth_hdr(tok_cust))).json()["order"]
        assert ord_final["status"] == "entregue"
        assert len(ord_final["approvals"]) == 1
        assert ord_final["approvals"][0]["project_version"] == 2

        # 10. Relatórios Admin (JSON, CSV, XLSX) & LGPD Export do cliente
        rep_json = await client.get("/api/admin/reports?export_format=json", headers=_auth_hdr(tok_adm))
        assert rep_json.status_code == 200
        assert rep_json.json()["summary"]["total_orders"] >= 1

        rep_csv = await client.get("/api/admin/reports?export_format=csv", headers=_auth_hdr(tok_adm))
        assert rep_csv.status_code == 200
        assert "Atelier Maria Helena" in rep_csv.text

        rep_xlsx = await client.get("/api/admin/reports?export_format=xlsx", headers=_auth_hdr(tok_adm))
        assert rep_xlsx.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(rep_xlsx.content))
        assert "Pedidos" in wb.sheetnames

        lgpd = await client.get("/api/lgpd/my-data", headers=_auth_hdr(tok_cust))
        assert lgpd.status_code == 200
        assert lgpd.json()["user"]["email"] == "maria.helena@cliente.com"
        assert len(lgpd.json()["orders"]) == 1
