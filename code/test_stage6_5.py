# code/test_stage6_5.py

from datetime import date
from decimal import Decimal

from payment_candidates import PaymentCandidate
from payment_simulation import (
    CandidateSimulation,
)
from simulator import SimulationResult
from payment_ranking import (
    rank_safe_candidates,
    select_best_safe_candidate,
)


def make_simulation(
    candidate_id,
    payment_method,
    payments,
    total_amount,
    safe=True,
    source_payment_option_id=None,
):
    """
    Build a synthetic CandidateSimulation for testing the
    ranking logic independently from the financial simulator.
    """

    candidate = PaymentCandidate(
        candidate_id=candidate_id,
        payment_method=payment_method,
        payments=tuple(payments),
        total_amount=Decimal(str(total_amount)),
        source_payment_option_id=source_payment_option_id,
    )

    simulation = SimulationResult(
        safe=safe,
        minimum_balance_reached=Decimal("100000"),
        minimum_balance_date=date(2025, 1, 1),
        failure_date=None if safe else date(2025, 1, 10),
        ending_balance=Decimal("100000"),
    )

    return CandidateSimulation(
        candidate=candidate,
        simulation=simulation,
    )


DEADLINE = date(2025, 2, 28)


candidate_a = make_simulation(
    candidate_id="candidate_a",
    payment_method="installments",
    payments=[
        (date(2025, 1, 10), Decimal("1000")),
        (date(2025, 2, 10), Decimal("1000")),
    ],
    total_amount="2000",
    source_payment_option_id="payment_option_10",
)


candidate_b = make_simulation(
    candidate_id="candidate_b",
    payment_method="installments",
    payments=[
        (date(2025, 1, 20), Decimal("900")),
        (date(2025, 2, 20), Decimal("900")),
    ],
    total_amount="1800",
    source_payment_option_id="payment_option_11",
)


candidate_c = make_simulation(
    candidate_id="candidate_c",
    payment_method="full_payment",
    payments=[
        (date(2025, 1, 15), Decimal("2100")),
    ],
    total_amount="2100",
    safe=False,
    source_payment_option_id="payment_option_12",
)


simulations = [
    candidate_a,
    candidate_b,
    candidate_c,
]


ranked = rank_safe_candidates(
    simulations=simulations,
    desired_completion_date=DEADLINE,
)


winner = select_best_safe_candidate(
    simulations=simulations,
    desired_completion_date=DEADLINE,
)


print("=" * 65)
print("STAGE 6.5 — PAYMENT CANDIDATE RANKING")
print("=" * 65)

print(f"Total candidates: {len(simulations)}")
print(f"Safe candidates:  {len(ranked)}")
print()

print("RANKING")
print("-" * 65)

for position, ranked_candidate in enumerate(
    ranked,
    start=1,
):
    candidate = ranked_candidate.simulation.candidate

    print(
        f"{position}. "
        f"{candidate.candidate_id} | "
        f"{candidate.payment_method} | "
        f"total={candidate.total_amount} | "
        f"payments={len(candidate.payments)} | "
        f"deadline={ranked_candidate.completes_by_deadline}"
    )

print()

if winner is None:
    print("Winner: None")
else:
    print(
        "Winner: "
        f"{winner.simulation.candidate.candidate_id}"
    )

print("=" * 65)