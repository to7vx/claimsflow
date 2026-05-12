# Architecture

> Detailed technical documentation. Updated after each module ships.

## Current state — Module 1 (scaffold)

```mermaid
flowchart LR
    A[Hospital / Provider] -.->|future: n8n| API
    CLI[CLI<br/>claimsflow process] -->|Module 6| API
    API[FastAPI<br/>Module 5] -->|Module 4| PIPE[6-Stage Pipeline]
    PIPE -->|reads/writes| DB[(Postgres / SQLite)]
    PIPE -->|calls| LLM{LLM Provider<br/>Ollama · Anthropic · OpenAI}
    DASH[React Dashboard<br/>Module 7] -->|HTTP| API
```

Nothing in the diagram above is implemented yet — only the package skeleton, configuration, and CI exist after Module 1. Subsequent modules fill in each box.

## Module 1 — what shipped

- Python package `claimsflow` with subpackages for each layer (core / models / pipeline / providers / api / cli / seed)
- Typed settings (`pydantic-settings`) with `.env` loading
- Structured logging via `structlog` — JSON in production, color in dev
- SQLAlchemy 2.x engine + session factory keyed on `DATABASE_URL`
- Alembic environment wired to the same settings + metadata
- React 18 + Vite + TypeScript + Tailwind frontend with custom design tokens (Manrope / JetBrains Mono, deliberate non-default palette)
- Pre-commit (ruff + black + frontend eslint)
- GitHub Actions CI: backend lint + test, frontend lint + test + build
- MIT license + comprehensive `.gitignore`

## Decisions locked in Module 1

| Decision | Why | Alternative | Trade-off |
| --- | --- | --- | --- |
| Pydantic-settings over raw `os.environ` | Type-safe, validated, cached, IDE-friendly | `python-dotenv` + manual reads | Slight extra dep |
| SQLAlchemy 2.x typed `DeclarativeBase` | Modern API, mypy-friendly, future-proof | SQLAlchemy 1.x classic API | Steeper migration if upstream changes |
| `lru_cache`-backed singletons (`get_settings`, `get_engine`) | Cheap, thread-safe, test-overridable via `cache_clear()` | Module-level globals | Slight indirection |
| Manrope + JetBrains Mono pairing | Geometric humanist + technical mono — not generic Inter | Inter / Plex | Loads from Google Fonts |
| Tailwind config with custom `decision.*` color tokens | Constrains the dashboard to a deliberate palette | shadcn defaults | Less plug-and-play |

## Module 2 — what shipped

- 6 ORM entities (`Plan`, `Member`, `Provider`, `Claim`, `Decision`, `AuditLog`) with proper relationships including self-referential `Member.dependents`
- Pydantic v2 schemas mirroring the ORM, plus `ClaimSubmission` for the API ingest shape (validates non-empty diagnosis/procedure/line-item lists)
- StrEnum-backed enums shared across ORM, Pydantic, and pipeline layers
- Alembic initial migration generated from the metadata; verified end-to-end against fresh SQLite
- Synthetic-data generators producing Saudi-realistic data: Arabic + English names from curated pools, ICD-10 codes covering common Saudi diagnoses (diabetes, hypertension, asthma, plus pediatric subset), CPT codes with realistic SAR pricing
- Deterministic generation (seeded `random.Random`) so the same seed always produces the same dataset — required for reproducible tests and benchmarks
- Intentional data variety: ~5% fraud-pattern claims (velocity, duplicates, procedure-diagnosis mismatch), ~15% exception cases (out-of-network, soft flags), ~80% routine
- `claimsflow init [--reset]` and `claimsflow seed [--small|--full]` CLI commands with Rich progress + summary tables

### ER diagram (Module 2)

```mermaid
erDiagram
    PLAN ||--o{ MEMBER : "covers"
    MEMBER ||--o{ CLAIM : "submits"
    MEMBER ||--o{ MEMBER : "primary -> dependents"
    PROVIDER ||--o{ CLAIM : "services"
    CLAIM ||--o| DECISION : "yields"
    CLAIM ||--o{ AUDIT_LOG : "logged"

    PLAN { string plan_id PK
           string plan_name
           json   covered_benefits
           json   exclusions
           float  copay_percent
           float  annual_limit_default }
    MEMBER { string member_id PK
             string full_name_en
             string full_name_ar
             string national_id
             string plan_id FK
             string policy_status
             float  annual_limit
             float  used_amount }
    PROVIDER { string provider_id PK
               string name_en
               string name_ar
               string provider_type
               string network_tier
               string city
               float  fraud_risk_score }
    CLAIM { string claim_id PK
            string claim_type
            string member_id FK
            string provider_id FK
            json   diagnosis_codes
            json   procedure_codes
            json   line_items
            float  total_billed
            string status }
    DECISION { string decision_id PK
               string claim_id FK
               string decision_type
               float  amount_approved
               float  confidence_score
               text   reasoning
               json   policy_citations }
    AUDIT_LOG { int    log_id PK
                string claim_id FK
                string event_type
                json   event_data }
```

## Pending modules

- **Module 3 — LLM provider abstraction** (next)
- **Module 4 — 6-stage pipeline**
- **Module 5 — FastAPI service**
- **Module 6 — Click CLI**
- **Module 7 — React dashboard**
- **Module 10 — Full documentation**

Modules 8 (Docker) and 9 (n8n) are deferred — the interview-ready scope prioritizes the dashboard and pipeline.
