# Security, privacy and operations

## Access

Every service re-checks active SQL membership. Knowing another tenant's UUID does
not grant access. UI hiding is supplementary; tests exercise service boundaries.

| Role | Sales | Inventory | Forecast | Customers | Finance | HR | Knowledge | Approvals | Admin |
|---|---|---|---|---|---|---|---|---|---|
| Owner | Read/write | Read/write | Run | Read | Read/write | Read/write | Read/write/delete | Decide | Yes |
| Manager | Read/write | Read/write | Run | Read | Read | No | General/finance read/write | Decide | No |
| Sales | Read/write | Read | No | Read | No | No | General read | Read | No |
| Inventory | Read | Read/write | Run | No | No | No | General read | Read | No |
| Finance | Read | Read | No | No | Read/write | No | General/finance read | Read | No |
| HR | No | No | No | No | No | Read/write | General/HR read/write | No | No |
| Analyst | Read | Read | Run | Read | No | No | General read | No | No |

All authenticated roles can ask permitted chatbot questions. Saved report reads
also check the report domain. Sales staff cannot save shared reports; other roles
can save permitted scopes. Jobs expose results only to their requester and re-check
the result domain after a role change. Only owner/manager manage schedules. Only
owners delete sources because that action invalidates cross-source artifacts.

Password sessions are server-side hashed random tokens with an eight-hour default
expiry. Password hashes use random salt and PBKDF2-SHA256 (600,000 iterations).
Repeated email login failures are throttled. OIDC is an optional identity-provider
adapter; MFA, recovery, account linking and organizational provisioning must be
configured before shared deployment. Role changes revoke current sessions.

## Boundaries implemented in the app

- SQLAlchemy parameterized queries; no model-generated SQL or code execution.
- Streamlit XSRF/CORS protections enabled; displayed HTML is fixed or escaped.
- Upload limits, extension checks, workbook expansion limits and macro rejection.
- UUID tenant folders; user filenames cannot choose storage paths.
- Source extraction treats content as data. LLMs have no execution tools.
- Permission filtering before reranking, context construction and report downloads.
- FAISS reads only server-created indexes, verifying a stored checksum before load;
  never accept an uploaded FAISS/pickle index.
- Public fetches validate every DNS address/redirect, reject private/loopback/link-local
  networks and pin a validated destination IP while retaining TLS hostname verification.
- External calls require server gates plus workspace-owner consent. Search accepts
  public terms only; it is not automatically populated with private store records.
- Groq receives relevant authorized excerpts and aggregate calculations. Obvious
  emails/long numeric identifiers are redacted. This is not comprehensive PII detection:
  owners must classify/redact sensitive documents before approving third-party use.
- Approval binds exact payload, cost and prior price. Atomic state changes prevent
  duplicate receipt/price application. No outbound order/payment/messaging integration.
- CSV and XLSX neutralize spreadsheet formula text, including untrusted headers.
- Source deletion removes raw dataset rows/files or knowledge text/indexes, invalidates
  stored reports/answers, cancels work and resets session-derived state on next rerun.

## Controls provided by deployment

Use HTTPS, restricted inbound access, a non-root process, encrypted volumes and
database backups. Keep `.env`, OIDC secrets and raw data out of source control.
Set `ALLOW_DEMO=false`, `ALLOW_SIGNUP=false` and `DEBUG_ERRORS=false` after onboarding
for a shared production installation. Add reverse-proxy request/connection limits
and a malware scanner for untrusted documents. Application account throttling is
not a replacement for network-level abuse controls.

Tenant isolation is enforced in services, not PostgreSQL row-level security.
Do not give business users direct database access. For high-assurance SaaS, add RLS,
separate worker identities, comprehensive penetration testing and resource quotas.
Audit records are application-managed; they are not tamper-evident against a database
administrator. Export them to an independently controlled audit system if required.

## Retention, backup and incident procedure

The default proposed derived-data retention is 90 days. It is a configurable policy,
not a silent background deletion. An operator can inspect eligible records with
`python -m scripts.retention --days 90`, then deliberately apply with `--apply`.
This clears old reports, assistant runs, research, terminal jobs and login attempts,
plus expired sessions; it preserves source records, approvals and audit records.
Source retention and backup expiry need an agreed business policy and owner review.

Back up PostgreSQL and the uploads/index folders together at a quiet point, encrypt
the backup, and test restoration into an isolated environment. SQLite backups must
use its backup API or a stopped app/worker; copying an active WAL database alone is
not a consistent backup. Keep model caches reproducible rather than backing up
weights with confidential data. Never expose backup URLs publicly.

For an incident: restrict access, stop affected integrations/workers, revoke sessions,
rotate involved credentials, preserve audit evidence, determine affected records and
notify according to the organization's obligations. Restore/test before reopening.
Source deletion cannot recall reports already downloaded or copies retained by an
external provider. Jurisdiction, employee/customer notices, lawful processing,
provider retention and cross-border rules need organizational review; the app does
not claim legal certification or automatic compliance.
