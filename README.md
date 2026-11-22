# JobFinder

Site pessoal pra buscar vagas em várias fontes (Vagas.com, InfoJobs, Indeed Brasil, Trampos.co, LinkedIn público, We Work Remotely, Remotive, Arbeitnow) com filtros totalmente personalizáveis (tipo de vaga, presencial / remoto BR / remoto mundo, palavras-chave, salário, senioridade, **bairro/região específica**...) e envio das vagas escolhidas por e-mail.

> **Status atual**: Etapas 1–7 concluídas. **9 fontes registradas** (8 ativas + Google Jobs como toggle manual), filtros salvos, alertas automáticos por e-mail (Gmail SMTP).

## Roadmap por etapas

- [x] **Etapa 1** — Backend base + storage + 1 scraper (Arbeitnow)
- [x] **Etapa 2** — Frontend React + Vite com formulário de filtros completo
- [x] **Etapa 3** — Scrapers BR: **InfoJobs Brasil** (regional) + **Remotive** (remoto worldwide)
- [x] **Etapa 4** — Envio por e-mail (Gmail SMTP) + template HTML
- [x] **Etapa 5** — Filtros salvos + agendamento (APScheduler) + alertas automáticos
- [x] **Etapa 6** — Mais fontes: **Vagas.com**, **Trampos.co**, **WeWorkRemotely**, **LinkedIn público**, Google Jobs (experimental, off por padrão)
- [x] **Etapa 7** — Scrapling (Chromium undetected) como motor anti-bot: fallback do LinkedIn + **Indeed Brasil** novo, com busca por bairro/proximidade
- [x] **Etapa 8** — **LearnFinder**: aba nova pra achar certificação/curso/pós/faculdade por tema e preço (ver seção própria abaixo)
- [ ] **Próximo** — Exportar CSV, ordenação por relevância, polimento da UI

## LearnFinder (certificações, cursos, pós, faculdade)

Aba separada (`/learn`) pra achar formação por tema livre (ex.: "red team",
"pentest") com filtro de tipo e teto de preço. Domínio isolado do de vagas —
próprios modelos (`Course`/`CourseFilter`), storage (`courses.json`) e
matcher (`app/services/course_matcher.py`), sem alertas por e-mail (faz
sentido pra vaga que muda todo dia, não pra pós que muda a cada meses).

| Fonte | Mecânica | Cobre |
|---|---|---|
| **Udemy** | Scrapling (browser undetected) | Cursos com preço real, filtro nativo de gratuito. Certificado de conclusão sempre. Só é consultada quando o filtro de tipo inclui "curso" (ou está vazio) — Udemy não tem certificação/pós/faculdade de verdade. |
| **Busca no Google** | Scrapling — busca orgânica (não o widget de jobs, esse é outro) | Cobre instituições de pós/faculdade/certificação que não estão em nenhum catálogo fechado (Senac, Estácio, PUC, Cruzeiro do Sul, IESB, etc.). Sem preço/certificado estruturado — aparece como "verificar no site". Mais lenta (resolve cada link) e sujeita a rate-limit do Google sob uso pesado (nesse caso volta vazia, sem erro). Pulada quando o filtro é só "curso" (Udemy já cobre melhor e mais rápido). |
| **Curado** | Dataset estático em `backend/data/curated_*.json` | ~18 certificações (CompTIA, ISC2, EC-Council, OffSec, TCM, INE, GIAC, ISACA) + ~8 pós/faculdade BR, mantidos à mão. Preços aproximados quando marcado. Carregado no storage a cada boot, não é "fonte ao vivo". |

DIO foi investigado e descartado: catálogo inteiro atrás de login (Keycloak),
sem navegação anônima.

## Fontes ativas

| Fonte | Mecânica | Cobre |
|---|---|---|
| **Vagas.com** | HTML SSR (`vagas-em-{cidade}` / `vagas-de-{kw}-em-{cidade}`) | BR generalista, melhor por cidade do que por UF |
| **InfoJobs BR** | HTML SSR (`/empregos-em-{slug-uf}.aspx`) | BR generalista, regional + home-office |
| **Indeed Brasil** | Scrapling (browser undetected) | BR generalista, **forte em não-tech** (varejo, alimentação, atendimento) e busca por **bairro/proximidade** (ex.: "Asa Norte, Brasília - DF") |
| **Trampos.co** | JSON embutido em `window.initialLoad` | BR tech / comunicação / design |
| **LinkedIn (público)** | Endpoint `jobs-guest` + fallback Scrapling (browser undetected) | BR + mundo, guest rápido + fallback quando dá 429 |
| **We Work Remotely** | RSS oficial por categoria | Remoto worldwide, foco tech |
| **Remotive** | API JSON pública | Remoto worldwide |
| **Arbeitnow** | API JSON pública | EU / DACH + remoto worldwide |
| Google Jobs | Playwright (off) | Descontinuado pra anônimos desde 2023 (reverificado 2026-08-30) |

