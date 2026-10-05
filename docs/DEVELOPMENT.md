# Step-by-step development guide

This guide explains how the delivered modules fit together and how a six-person
team can continue the project. The working source is already included; follow the
README to run it before changing anything.

## Suggested team ownership

| Placeholder | Ownership | Main files |
|---|---|---|
| Member 1 | Product / retail process / acceptance | Docs, demo scenario, business rules |
| Member 2 | Streamlit / accessibility | `app.py`, `src/ui/` |
| Member 3 | Database / identity / security | `src/core/`, migrations, security tests |
| Member 4 | Forecast / customer ML | `src/analytics/`, analytics service |
| Member 5 | RAG / Groq / CrewAI | `src/rag/`, `src/agents/`, market service |
| Member 6 | Jobs / exports / deployment / QA | Jobs/reports, Docker, CI, tests |

Replace names/photos/biographies in `src/ui/pages/about.py` when the real six team
members are known. Do not present placeholders as real credentials.

## 1. Establish the local baseline

Prerequisite: Python 3.12. Create a virtual environment, install `requirements.txt`,
copy the environment example, migrate and start Streamlit using the README commands.
Inspect `app.py` and `src/core/config.py`. Run `python -m scripts.check_setup`.
Completion: Home loads and **Explore the demo** opens a synthetic dashboard.

## 2. Own the schema and migrations

Read `src/core/models.py`, `db.py`, `migrations/versions/0001_initial_business_schema.py`.
Business records carry tenant IDs; SQL services scope every query. Keep data writes
inside the `session()` transaction context. Never put SQL in a page or give the LLM
database access. Run `python -m alembic upgrade head` against a fresh test database.
Completion: tables and indexes exist and the revision is `0001`.

## 3. Verify identity and permissions

Read `src/core/auth.py`, the login/settings pages and `tests/test_security_and_data.py`.
Create a workspace, invite an inventory staff member and test prohibited finance/HR
access. Change a role and verify the old session is invalidated. For OIDC, first
configure the provider in a test tenant; exercise account provisioning and MFA.
Completion: no service trusts a role supplied only by session/UI state.

## 4. Maintain the page architecture

Each page exports `render(ctx)` in `src/ui/pages/`. Add routes in `app.py` with a
permission and keep calculations in services. Shared controls live in components.
Use navy `#0F172A`, teal `#0F766E`, amber `#F59E0B` and neutral surfaces. Preserve
labels, keyboard-accessible standard controls, empty/error states and responsive
columns. Run `pytest -q tests/test_pages.py` after changing navigation.
Completion: public, populated and restricted page tests pass.

## 5. Validate business imports

Edit `src/services/data.py` for schema rules; use the Upload page only for mapping
and review. Support date/SKU/quantity first, conditional price/cost/customer/basket
fields second. Keep raw files and transformation metadata. Add fixture cases for
new formats or ambiguity; never silently fill invented IDs, costs or lead times.
Run the mapping/duplicates test and manually upload `sample_data/synthetic_sales.csv`.
Completion: rejected rows explain errors and accepted totals match the source.

## 6. Extend forecast benchmarking

Start with `src/analytics/forecasting.py` pure functions and
`src/services/analytics.py` scoped persistence. Add an adapter behind `predict()`,
then test fitting on early data and an untouched chronological holdout. Evaluate
accuracy against seasonal naive plus latency/RAM. Enable Prophet/Chronos only after
their extras install and model access succeeds. Future work: calendar/promotional
features, category/store hierarchies, full weekly model training and calibrated
intervals. Completion: no leakage and measured improvement on the intended store.

## 7. Refine inventory and pricing

Read `src/services/inventory.py` and the formula examples in ARCHITECTURE. Introduce
new constraints before forming a proposal. Preserve single shared-budget allocation
and incoming-order accounting. Add multi-supplier/capacity tables only with a clear
business rule and a migration. Test changed inputs, duplicate receipt and the margin
floor. Completion: proposals are explainable and execution requires valid approval.

## 8. Evaluate customer analysis

