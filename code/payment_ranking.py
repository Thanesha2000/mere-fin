# code/payment_ranking.py

"""
Stage 6.5 — Payment candidate ranking.

Ranks financially safe payment candidates according to the
deterministic challenge rules.

This stage does NOT:
- simulate financial safety
- modify spending
- generate explanations
- make an LLM-based decision

It only selects the highest-ranked candidate among the
candidates that have already passed financial simulation.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from payment_simulation import CandidateSimulation


@dataclass(frozen=True)
class RankedCandidate:
    """
    Candidate together with the information needed for
    deterministic ranking.
    """

    simulation: CandidateSimulation
    completes_by_deadline: bool
    requires_spending_changes: bool


def _first_payment_date(simulation: CandidateSimulation) -> date:
    """
    Return the date of the candidate's first payment.
    """

    return min(
        payment_date
        for payment_date, _amount
        in simulation.candidate.payments
    )


def _last_payment_date(simulation: CandidateSimulation) -> date:
    """
    Return the date of the candidate's final payment.
    """

    return max(
        payment_date
        for payment_date, _amount
        in simulation.candidate.payments
    )


def _number_of_payments(simulation: CandidateSimulation) -> int:
    """
    Return the number of payments in the candidate.
    """

    return len(simulation.candidate.payments)


def _payment_option_id(simulation: CandidateSimulation) -> str:
    """
    Return the source payment option ID.

    Candidates such as future wait/partial candidates may not
    originate from a supplied payment option, so a deterministic
    fallback is used.
    """

    option_id = simulation.candidate.source_payment_option_id

    if option_id is not None:
        return option_id

    return simulation.candidate.candidate_id


def _ranking_key(
    ranked_candidate: RankedCandidate,
    desired_completion_date: date,
):
    """
    Build the lexicographic ranking key.

    Lower tuple values are preferred.

    Priority:
    1. Complete by deadline
    2. Require no spending changes
    3. Lowest total payable amount
    4. Earliest first payment
    5. Fewest payments
    6. Lowest payment option ID
    """

    simulation = ranked_candidate.simulation

    return (
        not ranked_candidate.completes_by_deadline,
        ranked_candidate.requires_spending_changes,
        simulation.candidate.total_amount,
        _first_payment_date(simulation),
        _number_of_payments(simulation),
        _payment_option_id(simulation),
    )


def rank_safe_candidates(
    simulations: list[CandidateSimulation],
    desired_completion_date,
    requires_spending_changes_by_candidate: Optional[
        dict[str, bool]
    ] = None,
):
    """
    Return safe candidates ordered from highest to lowest priority.

    Unsafe candidates are excluded before ranking.

    Parameters
    ----------
    simulations:
        Results produced by Stage 6.4.

    desired_completion_date:
        Deadline by which the request should be completed.

    requires_spending_changes_by_candidate:
        Mapping from candidate_id to whether that candidate
        requires spending changes.

        Missing candidates default to False because Stage 6.5
        itself does not perform spending-change optimization.
    """

    desired_completion_date = (
        desired_completion_date
        if isinstance(desired_completion_date, date)
        else date.fromisoformat(str(desired_completion_date))
    )

    requires_spending_changes_by_candidate = (
        requires_spending_changes_by_candidate or {}
    )

    ranked_candidates = []

    for simulation in simulations:

        # Unsafe candidates cannot be recommended.
        if not simulation.simulation.safe:
            continue

        last_payment_date = _last_payment_date(simulation)

        completes_by_deadline = (
            last_payment_date <= desired_completion_date
        )

        requires_spending_changes = (
            requires_spending_changes_by_candidate.get(
                simulation.candidate.candidate_id,
                False,
            )
        )

        ranked_candidates.append(
            RankedCandidate(
                simulation=simulation,
                completes_by_deadline=completes_by_deadline,
                requires_spending_changes=(
                    requires_spending_changes
                ),
            )
        )

    ranked_candidates.sort(
        key=lambda candidate: _ranking_key(
            candidate,
            desired_completion_date,
        )
    )

    return ranked_candidates


def select_best_safe_candidate(
    simulations: list[CandidateSimulation],
    desired_completion_date,
    requires_spending_changes_by_candidate: Optional[
        dict[str, bool]
    ] = None,
):
    """
    Select the highest-ranked safe candidate.

    Returns:
        RankedCandidate | None
    """

    ranked_candidates = rank_safe_candidates(
        simulations=simulations,
        desired_completion_date=desired_completion_date,
        requires_spending_changes_by_candidate=(
            requires_spending_changes_by_candidate
        ),
    )

    if not ranked_candidates:
        return None

    return ranked_candidates[0]