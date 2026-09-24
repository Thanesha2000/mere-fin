# code/payment_simulation.py

"""
Stage 6.4 — Payment-plan safety simulation.

Evaluates complete PaymentCandidate schedules using the
existing Stage 4 deterministic financial simulator.

This stage does NOT:
- rank candidates
- choose a recommendation
- modify spending
- calculate a new safe amount

It only determines whether each candidate payment plan
keeps the user's balance above the required minimum.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from payment_candidates import PaymentCandidate
from simulator import SimulationResult, simulate


@dataclass(frozen=True)
class CandidateSimulation:
    """
    Result of simulating one complete payment candidate.
    """

    candidate: PaymentCandidate
    simulation: SimulationResult


def simulate_payment_candidate(
    candidate: PaymentCandidate,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    request_date,
    horizon_days: int,
    cash_events,
) -> CandidateSimulation:
    """
    Simulate one complete payment candidate.

    Every payment belonging to the candidate is passed to
    the Stage 4 simulator together with the user's future
    cash events.
    """

    result = simulate(
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        start_date=request_date,
        horizon_days=horizon_days,
        cash_events=cash_events,
        candidate_payments=candidate.payments,
    )

    return CandidateSimulation(
        candidate=candidate,
        simulation=result,
    )


def simulate_payment_candidates(
    candidates: list[PaymentCandidate],
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    request_date,
    horizon_days: int,
    cash_events,
) -> list[CandidateSimulation]:
    """
    Simulate every payment candidate independently.

    Each candidate receives its complete payment schedule.
    """

    results = []

    for candidate in candidates:
        result = simulate_payment_candidate(
            candidate=candidate,
            starting_balance=starting_balance,
            minimum_balance_to_keep=minimum_balance_to_keep,
            request_date=request_date,
            horizon_days=horizon_days,
            cash_events=cash_events,
        )

        results.append(result)

    return results