`src/analytics/customers.py` contains deterministic RFM, descriptive K-Means,
two-item Apriori-style counting and logistic inactivity prediction. Improve customer
features only with stable identifiers and usable history. Keep train labels earlier
than the test period; measure PR-AUC/Brier against prevalence. Evaluate campaigns
with holdout groups outside this app before claiming retention improvement.
Completion: insufficient history produces a useful disabled state, not fake scores.

## 9. Improve extraction and hybrid search

Use `src/rag/extract.py` to retain page/headings/table/row locations. Test searchable
and scanned PDFs, interleaved Word tables and workbooks. In `retrieval.py`, authorize
collections before any embedding/reranking context. Benchmark chunk sizes and top-k
on a hand-labelled query/source set, including SKU exact matches and absent answers.
Rebuild indexes after model or document changes. Completion: scoped relevant evidence
and source locations survive the full index/retrieval round trip.

## 10. Connect grounded assistants

`pipeline.py` owns domain routing and tools; `crew.py` owns typed writer/reviewer
handoffs. Configure Groq in a development environment with non-sensitive test data.
Never grant arbitrary code/SQL tools. Test unsupported citations, numbers, unavailable
providers and injected document instructions. Extend business planning through an
approved knowledge corpus, not fabricated numerical advice. Completion: sourced
answers or explicit insufficient-evidence responses, including a reviewer trail.

## 11. Exercise public market research

Use `src/services/market.py` for public search and safe URL fetching. Keep provider
failure, dates, snippet-only evidence and variant ambiguity visible. New-product
pilots need actual supplier and budget checks. Add notification connectors only
after explicit user settings, per-recipient permissions and delivery deduplication.
Completion: an out-of-stock existing SKU is never labelled a new assortment item.

## 12. Persist work and validate exports

Queue slow work through `jobs.queue()`. Do not load/download models repeatedly inside
Streamlit reruns. Use one coordinator, atomic job claims, bounded deadlines and user
cancellation. Export one shared report object through `reports.export()`. Add source
and limitations metadata to new reports and inspect representative Word/PDF output.
Completion: job restarts are visible and exported numeric figures match the UI.

## 13. Harden and deploy

Run the full test suite, reviewed migrations and a clean demo in Docker/PostgreSQL.
Add HTTPS/identity, backup/restore, malware checks, operating quotas and monitoring
for the actual hosting environment. Separate server secrets from user configuration.
Use `scripts/retention.py` in dry-run mode before applying an approved retention
policy. Completion: a release candidate restores from backup and has an incident owner.

## Roadmap and milestones

| Period | Dependency / team milestone | Acceptance |
|---|---|---|
| First week | Members 1–3 approve data/roles and run onboarding; Members 4–6 verify demo analytics, jobs and exports | Sign in → upload → validate → forecast → replenish → explain → download |
| Weeks 2–3 | Real store pilot with consented data; model/retrieval evaluation | Baseline scores, verified units, stock counts and useful owner feedback |
| Weeks 4–5 | Identity, encrypted hosting, PostgreSQL backup/restore, incident exercise | Shared-deployment acceptance and no unresolved critical access defects |
| V1 extension | Better calendar features, supplier/capacity rules, notifications and POS interfaces | Measured operational benefit and integration-specific tests |
| V2 extension | Hierarchical models, multilingual retrieval, causal pricing, fine-tuning if justified | Prospective evaluation showing benefit over existing tools |

Suggested workflow: one feature branch per concern, reviewed migration with each
schema change, a short PR describing business behavior and tests, CI required before
merge. Members 3 and 6 jointly review permissions/deployment; Member 1 accepts the
business process. Never commit business CSVs, API keys, environment secrets or model
caches. Interfaces should keep `Context` first, use serializable payloads, and return
bounded, located evidence rather than side effects from an LLM.

No operating-cost estimate is measured yet. Local classical analytics is CPU-only;
Groq usage depends on selected models/tokens, web search availability on providers,
and semantic/Chronos cost on machine RAM and download size. Monitor job duration,
provider errors, token charges, retrieval quality and owner time per decision before
selecting a paid hosting tier.
