"""
agent_payment_guard.py  -  Slice 1 of "Know Your Agent"

THEME: safeguarding humans from autonomous AI.

When an AI agent pays on your behalf, the old fraud controls break - there is no
human typing rhythm to fingerprint, and no one to send an OTP to. So instead of
asking the old question ("is this the right human, behaving normally?"), we
enforce a different, ANSWERABLE one:

        Did this agent stay INSIDE the authority the human actually delegated?

The mechanism is a MANDATE - a scoped grant of authority, e.g. "this agent may
spend up to GBP 1,500 on travel, in the next 48 hours, no single payment above
GBP 800." This is the safety principle of *least agency* made concrete: give the
agent the minimum authority its task needs, and nothing more.

Every agent-initiated payment is checked against its mandate. The guard returns
one of three verdicts, each with a plain-English reason:

    APPROVE   - fully inside the mandate; let it through
    STEP_UP   - allowed but notable -> bounce back to the human to confirm.
                This is where the OTP / liveness check now lives: ONCE, on the
                payment that warrants it, not on every single click.
    BLOCK     - outside the mandate -> refuse.

This is Slice 1: the mandate model + the guard, with a scenario run through it.
  Slice 2 will add a red-team harness (attacks that try to slip past the guard).
  Slice 3 will add risk scoring and richer explainability.

Pure standard library - no dependencies, runs anywhere.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class Verdict(Enum):
    APPROVE = "APPROVE"
    STEP_UP = "STEP_UP"
    BLOCK = "BLOCK"


@dataclass
class Mandate:
    """A scoped grant of authority from a human (the principal) to ONE agent.
    Short-lived and narrow on purpose - that narrowness is the safety."""
    agent_id: str
    principal: str                 # the human / legal entity delegating authority
    purpose: str                   # human-readable reason (kept for the audit trail)
    allowed_categories: set        # merchant categories the agent may pay
    per_txn_cap: float             # ceiling on any single payment
    total_budget: float            # ceiling on cumulative spend
    step_up_over: float            # payments at/above this must be confirmed by a human
    valid_from: datetime
    valid_until: datetime
    allowed_payees: set = field(default_factory=set)   # empty = any payee within an allowed category


@dataclass
class PaymentRequest:
    """A single payment an agent is trying to make."""
    agent_id: str
    payee: str
    category: str
    amount: float
    at: datetime


@dataclass
class Decision:
    verdict: Verdict
    reason: str


class Guard:
    """Sits between the agent and the payment rail. Holds one mandate plus the
    running total spent under it, and rules on each payment request."""

    def __init__(self, mandate: Mandate):
        self.mandate = mandate
        self.spent = 0.0           # cumulative APPROVED spend so far

    def evaluate(self, req: PaymentRequest) -> Decision:
        m = self.mandate

        # ---- hard scope checks: any failure is a BLOCK ----------------------

        # 1. identity - is this even the agent the human authorised?
        if req.agent_id != m.agent_id:
            return Decision(Verdict.BLOCK,
                f"agent impersonation: '{req.agent_id}' is not the mandated agent '{m.agent_id}'")

        # 2. time window - the mandate is only live for a short, defined period
        if not (m.valid_from <= req.at <= m.valid_until):
            return Decision(Verdict.BLOCK,
                "mandate not active: payment is outside the authorised time window")

        # 3. category - the agent may only buy what it was sent to buy
        if req.category not in m.allowed_categories:
            return Decision(Verdict.BLOCK,
                f"category '{req.category}' is not permitted by the mandate")

        # 4. payee allowlist (only if the mandate pins specific payees)
        #    The anti-hijack / anti-payee-swap check: a right-sized, right-category
        #    payment to the WRONG recipient is still refused.
        if m.allowed_payees and req.payee not in m.allowed_payees:
            return Decision(Verdict.BLOCK,
                f"payee '{req.payee}' is not on the mandate's allowed list")

        # 5. per-transaction cap
        if req.amount > m.per_txn_cap:
            return Decision(Verdict.BLOCK,
                f"amount GBP {req.amount:,.2f} exceeds the per-payment cap of GBP {m.per_txn_cap:,.2f}")

        # 6. cumulative budget - stops a slow drain across many small payments
        if self.spent + req.amount > m.total_budget:
            remaining = m.total_budget - self.spent
            return Decision(Verdict.BLOCK,
                f"budget exhausted: GBP {req.amount:,.2f} would exceed the GBP {remaining:,.2f} remaining")

        # ---- inside scope: approve, or step up to the human -----------------
        # The step-up band is where the human check now lives: once, on the
        # payment that warrants it, rather than an OTP on every single click.
        if req.amount >= m.step_up_over:
            return Decision(Verdict.STEP_UP,
                f"amount GBP {req.amount:,.2f} is at/above the GBP {m.step_up_over:,.2f} "
                f"step-up line - confirm with the human before releasing")

        # fully inside the mandate -> approve and record the spend
        self.spent += req.amount
        return Decision(Verdict.APPROVE,
            f"within mandate (spent so far GBP {self.spent:,.2f} of GBP {m.total_budget:,.2f})")


# ==========================================================================
#  Scenario:  a travel agent booking a Lisbon weekend, with two attacks mixed in
# ==========================================================================
def run_demo():
    now = datetime(2026, 9, 27, 21, 0)     # fixed time so the run is reproducible

    mandate = Mandate(
        agent_id="travel-agent-007",
        principal="Danish Shabbir",
        purpose="Book a weekend in Lisbon, budget GBP 1,500",
        allowed_categories={"airline", "hotel", "car_hire"},
        per_txn_cap=800.0,
        total_budget=1500.0,
        step_up_over=600.0,
        valid_from=now,
        valid_until=now + timedelta(hours=48),
        allowed_payees=set(),              # category-only mandate for this demo
    )

    guard = Guard(mandate)

    requests = [
        # payee                  agent_id            category    amount   when
        PaymentRequest("travel-agent-007", "TAP Air Portugal",  "airline",  420.00, now + timedelta(minutes=2)),
        PaymentRequest("travel-agent-007", "Lisbon Marriott",   "hotel",    650.00, now + timedelta(minutes=5)),
        PaymentRequest("travel-agent-007", "Europcar",          "car_hire", 120.00, now + timedelta(minutes=6)),
        PaymentRequest("travel-agent-007", "CryptoDrainer Ltd", "crypto",   500.00, now + timedelta(minutes=7)),
        PaymentRequest("travel-agent-007", "Grand Hotel",       "hotel",    900.00, now + timedelta(minutes=8)),
        PaymentRequest("rogue-agent-666",  "TAP Air Portugal",  "airline",  200.00, now + timedelta(minutes=9)),
        PaymentRequest("travel-agent-007", "Sintra Lodge",      "hotel",    500.00, now + timedelta(minutes=10)),
        PaymentRequest("travel-agent-007", "Cascais Resort",    "hotel",    600.00, now + timedelta(minutes=11)),
    ]

    # what each request is meant to demonstrate (for readability of the output)
    notes = [
        "normal booking",
        "large-ish -> should pause for the human",
        "normal booking",
        "HIJACK: agent told (by poisoned content) to pay a crypto drainer",
        "over the single-payment cap",
        "IMPERSONATION: a different agent using this mandate",
        "normal booking",
        "would push total over the GBP 1,500 budget",
    ]

    print("=" * 78)
    print("KNOW YOUR AGENT - payment guard (Slice 1)")
    print("=" * 78)
    print(f"Principal : {mandate.principal}")
    print(f"Agent     : {mandate.agent_id}")
    print(f"Mandate   : {mandate.purpose}")
    print(f"Scope     : {sorted(mandate.allowed_categories)} | per-payment <= GBP "
          f"{mandate.per_txn_cap:,.0f} | budget GBP {mandate.total_budget:,.0f} | "
          f"step-up >= GBP {mandate.step_up_over:,.0f}")
    print("=" * 78)

    tally = {Verdict.APPROVE: 0, Verdict.STEP_UP: 0, Verdict.BLOCK: 0}
    for i, (req, note) in enumerate(zip(requests, notes), 1):
        d = guard.evaluate(req)
        tally[d.verdict] += 1
        print(f"\n{i}. {req.payee:<18} {req.category:<9} GBP {req.amount:>8,.2f}   ({note})")
        print(f"   -> {d.verdict.value:<8} {d.reason}")

    print("\n" + "=" * 78)
    print(f"Summary: {tally[Verdict.APPROVE]} approved, "
          f"{tally[Verdict.STEP_UP]} stepped up to the human, "
          f"{tally[Verdict.BLOCK]} blocked.")
    print(f"Total released automatically: GBP {guard.spent:,.2f} "
          f"of GBP {mandate.total_budget:,.0f} authorised.")
    print("=" * 78)
    print("\nNote: this slice enforces SCOPE only (identity, time, category, payee,")
    print("caps, budget). It does not yet score risk or model velocity/behaviour -")
    print("that is Slice 3. And it has not yet been attacked systematically - the")
    print("red-team harness that measures what slips through is Slice 2.")


if __name__ == "__main__":
    run_demo()
