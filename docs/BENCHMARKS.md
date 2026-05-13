# Benchmarks

How to reproduce the measurements that back the README's performance claims.

## Methodology

```bash
cd backend
claimsflow init --reset
claimsflow seed --full --seed 42       # 1000 claims, deterministic
claimsflow demo --count 500             # adjudicate first 500
```

Then query the database for the metrics below. The audit log records per-stage `latency_ms` so we can compute median + p95 per stage.

## Planned measurement suite

| Metric | Source | Why it matters |
| --- | --- | --- |
| Per-stage latency (median, p95) | `audit_logs.event_data.latency_ms` where `event_type = 'stage_completed'` | Pinpoints which stage to optimise; LLM stages dominate |
| End-to-end pipeline latency | `audit_logs.event_data.pipeline_ms` where `event_type = 'decision_rendered'` | The number that matters most for operations sign-off |
| LLM tokens per claim by provider | Currently logged via structlog; needs aggregation | Cost forecasting |
| Medical-necessity cache hit rate | `claimsflow.pipeline.verdict_cache.hit_rate` after the batch | Validates the cache is doing useful work |
| Decision distribution | `SELECT decision_type, COUNT(*) FROM decisions GROUP BY 1` | Sanity check the seed data + pipeline routing |
| Override rate | `COUNT(decided_by != 'system') / COUNT(*)` on decisions | How often humans disagree with the AI |

## Running the benchmark (planned script)

A `claimsflow bench` subcommand is on the roadmap; it would:

1. Reset and reseed deterministically
2. Run the full pipeline against the seeded set
3. Pull all `audit_logs.event_data.latency_ms` values
4. Compute median + p95 per stage
5. Emit a markdown table to stdout

For now run `claimsflow demo` and inspect the structured logs.

## Recorded results

> Populated after a live run on the target hardware. Empty until then — see methodology above to reproduce.

| Stage | Median ms | p95 ms | LLM tokens |
| --- | --- | --- | --- |
| Eligibility | — | — | n/a |
| Provider validation | — | — | n/a |
| Medical necessity (cache hit) | — | — | 0 |
| Medical necessity (LLM call) | — | — | — |
| Fraud detection | — | — | — |
| Cost calculation | — | — | n/a |
| Decision router | — | — | n/a |
| **End-to-end** | — | — | — |
