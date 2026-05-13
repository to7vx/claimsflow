# 5-Minute Demo Script

A scene-by-scene script for showing ClaimsFlow live. Practise it twice — the goal is to land five specific moments in five minutes.

## Pre-flight (done before the demo starts)

```bash
# Terminal 1 — backend
cd backend && .\.venv\Scripts\Activate.ps1
claimsflow init --reset
claimsflow seed --full --seed 42
claimsflow demo --count 50            # populates dashboard with real decisions
claimsflow serve                       # http://localhost:8000

# Terminal 2 — dashboard
cd frontend && npm run dev             # http://localhost:5173

# Browser open at http://localhost:5173 in dark mode, full screen, one extra terminal visible
```

## Scenes

```text
[00:00 – 00:30]  OPEN THE DASHBOARD
  SAY:  "This is ClaimsFlow — an open-source PoC for auto-adjudicating
         medical insurance claims. It's a demonstration of how to combine
         workflow automation, agentic AI, and healthcare domain modeling."
  POINT: live indicator (pulsing dot, top-left), Auto-adjudication rate,
         Pending reviews, Total paid.

[00:30 – 01:30]  SUBMIT A CLAIM VIA CLI
  SAY:  "Let's watch a real claim flow through the pipeline."
  DO:   In Terminal 2: claimsflow process examples/asthma_routine.json
        (or: curl -X POST http://localhost:8000/api/v1/claims/submit ...)
  SHOW: The progress bar — 6 stages execute in order. CLI prints the
        decision summary.
  SAY:  "Each stage emits a structured audit log entry. Two of the six
         stages call the LLM — medical necessity and fraud reasoning."
  DO:   Switch to the dashboard, refresh — the claim appears in the
        right page (approved → Overview metric ticks up, exception →
        Exception Queue).

[01:30 – 02:30]  OPEN THE EXCEPTION QUEUE
  DO:   Click /queue/exceptions in the nav.
  SAY:  "This is the queue a human reviewer works through. It's sorted
         by priority — a blend of SLA age, amount, and 1-minus-confidence."
  DO:   Press J twice to navigate. Press Enter to open the side panel.
  POINT: AI reasoning is a real paragraph, not a JSON dump.
  POINT: Policy citations and flags listed below.
  POINT: Confidence meter at the top with color.

[02:30 – 03:30]  ACT ON AN EXCEPTION
  SAY:  "I can approve or deny right from here. Both actions are logged
         with my reviewer ID — every override is auditable."
  DO:   Press A to approve. The side panel closes, the row disappears,
        the queue updates live. The Overview metric for Pending reviews
        drops by 1.

[03:30 – 04:15]  SHOW THE FRAUD CASE
  DO:   Click /queue/fraud.
  SAY:  "The seed data includes ~5% deliberate fraud patterns —
         duplicates, provider velocity, amount anomalies, demographic
         mismatch. The rules catch them, then the LLM writes a
         specific reasoning paragraph about what's suspicious."
  DO:   Open one fraud case. Highlight the flags list (e.g.
         'fraud_signal:provider_velocity', 'fraud_signal:duplicate_within_7d').
  SAY:  "Notice the reasoning names the actual pattern — '8 same-day
         claims from the same provider for the same procedure code' —
         instead of just 'unusual'."

[04:15 – 05:00]  SHOW THE BILINGUAL EOB
  DO:   Click /queue/exceptions or go to an approved claim's detail page
        and click "View EOB" or "View bilingual EOB →".
  SAY:  "For approved claims we generate a member-facing Explanation of
         Benefits letter in both English and Arabic, with proper RTL
         layout. The LLM polishes the tone; if it fails we fall back to
         a deterministic template so the member always gets something."
  DO:   Close modal (Esc). Switch tabs to /quality.
  SAY:  "Finally, AI quality — override rate, median confidence, and
         how many decisions had low enough confidence to route to a human
         instead of auto-approving. This is how I'd monitor whether the
         AI is doing more harm than good in production."
```

## If they ask…

| Question | Short answer |
| --- | --- |
| "Why three LLM providers?" | BYOK is a portfolio choice — Ollama for free local demos, Anthropic / OpenAI for production. One Protocol, three implementations behind a settings-driven router. |
| "How do you handle prompt injection in clinical notes?" | I use tool-use / json_schema structured output, so the model can't return arbitrary text into the audit trail. I'd add input filtering and a low-temperature prompt for production. |
| "What if the LLM is wrong?" | Two layers: confidence-based routing (low confidence → human), and the override rate metric (if reviewers keep flipping the AI, that's a signal something's off). Every override is logged with the reviewer ID. |
| "How would you scale this?" | Swap BackgroundTasks for Celery/RQ. Swap the in-memory cache for Redis. Add horizontal Postgres read replicas. The LLM is the bottleneck — cache aggressively. |
| "What's missing for SAMA / CCHI compliance?" | Field-level PHI encryption, signed audit-log chain, retention policies, RBAC, a real authn/z model. They're explicitly out of scope for the PoC — listed in the "What's NOT production-ready" README section. |
| "Why Saudi context?" | The bilingual EOB and Arabic name pools are domain authenticity for the Saudi insurance market — not gimmicks. |

## Closing

> "I'd be happy to go deeper into any of the stages, the LLM provider abstraction, the dashboard side panel, or how I'd take this to production. The repo's open-source — clone it and run `claimsflow demo` if you want to see it again later."
