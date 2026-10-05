# Release verification

Checked on 5 October 2026 with Python 3.12.14. Tests used synthetic data and
temporary local databases, not a real customer's business records.

## Automated results

`python -m pytest -q`: **43 passed in 21.01 seconds** on the verification machine.
`python -m compileall -q app.py src scripts migrations`: passed.

Coverage includes password/session behavior, login throttling, expired invites,
live role revocation, tenant isolation, HR/finance document and report boundaries,
CSV/XLSX mapping and limits, returns/rejected rows, duplicate imports, source deletion,
private job visibility, forecast chronology and all installed classical baselines,
missing-date handling, shared inventory budget, changed-price inputs, single receipt,
customer analytics, job/schedule deduplication/cancel, and a separate worker process.

Streamlit AppTest exercised every available route in a populated owner demo, all
public pages, an empty inventory-role workspace, demo navigation and churn controls.
No page exception or error state occurred in those scenarios. This is functional UI
verification, not a cross-browser/mobile accessibility certification.

Seven export formats were parsed/checked: TXT, Markdown, CSV, XLSX, DOCX, PDF and
JSON. Tests verify numeric fidelity, missing-value handling and spreadsheet formula
neutralization. A populated 12-SKU wide inventory report was rendered for visual
inspection: two landscape Word pages and two PDF pages after layout adjustment.

## Real optional-component smoke checks

| Component | Actual result |
|---|---|
| BGE embedding | Downloaded configured weights; produced finite 384-dimensional embeddings |
| MiniLM reranker | Downloaded configured weights; scored the relevant milk-storage sentence above an unrelated soap sentence |
| FAISS hybrid pipeline | Built a synthetic tenant index and returned `Hybrid keyword + FAISS + cross-encoder` with the correct policy source |
| Prophet 1.4.0 | Fit a synthetic daily sequence and returned seven finite forecast values |
| Tesseract OCR | Read “MILK-1 requires refrigeration” from a generated image and image-only PDF, preserving the OCR-review label |
| DuckDuckGo/DDGS | Returned five public results using the explicit backend; source-page reads were unavailable in this environment, so results correctly remained labelled search snippets |
| CrewAI 1.15.23 | Real typed Flow and separate writer/reviewer executed with a mocked Groq response; no paid provider call |
| Alembic | Applied `0001` to fresh SQLite and `alembic check` found no schema difference; PostgreSQL migration SQL compiled successfully |

## External checks still needed in the deployment environment

- **Groq live inference:** no user API key was supplied, so credentials/quota/network
  behavior was not tested against a live Groq account. Local SDK and mocked Flow work.
- **Chronos-2:** adapter follows the current official pandas API; its optional package
  and model inference were not installed/executed during this run. Benchmark after
  installation on intended hardware before selecting it for operations.
- **Docker/PostgreSQL runtime:** Compose YAML and PostgreSQL SQL generation were checked;
  Docker Engine and a live PostgreSQL server were not available for a container test.
  The supplied CI workflow runs PostgreSQL migrations when used in GitHub Actions.
- **OIDC:** requires the intended identity provider and provisioning configuration;
  no live identity provider was configured here.
- **Production assurance:** backup restoration, load/latency targets, penetration
  testing, full multilingual retrieval and real-store forecast/retrieval quality
  are deployment/pilot gates, not results inferred from synthetic tests.

`constraints-tested.txt` records the actual direct versions present. Tests are not
a complete security audit or a guarantee of business/forecast performance.
