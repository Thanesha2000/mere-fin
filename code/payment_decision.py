from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from earliest_safe_date import find_earliest_safe_date
from payment_candidates import (
    PaymentCandidate,
    generate_payment_candidates,
)
from payment_eligibility import filter_eligible_payment_options
from payment_options import PaymentOption
from payment_ranking import (
    RankedCandidate,
    rank_safe_candidates,
)
from payment_simulation import (
    CandidateSimulation,
    simulate_payment_candidates,
)
from safe_amount import find_max_safe_amount


@dataclass(frozen=True)
class PaymentDecisionResult:
    requested_amount: Decimal
    amount_safe_to_pay: Decimal
    earliest_date_for_full_payment: Optional[date]
    eligible_options: tuple[PaymentOption, ...]
    candidates: tuple[PaymentCandidate, ...]
    simulations: tuple[CandidateSimulation, ...]
    ranked_candidates: tuple[RankedCandidate, ...]
    selected_candidate: Optional[RankedCandidate]


def build_payment_decision(
    request_date,
    requested_amount: Decimal,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    horizon_days: int,
    cash_events,
    payment_options: list[PaymentOption],
    payment_methods_user_will_consider,
    max_installment_months,
    allows_partial_payment: bool,
    desired_completion_date,
):
    """
    Run the complete deterministic payment-planning pipeline.

    Stage 5
        -> maximum safe amount

    Stage 5b
        -> earliest safe date

    Stage 6.2
        -> payment-option eligibility

    Stage 6.6
        -> candidate generation

    Stage 6.4
        -> candidate simulation

    Stage 6.5
        -> candidate ranking
    """

    request_date = (
        request_date
        if isinstance(request_date, date)
        else date.fromisoformat(str(request_date))
    )

    requested_amount = Decimal(str(requested_amount))
    starting_balance = Decimal(str(starting_balance))
    minimum_balance_to_keep = Decimal(
        str(minimum_balance_to_keep)
    )

    desired_completion_date = (
        desired_completion_date
        if isinstance(desired_completion_date, date)
        else date.fromisoformat(
            str(desired_completion_date)
        )
    )

    # ---------------------------------------------------------------
    # STAGE 5 — MAXIMUM SAFE AMOUNT
    # ---------------------------------------------------------------

    amount_safe_to_pay = find_max_safe_amount(
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        start_date=request_date,
        horizon_days=horizon_days,
        cash_events=cash_events,
        upper_bound=requested_amount,
    )

    # ---------------------------------------------------------------
    # STAGE 5b — EARLIEST SAFE DATE
    # ---------------------------------------------------------------

    earliest_date_for_full_payment = find_earliest_safe_date(
        requested_amount=requested_amount,
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        request_date=request_date,
        horizon_days=horizon_days,
        cash_events=cash_events,
    )

    # ---------------------------------------------------------------
    # STAGE 6.2 — PAYMENT OPTION ELIGIBILITY
    # ---------------------------------------------------------------

    eligible_options = filter_eligible_payment_options(
        payment_options=payment_options,
        payment_methods_user_will_consider=(
            payment_methods_user_will_consider
        ),
        max_installment_months=max_installment_months,
    )

    # ---------------------------------------------------------------
    # STAGE 6.6 — PAYMENT CANDIDATE GENERATION
    # ---------------------------------------------------------------

    candidates = generate_payment_candidates(
        request_date=request_date,
        requested_amount=requested_amount,
        eligible_payment_options=eligible_options,
        payment_methods_user_will_consider=(
            payment_methods_user_will_consider
        ),
        amount_safe_to_pay=amount_safe_to_pay,
        earliest_date_for_full_payment=(
            earliest_date_for_full_payment
        ),
        desired_completion_date=desired_completion_date,
        allows_partial_payment=allows_partial_payment,
    )

    # ---------------------------------------------------------------
    # STAGE 6.4 — JOINT PAYMENT SIMULATION
    # ---------------------------------------------------------------

    simulations = simulate_payment_candidates(
        candidates=candidates,
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        request_date=request_date,
        horizon_days=horizon_days,
        cash_events=cash_events,
    )

    # ---------------------------------------------------------------
    # STAGE 6.5 — CANDIDATE RANKING
    # ---------------------------------------------------------------

    all_ranked_candidates = rank_safe_candidates(
        simulations=simulations,
        desired_completion_date=desired_completion_date,
    )

    selected_candidate = (
        all_ranked_candidates[0]
        if all_ranked_candidates
        else None
    )

    return PaymentDecisionResult(
        requested_amount=requested_amount,
        amount_safe_to_pay=amount_safe_to_pay,
        earliest_date_for_full_payment=(
            earliest_date_for_full_payment
        ),
        eligible_options=tuple(eligible_options),
        candidates=tuple(candidates),
        simulations=tuple(simulations),
        ranked_candidates=tuple(all_ranked_candidates),
        selected_candidate=selected_candidate,
    )