## Busca por bairro/região específica

Nenhum portal brasileiro filtra por bairro nativamente (todos operam por
cidade/UF) — **exceto o Indeed**, cujo campo de localização aceita texto
livre e faz busca por proximidade geocodificada. Pra aproveitar isso, digite
o bairro direto no campo "Região" com modo presencial/híbrido (ex.:
`Asa Norte, Brasília - DF`). O card da vaga pode continuar mostrando só
"Brasília, DF" (o Indeed não expõe o bairro na listagem), mas o resultado já
vem filtrado por proximidade real — o `matcher.py` reconhece isso via uma
tag interna e não descarta essas vagas.

Nas outras fontes (InfoJobs, Vagas.com), digitar um bairro no campo Região
não funciona — elas só reconhecem UF/capital e, se não reconhecerem o texto,
caem silenciosamente numa busca nacional. Prefira UF/capital nelas
("Distrito Federal", "Brasília-DF") e use o Indeed pra granularidade de bairro.

## Stack

- **Backend**: Python 3.13 + FastAPI + Pydantic v2 + httpx + selectolax + APScheduler
- **Browser automation** (opcional, etapa 6): Playwright + Chromium headless
- **Scrapling** (etapa 7): Chromium "undetected" (patchright) via `StealthyFetcher`/`AsyncStealthySession` — fallback do LinkedIn quando dá 429, e motor único do **Indeed Brasil** (que bloqueia scraping direto agressivamente)
- **Storage**: arquivos JSON em `backend/data/` (com filelock e dedup por hash)
- **Frontend**: React 19 + Vite 6 + TypeScript + Tailwind 4 + react-router
- **E-mail** (etapa 4): Gmail SMTP

## Como rodar (Windows)

### Modo fácil — 1 clique

1. Duplo-clique em `start.bat` na raiz do projeto.
   - Sobe backend (porta 8765) e frontend (porta 5173) em janelas separadas
   - Abre `http://localhost:5173` no navegador automaticamente
2. Para parar tudo: duplo-clique em `stop.bat` (ou feche as duas janelas).

### Modo manual — 2 terminais

**Setup inicial (só uma vez):**

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m patchright install chromium

cd ..\frontend
npm install
```

> O `patchright install chromium` baixa o Chromium usado pelo Scrapling
> (fallback do LinkedIn) e pelo `GoogleJobsScraper` (off por padrão), ~150 MB.
> Os outros 6 scrapers funcionam sem browser nenhum.

**Rodar (toda vez):**

Terminal 1 (backend):
```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8765
```

Terminal 2 (frontend):
```powershell
cd frontend
npm run dev
```

API em `http://127.0.0.1:8765` (docs em `/docs`). App em `http://localhost:5173`.

## Endpoints atuais

| Método | Rota | Descrição |
|---|---|---|
| GET  | `/health` | Status da API, fontes, scheduler e config de e-mail |
| GET  | `/settings` | Status mascarado SMTP + jobs agendados |
| GET  | `/sources` | Lista das fontes (scrapers) disponíveis |
| POST | `/scrape` | Faz scraping ao vivo com um `JobFilter` e persiste |
| POST | `/jobs/search` | Aplica filtro só sobre vagas já armazenadas |
| GET  | `/jobs?limit=&offset=` | Lista vagas persistidas |
| GET  | `/filters` | Lista filtros salvos |
| POST | `/filters` | Cria filtro salvo |
| GET  | `/filters/{id}` | Lê filtro |
| PATCH | `/filters/{id}` | Atualiza filtro (parcial) |
| DELETE | `/filters/{id}` | Remove filtro e seu histórico de envios |
| POST | `/filters/{id}/run-now` | Executa agora (faz scrape + e-mail se houver vaga nova) |
| POST | `/filters/{id}/reset-sent` | Limpa histórico — próximo run trata todas como novas |
| POST | `/filters/test-email` | Manda e-mail de teste pra validar credenciais |

## Configurando e-mail (Gmail SMTP)

