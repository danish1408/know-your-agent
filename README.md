# Know Your Agent — a safety guard for AI-agent payments

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![scikit-learn](https://img.shields.io/badge/scikit--learn-anomaly%20detection-green)
![Tested](https://img.shields.io/badge/all%20scripts-runnable-brightgreen)
![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey)

When an AI agent pays on your behalf, the fraud controls we rely on today quietly
break. There is no human typing-rhythm or mouse movement to fingerprint, and no one
to send a one-time passcode to — the whole point of the agent is that the human is
away. So instead of asking *"is this the right human, behaving normally?"*, this
project enforces a different, answerable question:

> **Did this agent stay inside the authority a human actually delegated to it?**

It builds that guard in honest, runnable layers — and then **attacks its own guard**
and scores what gets through. Every result below is produced by a script in this repo.

Companion to my [AI Fraud Detection](https://github.com/danish1408) project — the same
honest-evaluation discipline, applied to the new problem of *agentic* payments.

---

## Why this matters

Agent-initiated payments are arriving fast (Meta's Muse and the card networks' agentic
protocols are early examples). The IMF has noted that *"traditional fraud models rely on
human behavioural patterns, which become ineffective when transactions are initiated by
autonomous agents."* That is the gap this project explores: a control that works when
the actor is software, by binding every payment to a **mandate** — a scoped grant of
authority (which categories, which payees, how much, how often) — and refusing anything
outside it, even when the agent itself has been hijacked.

The guard sits **outside** the agent, between it and the payment rail — so it holds even
when the agent's reasoning is fooled. You cannot stop the brain being tricked; you *can*
stop the tricked brain from moving money outside its mandate.

---

## The layers (each file runs on its own)

| File | What it shows |
|---|---|
| `toy_agent.py` | A minimal AI agent: goal → **think / act / observe** loop. The thing the guard protects. |
| `slice1_mandate_guard.py` | **Mandate + scope guard.** Deterministic checks (identity, category, payee, per-payment cap, budget) → **approve / step-up / block**, with a reason. |
| `slice2_hijack_and_guard.py` | A **prompt-injection hijack**: a poisoned web page talks the agent into paying a scammer. Run with the guard off (money lost) vs on (blocked). |
| `slice2_redteam_harness.py` | A **battery of attacks + legitimate traffic**, scored honestly — including attacks the scope guard *cannot* catch. |
| `slice3_risk_guard.py` | A **behavioural risk layer** (amount-vs-baseline, duplicate, novelty) that closes the gaps the scorecard exposed. |
| `slice4_synthetic_and_model.py` | An **unsupervised ML anomaly model** trained on *normal* payments only — detecting fraud with **no fraud labels and no real attack data**. |

```bash
pip install -r requirements.txt
python slice2_redteam_harness.py      # the honest baseline scorecard
python slice3_risk_guard.py           # before/after with the risk layer
python slice4_synthetic_and_model.py  # ML on synthetic data
```

---

## Results (honest, reproducible)

### Slice 2 — red-team the deterministic guard

| | caught | missed | false-blocked |
|---|---|---|---|
| **Attacks (6)** | 4 (67%) | 2 | — |
| **Legit (4)** | — | — | 1 (25%) |

The guard cleanly catches out-of-scope category, unknown payee, impersonation and
over-cap. It **misses** two attacks — *overpaying a valid payee* and a *duplicate charge*
— because both are right-sized payments to an allowed payee, so no static rule fires.
It also **wrongly blocks** one legitimate payment to a new (not pre-listed) payee. A
harness that only threw easy attacks would have scored 100% and proved nothing; these
two misses are the point.

### Slice 3 — add a behavioural risk layer

| metric | before (scope only) | after (scope + risk) |
|---|---|---|
| attacks silently **missed** | 2 | **0** |
| legit **wrongly blocked** | 1 | **0** |

The overpay is now caught by *amount-vs-baseline* (£790 is 2.2× the payee's usual £360),
the duplicate by *duplicate detection*, and the new payee is sent to a **human review
(step-up)** instead of being refused. The honest trade-off, shown in the output: softening
the hard allowlist means unknown-payee attacks are now *escalated to a human* rather than
hard-blocked — nothing is silently allowed, but more cases need review.

### Slice 4 — ML with no fraud data

Trained on 4,000 **normal** payments only (no fraud labels), an Isolation Forest was
tested on unseen normal traffic + labelled attacks:

| attack type | caught |
|---|---|
| overpay a valid payee | **12 / 12** |
| new / unknown payee | ~6 / 12 |
| duplicate charge | 0 / 12 |
| velocity burst | 0 / 12 |

The model nails **amount / novelty** anomalies but is blind to pure **timing** anomalies
(duplicate, velocity), because those are normal on every feature except the gap, and a
general anomaly model dilutes a single off-axis signal.

---

## The key finding: layered, not either/or

No single technique catches everything, and that is the architecture, not a failure:

- **Deterministic rules** own the *exact and countable* — scope, caps, identity,
  duplicates, velocity. Cheap, provable, explainable (what a regulator wants first).
- **ML anomaly detection** owns the *fuzzy and behavioural* — amount-vs-baseline, novelty
  — that is hard to threshold by hand, and it needs only *normal* data to learn.

Slice 3's rules and slice 4's model are **complementary layers**, not competitors.
Knowing *when not to use ML* (a one-line duplicate rule beats a model) is part of the point.

---

## Honest limitations

- **The agent's brain is rule-based, not a real LLM** (so it runs with no API key and you
  can read every decision). The think-act loop is identical to a real agent; swapping in an
  LLM so the hijack is a *genuine* prompt injection is the planned next step.
- **The attacks in slice 4 are synthetic** — patterns I chose — so the model proves the
  *machinery* works, not robustness to novel real-world attacks. Real agent telemetry is the
  asset that only accumulates in production.
- **Scope state is in-memory and single-mandate**; a production guard needs persistence,
  many agents/mandates, cryptographic agent identity, and an agent registry to check against.
- The `risk_score()` function is deliberately simple statistics — it is the slot where a
  trained model drops in (slice 4 is the first step).

---

## What this project demonstrates

- Taking a new, ill-defined problem (agentic-payment fraud) and building a **working,
  layered system** from first principles.
- **Honest evaluation** — red-teaming your own defence and reporting what gets through.
- Applying **fraud-domain expertise** (behavioural baselines, velocity, novelty) to a
  problem with *no training data yet*, using unsupervised ML that needs only normal behaviour.
- Knowing where **rules beat ML** and where ML earns its place.

---

## License

MIT — see [LICENSE](LICENSE).
