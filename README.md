# EditorGráfica Pro — Plataforma Web de Criação e Personalização de Miolos de Agendas CMYK

Plataforma gráfica web desenvolvida em **Python (FastAPI)**, **SQLite (migrações incrementais)**, **ReportLab (CMYK nativo)** e **JavaScript ES6+** para produção em larga escala de miolos de agendas personalizados (15x21 cm A5 e formatos customizados).

---

## Principais Recursos

- **Motor de Calendário Exato**: datas datadas ou permanentes (não datadas), anos bissextos, 1 dia/página (Sábado e Domingo juntos ou separados), 2 dias/página, Semanal, Mensal, Financeiro, Empresarial e Planner, feriados nacionais móveis/fixos, estaduais por UF e municipais/personalizados.
- **Editor Gráfico Visual**: réguas em milímetros, zoom (`50%` a `150%`), sangria (`3 mm`), margem interna de encadernação (*gutter*) com espelhamento frente/verso, área de segurança, grade, alinhamento magnético, redimensionamento, rotação livre, desfazer/refazer (`Ctrl+Z`/`Ctrl+Y`) e temas **Escuro (Dark)** e **Claro (Light)**.
- **Cartela de Cores 100% CMYK**: seletores `C% M% Y% K%` sincronizados com preview Hex, 8 paletas gráficas prontas e salvamento de novas paletas na biblioteca.
- **Motor de PDF para Impressão**: operadores nativos CMYK (`k`/`K`), fontes TrueType vetoriais incorporadas, marcas de corte (*Crop Marks*), sangria, exportação em PDF único, separado por mês (`.zip`), páginas individuais (`.zip`) e **Personalização em Massa (Mala Direta)** com `.csv`/`.xlsx`.
- **Pré-Impressão (Preflight)**: verificação automática de dimensões, sangria, encadernação, área de segurança, carga de tinta CMYK (`TAC <= 300%`) e resolução real (`DPI`) de imagens.

---

## Opção 1: Instalação Rápida na VPS (Ubuntu / Debian) em 1 Comando

Execute na sua VPS (como `root` ou com `sudo`):

```bash
curl -fsSL https://raw.githubusercontent.com/Gabrielchr1/editorG/main/deploy_vps.sh | sudo bash
```

Ou clonando manualmente:

```bash
git clone https://github.com/Gabrielchr1/editorG.git /opt/editorgrafica
cd /opt/editorgrafica
sudo bash deploy_vps.sh
```

Esse script instala Python 3, fontes TrueType (`fonts-liberation` e `fonts-dejavu-core`), configura o ambiente virtual `.venv`, inicializa o SQLite, cria o serviço `systemd` (`editorgrafica`) e publica automaticamente via **Nginx** na **porta 80**.

### Como atualizar a VPS depois de novos commits

```bash
sudo bash /opt/editorgrafica/deploy_vps.sh
```

Ou manualmente:

```bash
cd /opt/editorgrafica && git pull && sudo systemctl restart editorgrafica
```

---

## Opção 2: Deploy Rápido com Docker Compose

```bash
git clone https://github.com/Gabrielchr1/editorG.git
cd editorG
docker compose up -d --build
```

Acesse em `http://IP-DO-SERVIDOR:8000` (os dados do SQLite ficam persistidos em `./data` e os uploads em `./uploads`).

---

## Opção 3: Execução Local (Desenvolvimento)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Executar suíte de testes automatizados:

```bash
python -m pytest -v tests/test_platform.py
```
