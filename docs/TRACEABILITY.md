# Scope and requirement traceability

The uploaded prompt describes a phased product. This package implements its usable
local business workflow and the optional AI integration paths. The table separates
running behavior from integrations needing credentials/deployment and future product
extensions; it does not imply that every future PRD feature is production-certified.

| Prompt area | Delivered behavior | Verification / owner | Next phase boundary |
|---|---|---|---|
| 1. Business purpose | Merchandise planning, retained human control, synthetic demo | End-to-end demo; Member 1 | Prospective business KPI pilot |
| 2. Python stack | Streamlit, SQLAlchemy/Alembic, Groq, CrewAI Flow, FAISS/BM25, worker | Imports/service/page tests; Members 3/5/6 | Hosted identity/production infrastructure |
| 3. Ingestion | CSV/XLSX/XLS/TSV, sheet mapping, raw files, rejected/corrected downloads, quality | Mapping/file tests; Member 3 | Spreadsheet connectors, cross-file transaction reconciliation |
| 4. Forecast | Daily horizons, chronological folds/holdout, ETS/ARIMA/baselines/Croston; optional Prophet/Chronos | Numeric/backtest tests; Member 4 | Full weekly training, covariates, hierarchy, calibrated bands, lighter neural comparison |
| 5. Inventory/pricing | EOQ/ROP/safety stock, shared budget, pack/MOQ/shelf, expiry review, purchase/price approvals | Budget/receipt/margin tests; Member 4 | Supplier comparison, storage capacity, causal price optimization, external POS/order connector |
| 6. Customers | RFM, K-Means, temporal logistic churn, exact two-item support/confidence/lift | Analytics test; Member 4 | General Apriori/FP-Growth multi-item mining and campaign outcome tracking |
| 7. Chat/extraction | Grounded domain tools, Groq, PDF/DOCX/text/HTML/sheets, optional OCR, source locations | Extraction/agent tests; Member 5 | Validated Urdu/Roman Urdu and optional justified fine-tuning |
| 8. Hybrid retrieval | Protected tenant/scope folders, manifests/checksums, BM25+FAISS+RRF+reranker | Real model smoke plus index tests; Member 5 | Labelled retrieval benchmark, stronger document ACLs and multi-node file store |
| 9. Market researcher | Explicit DuckDuckGo, safe page evidence, saved/dismissed/snoozed cards, catalog/pilot review | SSRF/catalog tests; Member 5 | Source-specific sales datasets and notifications |
| 10. Agents | Ten bounded roles; specialist tools; typed writer/reviewer Flow; deterministic checks | Real CrewAI mocked-provider test; Member 5 | Completeness/contradiction evaluation corpus and selective revision loops |
| 11. Automation | Durable jobs/schedules, cancel/timeout/retry, approval state and exact payload recheck | Job/approval tests; Member 6 | Recurring campaign/expiry/finance notifications; calendar-aware scheduler |
| 12. Pages/design | 17 routes, individual modules, navy/teal/amber, six team placeholders | All routes via AppTest; Member 2 | Browser accessibility/mobile usability study |
| 13. Database/files | Compact normalized business schema, tenant indexes, Alembic, PostgreSQL Compose | Schema migration test; Member 3 | Dedicated suppliers/orders/customers and database RLS |
| 14. Outputs | Text/Markdown/table/chart, Word/PDF/Excel/CSV/JSON; consistent report object | Export parsing and visual QA; Member 6 | Full RTL typography and custom report templates |
| 15. Governance | Auth, role checks, consent gates, audit, SSRF/upload guards, deletion, retention CLI | Isolation/revocation/deletion tests; Member 3 | Production identity provisioning, encrypted hosting, penetration/restore tests |
| 16. Evaluation | Service, role, source, numeric, page and export gates | `tests/`, VALIDATION; all owners | Measured field accuracy, p95 latency, business ROI |
| 17. Development | Runbook, architecture, formulas, agents, CI, Docker, samples, phased team guide | README/DEVELOPMENT; Member 6 | Store-specific rollout plan |

## Quality measures

| Dimension | Measure and proposed gate | Evaluation / owner |
|---|---|---|
| Evidence | 100% displayed source IDs resolve to authorized source records; unsupported citations rejected | Synthetic permissions/citation cases; Member 5 |
| Accuracy | Calculations match fixtures; forecast candidate reports actual holdout errors and baseline | Forecast/inventory/export tests; Member 4 |
| Completeness | Every supported operation has a result or a stated missing input; requested export opens | Core journey and format checks; Members 1/6 |
| Quality | Owner can follow a proposed order from evidence through approval/receipt | User acceptance pilot, target to be agreed; Members 1/2 |
| Efficiency | Record job elapsed time, API cost and time-to-decision; set p95 targets after measurement | Deployment metrics and pilot diary; Member 6 |

Targets beyond passing the included fixtures are proposed until measured on the
intended store's data. No invented accuracy percentage or profit improvement is used.
