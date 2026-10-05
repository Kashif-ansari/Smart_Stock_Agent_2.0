# Smart Stock Agent

A working Python and Streamlit application for a general store: validate sales,
forecast demand, plan replenishment, analyze customers, research products, and
produce evidence-based reports. Navy, teal and amber are used across 17 pages.

The application runs without an API key in **Evidence only** mode. Groq, CrewAI,
local semantic models, Prophet and Chronos are opt-in integrations. No real store
records, credentials, database or model weights are included in this package.

## 1. Start locally

Use **Python 3.12**. Run commands from this folder after extracting the ZIP.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m streamlit run app.py
```

If your machine blocks PowerShell activation, use `.venv\Scripts\python.exe`
instead of `python` for the remaining commands; activation is optional.

**macOS / Linux**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m alembic upgrade head
python -m streamlit run app.py
```

Open **http://localhost:8501**. Select **Explore the demo**. Each demo gets its own
isolated workspace with 180 days of synthetic sales. There is no shared demo password.
Or create your own account on **Sign in**; passwords require at least 12 characters.

## 2. Complete the first business workflow

1. Open the demo, or upload `sample_data/synthetic_sales.csv` in your own workspace.
2. Review column mappings and rejected rows. Confirm missing days are zero sales
   only when this is true. Import accepted records.
3. In **Demand forecasting**, select a product and horizon, then generate a forecast.
   Use **Refresh status** when the background task is ready.
4. In **Inventory & reordering**, confirm physical stock, supplier lead time, pack
   size, costs and shelf life. Historical uploads do not update physical inventory.
5. Review proposed quantities against the shared purchase budget. Submit a draft.
6. Approve it in **Automation & approvals**. Record receipt only after goods arrive.
   The app does not send supplier orders or debit bank accounts.
7. Ask the **Business chatbot**, “Which products should I reorder?” in Evidence only
   mode. Inspect its sources and calculations.
8. Choose Excel, PDF, Word, CSV, text or JSON in the report download control.

Do not import overlapping copies of the same sales period. Identical files are
blocked, but different files with overlapping transactions require review.

## 3. Enable Groq and CrewAI

```bash
python -m pip install -r requirements-ai.txt
```

Edit the server's `.env` file, then restart the app and any separate worker:

```dotenv
GROQ_API_KEY=your_own_key
GROQ_MODEL=openai/gpt-oss-20b
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
ENABLE_EXTERNAL_AI=true
```

The owner must also enable consent in **Settings → Integrations**. Select
**Groq assistant** for a grounded draft, or **CrewAI review** for separate writer
and reviewer agents in a typed CrewAI Flow. Business calculations and permissions
remain deterministic Python services. Source text cannot call tools or execute code.

The chatbot uses an existing LLM with RAG; it does not train a new LLM. Forecasts
and churn models are fitted separately to business data. Fine-tuning needs a future
evaluation project with appropriate, consented training examples.

## 4. Enable FAISS hybrid search and reranking

Install `requirements-ai.txt`, then set:

```dotenv
ENABLE_SEMANTIC_SEARCH=true
ENABLE_MODEL_DOWNLOADS=true
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
```

Restart the processes. Upload and review a document in **Knowledge base**, choose
the correct access collection, then **Build semantic index**. The first build
downloads weights from the model provider. Internet access and writable disk space
are required. Inference then runs locally with FastEmbed/ONNX on CPU.

The pipeline authorizes collections before BM25, FAISS, reciprocal-rank fusion,
cross-encoder reranking and citation selection. Indexes are stored under
`data/indexes/<tenant>/<collection>/<version>/` with checksum manifests. Changed
documents invalidate stale vectors. Keyword search works without model downloads.
Initial chunking uses 220 words and 35-word overlap. English retrieval is the
validated design language; Urdu/Roman Urdu quality is not established.

## 5. Forecasting, OCR and public research extras

**Forecast models:** `python -m pip install -r requirements-forecast.txt` adds
Prophet and the `amazon/chronos-2` adapter. Chronos requires model downloads and
substantially more RAM than the classical models. Try it on a small SKU first;
compare its held-out MAE/WAPE with baselines before adopting it. No universal
“best model” or accuracy guarantee is claimed. The default automatic benchmark
compares seasonal naive, moving average, ETS and Croston SBA. ARIMA is selectable.
Forecasts are daily; the UI can group them into weekly planning totals.

**OCR:** `python -m pip install -r requirements-ocr.txt`, plus the Tesseract executable
installed on the operating system (`sudo apt-get install tesseract-ocr` on Debian/
Ubuntu). OCR supports images and PDFs needing OCR up to 20 pages. Review extracted
text before saving. Searchable PDFs support up to 250 pages.

