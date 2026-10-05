# Agent and workflow contracts

The word agent describes a bounded responsibility. Exact calculations and access
checks use Python services; the app does not pay for a separate LLM call for every
role. CrewAI is used for the optional writer/reviewer flow. Research and specialist
roles are orchestrated through typed service inputs and persisted jobs.

Common input: authenticated `Context`, bounded question or structured job payload,
current permitted data. Common state: tenant/requester-scoped SQL job and agent-run
records. No global conversation memory. Common output: JSON-serializable evidence,
tables, limitations, stage status and optional shared report. Roles cannot expand
their own permissions. A human reviews consequential decisions.

| Role | Goal and tasks | Workflow / tools | Output / trigger | Required access / escalation |
|---|---|---|---|---|
| Orchestrator | Understand request and route to the smallest adequate path | Authorize → classify → invoke one specialist → collect evidence → write/review | Structured run when chat/job starts | `chat` plus downstream service permissions; deny restricted domains |
| Market researcher | Find public evidence and evaluate absent assortment candidates | Public query → DuckDuckGo → safe source fetch → catalog comparison → pilot checks | URLs, timestamps, matched variants, scenario and limitations | `market.read`, server gate and owner consent; unavailable search fails visibly |
| Sales / retention | Describe customers and candidate bundles | Sales → RFM → K-Means; transaction pairs; temporal churn | Aggregate segments/rules and measured metrics | `customers.read`; insufficient IDs/history disables that analysis |
| Forecast analyst | Produce reproducible demand estimates | Dataset validation → chronological folds → holdout → final fit | Model/period/version, predictions, MAE/WAPE/bias, bands | `forecast.run`; no eligible model returns an actionable error |
| Operations / procurement | Review stock and feasible purchase quantities | Catalog/sales → safety stock/ROP/EOQ → shared budget → draft | SKU table and exact purchase payload | `inventory.read/write`; changes require separate approval |
| Finance | Explain recorded revenue, cost and expenses | Scoped sales/expense queries → exact arithmetic → completeness flags | Aggregate financial estimate, period and limitations | `finance.read`; missing cost/price prevents complete-profit claims |
| HR support | Describe staffing capacity and coverage gaps | Restricted employee availability → aggregate available hours | Staffing totals and advisory gap | `hr.read`; no autonomous hiring, payroll or personnel messaging |
| Knowledge researcher | Retrieve located authorized evidence | Collection auth → chunks → BM25/FAISS → fusion → rerank | Up to six source chunks and retrieval status | `knowledge.read`; lexical fallback for stale/unavailable dense index |
| Writer | Explain tools and evidence in plain language | Read-only evidence → Groq structured answer; local extract fallback | Answer and exact source IDs | Consent and API key for live AI; never executes tools |
| Reviewer | Reject ungrounded or malformed drafts | Permission/domain checks → exact source IDs → numeric-literal check; optional independent CrewAI judgment | Accept or evidence fallback, review note | No new data access; failed review does not authorize an action |

Success criteria: authorized sources, traceable calculations, no fabricated forecast
values, a usable report, and an explicit missing-data explanation when needed. These
are functional criteria, not a claim that model answers are always correct.

## Structured handoff

`run_case()` returns answer, citations, tables, notes, stages, provider, review,
elapsed seconds, retrieval status, shared report and run ID. The stages are user
input, research, analysis, verification, writing, review, and final report. Simple
evidence-only questions avoid LLM calls. Finance and HR context is kept out of other
domain reports even when an owner has access to all collections.

The shared report has title, generated UTC timestamp, summary, named row tables,
source references, limitations, scope and approval status. The same object feeds
all export formats. Business service outputs determine numeric values; a writer
cannot invent additional metrics. The conservative literal check may reject a
valid paraphrase that changes numeric formatting; users then see direct evidence.

## Timeouts and review limits

Groq: 35-second SDK timeout, one retry, then one configured fallback model. CrewAI:
fresh writer/reviewer agents, no delegated tool calls, max two reasoning iterations
per agent; the outer job has a 600-second process deadline. No unbounded correction
loop. An unavailable/rejected draft falls back to sourced tool output. Invalid
credentials/consent are explicit configuration errors before provider invocation.
The reviewer does not certify legal, medical, financial or operational correctness.

## Business process state

| Process | Trigger and inputs | Result | Approval / follow-through |
|---|---|---|---|
| Demand planning | Button or elapsed schedule; dataset/SKU/horizon | Saved forecast and evaluated model | No purchasing side effect |
| Replenishment | Current catalog, sales, supplier assumptions, budget | Reviewed plan and optional purchase proposal | Pending → approved/rejected → confirmed receipt |
| Expiry review | Inventory page; product expiry and stock | Seven-day attention list | Physical inspection and disposition remain human |
| Price simulation | User price, cost, margin floor, assumed volume | Scenario and exact proposed catalog price | Manager/owner approves; inventory staff applies |
| Customer campaign | RFM/basket/churn evidence | Advisory segment/bundle idea | No marketing messages sent by this release |
| Finance summary | Uploaded sales and recorded expenses | Restricted report | Review for missing inputs; no statutory filing |
| Staffing support | Staff roles/hours and required coverage | Restricted capacity/gap view | Human schedules staff; no automated personnel actions |
| Market research | Public category/variant; optional interval service schedule | Evidence cards and reviewed pilot scenario | Save/dismiss/snooze; no repeated external notifications |

Approvals contain a hash of exact payload and a two-day decision deadline. Current
cost and prior price must still match. After approval, an incoming purchase stays
on order until recorded receipt. A catalog price approval expires at its deadline.
Execution claims state atomically and commits stock/price updates in the same SQL
transaction. Only the requester sees private task results. Jobs can be cancelled
and failed attempts resubmitted from the UI. Audit entries record actor and IDs.
