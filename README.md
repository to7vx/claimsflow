# ClaimsFlow

> AI-powered medical claims auto-adjudication pipeline — a portfolio PoC for the Workflow Automation Engineer Tamheer role at Bupa Arabia.

<p>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-46E5B5?style=flat-square" />
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img alt="Node" src="https://img.shields.io/badge/node-20%2B-339933?style=flat-square&logo=node.js&logoColor=white" />
  <img alt="BYOK" src="https://img.shields.io/badge/BYOK-Anthropic%20%C2%B7%20OpenAI%20%C2%B7%20Ollama-1B232C?style=flat-square" />
  <img alt="Made with Claude" src="https://img.shields.io/badge/Made%20with-Claude-D946EF?style=flat-square" />
</p>

> [!NOTE]
> **Status:** scaffolding (Module 1 of 10). The README will be fully replaced once the dashboard, pipeline, and documentation modules ship — for now it documents the build's current state, not the finished product.

---

## What this is (60-second version)

A claim arrives from a hospital. ClaimsFlow runs it through 6 stages — eligibility, provider validation, medical-necessity reasoning (LLM), fraud detection (rules + LLM), cost calculation, and decision routing — then either auto-approves it, routes it to a human reviewer with a written reasoning paragraph, or holds it for fraud investigation. End-to-end in ~4 seconds.

| Question | Answer |
| --- | --- |
| What does it do? | Auto-adjudicates medical insurance claims with an LLM in the loop on 2 of 6 stages |
| Who is it for? | Insurance operations teams, automation engineers, healthcare PMs |
| What's the demo? | Drop a claim JSON in via CLI or webhook → watch the dashboard decide it live |
| What's the stack? | Python · FastAPI · SQLAlchemy · Postgres / SQLite · React · Tailwind · Ollama / Anthropic / OpenAI |
| How do I run it? | `pip install -e backend && claimsflow init && claimsflow seed && claimsflow serve` |

---

## Quick start (scaffold only — current state)

```bash
# Backend
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q                                           # smoke tests should pass
claimsflow hello                                    # prints "ClaimsFlow v0.1.0 — scaffold OK"
```

```bash
# Frontend
cd frontend
npm install
npm run dev      # http://localhost:5173 — placeholder pages until Module 7
npm test         # Vitest smoke test
```

LLM defaults to local Ollama. Copy `.env.example` to `.env` and pick a provider (`LLM_PROVIDER=ollama|anthropic|openai`).

---

## Project layout

```text
.
├── backend/
│   ├── claimsflow/
│   │   ├── core/           # settings, logging, db session
│   │   ├── models/         # Pydantic + SQLAlchemy (Module 2)
│   │   ├── pipeline/       # 6-stage adjudication pipeline (Module 4)
│   │   ├── providers/      # LLM provider abstraction (Module 3)
│   │   ├── api/            # FastAPI routes (Module 5)
│   │   ├── cli/            # Click CLI (Module 6)
│   │   └── seed/           # Synthetic data generators (Module 2)
│   ├── tests/              # pytest
│   ├── alembic/            # DB migrations
│   └── pyproject.toml
├── frontend/               # React 18 + Vite + TS + Tailwind (Module 7)
├── docs/                   # ARCHITECTURE.md, DEMO_SCRIPT.md, BENCHMARKS.md (Module 10)
├── n8n/                    # Importable n8n workflow JSON (Module 9 — deferred)
├── docker/                 # Dockerfiles (Module 8 — deferred)
└── .github/workflows/ci.yml
```

---

## What's NOT production-ready

This is a portfolio PoC. The following gaps are deliberate; Module 10 documents them in full:

- Synthetic data only — no real PHI/PII handling, no encryption at rest, no SAMA/CCHI certification
- ICD-10 / CPT references use public lists only; no licensed clinical reference data
- No HA, no multi-region, no rate-limit-aware LLM batching
- Not affiliated with Bupa or any insurer — a learning project framed around the domain

---

## License

MIT. See [LICENSE](./LICENSE).