1. Ative **verificação em 2 etapas** na sua conta Google.
2. Gere uma **App Password** em [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Copie `backend/.env.example` para `backend/.env` e preencha:
   ```
   GMAIL_USER=seu-email@gmail.com
   GMAIL_APP_PASSWORD=abcdefghijklmnop
   DEFAULT_RECIPIENT=destino-padrao@gmail.com
   ```
4. Reinicie o backend e teste em **Configurações → Enviar e-mail de teste**.

### Exemplo de filtro (`POST /scrape`)

```json
{
  "keywords": ["python", "django"],
  "exclude_keywords": ["senior", "php"],
  "job_types": ["full_time", "freelance"],
  "location_mode": "remote_worldwide",
  "region": null,
  "seniorities": ["junior", "mid"],
  "min_salary": null,
  "posted_within_days": 7,
  "sources": [],
  "sort_by": "recent",
  "limit": 50
}
```

#### `location_mode` — os modos pedidos:
- `"on_site_region"` + `region: "Brasília-DF"` → presencial em região específica
- `"hybrid_region"` + `region: "Brasília-DF"` → híbrido
- `"remote_brazil"` → remoto, mas restrito ao Brasil
- `"remote_worldwide"` → remoto de qualquer lugar
- `"any"` → não filtra por localização

#### `job_types`:
`full_time`, `part_time`, `freelance`, `contract`, `internship`, `temporary`

## Estrutura

```
JobFinder/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint + lifespan do scheduler
│   │   ├── bootstrap.py             # Registra scrapers
│   │   ├── config.py                # Settings via .env
│   │   ├── api/
│   │   │   ├── jobs.py              # /scrape, /jobs, /sources
│   │   │   ├── filters.py           # CRUD + run-now + test-email
│   │   │   └── settings.py          # /settings (status SMTP + scheduler)
│   │   ├── models/job.py            # Job, JobFilter, SavedFilter, enums
│   │   ├── scrapers/                # arbeitnow, infojobs, remotive,
│   │   │                            # vagas_com, trampos, weworkremotely,
│   │   │                            # linkedin, indeed, google_jobs (+ _playwright)
│   │   └── services/
│   │       ├── storage.py           # JSON + filelock + dedup + sent por filtro
│   │       ├── matcher.py           # word-boundary, aliases, accent-insensitive
│   │       ├── scrape_service.py    # orquestra scrapers
│   │       ├── email_service.py     # SMTP Gmail + templates HTML
│   │       ├── alert_service.py     # combina scrape + dedup + e-mail
│   │       └── scheduler.py         # APScheduler async
│   ├── data/                        # jobs.json, filters.json, sent.json (gitignored)
│   ├── .env / .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx + main.tsx
│   │   ├── api/                     # client.ts + types.ts (espelha backend)
│   │   ├── components/
│   │   │   ├── ui/                  # Button, Input, Modal, Card, Badge, etc.
│   │   │   ├── FilterForm.tsx
│   │   │   ├── SaveFilterModal.tsx
│   │   │   ├── JobCard.tsx + JobList.tsx
│   │   │   └── Layout.tsx
│   │   └── pages/
│   │       ├── SearchPage.tsx       # busca ao vivo + salvar como alerta
│   │       ├── JobsPage.tsx         # vagas persistidas
│   │       ├── FiltersPage.tsx      # filtros salvos + ações
│   │       └── SettingsPage.tsx     # SMTP + scheduler
│   ├── index.html
│   ├── vite.config.ts               # proxy /api -> backend
│   └── package.json
└── README.md
```

## Como adicionar uma nova fonte

1. Crie `backend/app/scrapers/minha_fonte.py` herdando de `BaseScraper`.
2. Defina `source_id`, `name`, `description` (e opcionalmente `enabled = False` se ainda não tá pronto pra ligar por padrão).
3. Implemente `async def fetch(self, f: JobFilter) -> list[Job]`.
4. Registre em `app/bootstrap.py` e adicione o ID em `JobSource` em `app/models/job.py`.
5. Adicione o ID e o label em `frontend/src/api/types.ts` (`JobSource` + `SOURCE_LABELS`).

Se a fonte exigir JavaScript, importe `browser_page` de `app/scrapers/_playwright.py` — ele já cuida do lifecycle do Chromium, user-agent, viewport e bloqueio de imagens/fontes.

A interface do `BaseScraper` é simples: receba um `JobFilter`, faça best-effort para filtrar do lado da fonte, retorne `Job`s normalizados. O `matcher.apply_filter()` roda depois pra garantir consistência (palavras-chave, exclusões, localização estrita vs híbrida, etc.).
