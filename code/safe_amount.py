# code/safe_amount.py
"""
Stage 5 — Maximum safe amount solver.

Uses the Stage 4 simulator as the safety oracle and finds the
maximum amount that can be paid today without allowing the user's
balance to fall below the required minimum during the forecast
horizon.

Stage 5 does NOT decide:
- payment method
- installment plan
- spending reductions
- affordability status wording

Those decisions belong to later stages.

The solver only answers:

    "What is the maximum amount that can safely be paid today?"
"""

from datetime import date
from decimal import Decimal, ROUND_DOWN

from simulator import simulate


CENT = Decimal("0.01")


def _to_cents(amount: Decimal) -> int:
    """
    Convert a Decimal monetary amount into integer cents/paise.

    Example:
        Decimal("100.25") -> 10025
    """
    amount = Decimal(str(amount))

    return int(
        (amount * 100).to_integral_value(
            rounding=ROUND_DOWN
        )
    )


def _from_cents(cents: int) -> Decimal:
    """
    Convert integer cents/paise back into a Decimal amount.

    Example:
        10025 -> Decimal("100.25")
    """
    return (
        Decimal(cents) / Decimal("100")
    ).quantize(CENT)


def _is_safe(
    amount: Decimal,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    start_date,
    horizon_days: int,
    cash_events,
) -> bool:
    """
    Ask Stage 4 whether a candidate payment is safe.

    Stage 4 expects candidate_payments in the form:

        [(payment_date, payment_amount)]

    rather than simply:

        [payment_amount]
    """

    result = simulate(
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        start_date=start_date,
        horizon_days=horizon_days,
        cash_events=cash_events,
        candidate_payments=[
            (start_date, amount)
        ],
    )

    return result.safe


def find_max_safe_amount(
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    start_date,
    horizon_days: int,
    cash_events,
    upper_bound: Decimal,
) -> Decimal:
    """
    Find the maximum amount that can safely be paid today.

    Parameters
    ----------
    starting_balance:
        User's available balance at the request date.

    minimum_balance_to_keep:
        Minimum balance that must never be violated.

    start_date:
        Date on which the candidate payment is made.

    horizon_days:
        Number of days over which Stage 4 should simulate
        the user's financial state.

    cash_events:
        Future real + projected cash events from Stage 3.

    upper_bound:
        Maximum amount that should be considered.
        Normally this is the user's requested amount.

    Returns
    -------
    Decimal
        Maximum safe payment amount.
    """

    starting_balance = Decimal(str(starting_balance))

    minimum_balance_to_keep = Decimal(
        str(minimum_balance_to_keep)
    )

    upper_bound = Decimal(str(upper_bound))

    # ---------------------------------------------------------
    # Guard against invalid input
    # ---------------------------------------------------------

    if upper_bound <= Decimal("0"):
        return Decimal("0.00")

    # A payment cannot be greater than the currently
    # available balance.
    #
    # Future income is deliberately NOT used to increase
    # the upper bound here. Stage 4 determines safety based
    # on the complete future timeline.
    upper_bound = min(
        upper_bound,
        starting_balance,
    )

    # ---------------------------------------------------------
    # Convert the search range into integer cents/paise.
    #
    # This gives us exact 0.01 precision.
    # ---------------------------------------------------------

    low = 0
    high = _to_cents(upper_bound)

    best_safe_cents = 0

    # ---------------------------------------------------------
    # Binary search
    # ---------------------------------------------------------

    while low <= high:
        mid = (low + high) // 2

        candidate = _from_cents(mid)

        if _is_safe(
            amount=candidate,
            starting_balance=starting_balance,
            minimum_balance_to_keep=minimum_balance_to_keep,
            start_date=start_date,
            horizon_days=horizon_days,
            cash_events=cash_events,
        ):
            # Candidate is safe.
            #
            # Save it and search for an even larger
            # safe amount.
            best_safe_cents = mid
            low = mid + 1

        else:
            # Candidate is unsafe.
            #
            # Search only smaller amounts.
            high = mid - 1

    return _from_cents(best_safe_cents)