**Research:** set `ENABLE_WEB_SEARCH=true`, restart, then enable owner consent in
Settings. Research uses DDGS with the DuckDuckGo backend explicitly selected.
Queries must contain public product/category terms. Search results include URLs,
retrieval timestamps and evidence limitations. A separate pilot form compares the
catalog, flags possible variant matches, and checks margin, supplier and budget.
Search rank is never treated as proof of sales. Missing product quantities are
explicitly labelled scenarios.

## 6. Background work and schedules

Local development starts one worker thread which launches each task in a separate
process. Jobs, state and interval schedules live in SQL. There is a 600-second
default deadline, cancellation, stale-run detection, and a manual retry control.
Double-click duplicates are suppressed for a one-minute window per requester.
Scheduled occurrences have persistent deduplication keys.

For deployment, set `AUTO_WORKER=false` and run a separate process:

```bash
python -m src.services.jobs
```

Use one scheduler/worker coordinator per deployment. Forecast schedules are
available in the UI; market research schedules are supported by the service API.
Schedules use elapsed UTC intervals, not local-time cron rules. A server restart
does not lose queued jobs. The configured workspace timezone labels business
preferences; source sales dates should already represent local business dates.

## 7. Docker with PostgreSQL

1. Install Docker Engine/Desktop with Compose.
2. Copy `.env.example` to `.env` if necessary.
3. Generate a database password: `python -c "import secrets; print(secrets.token_hex(24))"`.
4. Set `POSTGRES_PASSWORD` to that generated value. Do not commit `.env`.
5. Run:

```bash
docker compose up --build -d
docker compose logs -f app worker
```

Open http://localhost:8501. Compose runs PostgreSQL 16, the Streamlit app, and the
separate worker with durable named volumes. The app applies Alembic migrations
before starting. AI extras are installed by default; set `INSTALL_AI=false` for
a smaller core-only image. Model weights are still downloaded separately.

The port binds to localhost. For shared access, use an HTTPS reverse proxy, an
identity provider, restricted network access, encrypted disks and backups. Disable
public signup/demo in shared production environments. The ZIP is a runnable project,
not a hosted deployment. Do not use `docker compose down -v` unless you intend to
erase its stored database and files.

## 8. Identity and roles

Local development includes password hashing, login throttling, expiring sessions,
invite codes and live server-side role checks. **Settings → People & roles** creates
one-time invitations; it does not email anyone. The owner can revoke access.

For OIDC, configure `.streamlit/secrets.toml` from its example and set `AUTH_MODE=oidc`.
Install `Authlib>=1.3.2,<2` for Streamlit's OIDC support. Require MFA at the identity
provider. Verified email, issuer and subject are required; accounts are not linked
automatically based only on a matching email. OIDC provisioning/invitations across
an existing business need administrator integration before organizational rollout.
Password mode is the fully implemented local onboarding flow.

Roles: owner, manager, sales, inventory, finance, HR and analyst. See
`docs/SECURITY.md` for the permission matrix, data boundaries and deployment controls.

## 9. Verify and maintain

```bash
python -m scripts.check_setup
python -m pytest -q
python -m compileall -q app.py src
```

Tests use temporary databases and synthetic inputs. The optional CrewAI test skips
when its package is absent. It runs a real Flow with a mocked provider, so no API
key or billable call is used. See `docs/VALIDATION.md` for measured test results and
integration limitations.

Alembic owns schema changes. After modifying models, create and review a migration:
`python -m alembic revision --autogenerate -m "describe change"`, then run
`python -m alembic upgrade head`. Back up before migrations. For existing databases
created by `app.py` before migrations were introduced, verify schema compatibility
before `alembic stamp 0001`; do not stamp an unknown schema.

Source deletion is available to owners in Settings. It conservatively clears
saved reports/assistant answers, cancels jobs and pending proposals, and deletes
dependent forecasts and schedules. Downloaded copies cannot be recalled. Approved
commitments and stock movement history remain business records.

## Project guide

- `docs/ARCHITECTURE.md`: modules, data model, formulas and agent boundaries.
- `docs/DEVELOPMENT.md`: step-by-step development and deployment extension guide.
- `docs/SECURITY.md`: role matrix, privacy, retention and operating controls.
- `docs/TRACEABILITY.md`: implemented scope, optional integrations and future phases.
- `docs/VALIDATION.md`: verification evidence and remaining external checks.
- `docs/MODEL_NOTES.md`: checked model cards, license metadata and selection rationale.
- `requirements.txt`: runnable core; extras are in separately named requirements files.
- `constraints-tested.txt`: versions present during verification, not a complete lockfile.

This release supports a single store and currency per workspace. Supplier EDI/POS
sync, payments, payroll, marketing sends, multi-store reconciliation, causal pricing,
full accounting, and independently validated multilingual retrieval are extensions.
About Us contains six clearly labelled team placeholders to replace with real details.
