# Benchmarks

> Placeholder. Populated after Module 4 (pipeline) ships and Module 10 runs the measurement suite.

Planned measurements:

- Per-stage latency (median, p95) over a 500-claim batch
- LLM token cost per claim by provider (Ollama / Anthropic Haiku / OpenAI mini)
- Medical-necessity cache hit rate
- Decision distribution: % auto-approved · % review · % fraud-hold · % auto-deny
- End-to-end time from `POST /claims/submit` to terminal decision
