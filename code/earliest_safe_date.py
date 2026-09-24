# code/earliest_safe_date.py
"""
Stage 5b — Earliest safe date solver.

Finds the earliest date on which the user's full requested
amount can safely be paid.

Uses the Stage 4 simulator as the safety oracle.

Stage 5 answers:
    "How much can I safely pay today?"

Stage 5b answers:
    "When can I safely pay the full requested amount?"

Returns:
    - the earliest safe date, if one exists within the
      forecast horizon
    - None, if the full payment never becomes safe
      within the forecast horizon
"""

from datetime import date, timedelta
from decimal import Decimal

from simulator import simulate


def _is_full_payment_safe(
    payment_date,
    requested_amount: Decimal,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    request_date,
    horizon_days: int,
    cash_events,
) -> bool:
    """
    Ask Stage 4 whether the full requested amount is safe
    when paid on payment_date.
    """

    result = simulate(
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        start_date=request_date,
        horizon_days=horizon_days,
        cash_events=cash_events,
        candidate_payments=[
            (payment_date, requested_amount)
        ],
    )

    return result.safe


def find_earliest_safe_date(
    requested_amount: Decimal,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    request_date,
    horizon_days: int,
    cash_events,
):
    """
    Find the earliest date on which the full requested amount
    can safely be paid.

    Parameters
    ----------
    requested_amount:
        Full amount the user wants to pay.

    starting_balance:
        User's available balance on request_date.

    minimum_balance_to_keep:
        Minimum balance that must never be violated.

    request_date:
        Date on which the request is made.

    horizon_days:
        Number of days available for the search.

    cash_events:
        Real + projected future cash events from Stage 3.

    Returns
    -------
    date | None
        Earliest safe payment date, or None if the full amount
        never becomes safe within the forecast horizon.
    """

    request_date = (
        request_date
        if isinstance(request_date, date)
        else date.fromisoformat(str(request_date))
    )

    requested_amount = Decimal(
        str(requested_amount)
    )

    starting_balance = Decimal(
        str(starting_balance)
    )

    minimum_balance_to_keep = Decimal(
        str(minimum_balance_to_keep)
    )

    # ---------------------------------------------------------
    # Invalid / zero request
    # ---------------------------------------------------------

    if requested_amount <= Decimal("0"):
        return request_date

    # ---------------------------------------------------------
    # Search every date from request_date through the end
    # of the forecast horizon.
    # ---------------------------------------------------------

    for offset in range(horizon_days + 1):

        candidate_date = (
            request_date
            + timedelta(days=offset)
        )

        if _is_full_payment_safe(
            payment_date=candidate_date,
            requested_amount=requested_amount,
            starting_balance=starting_balance,
            minimum_balance_to_keep=minimum_balance_to_keep,
            request_date=request_date,
            horizon_days=horizon_days,
            cash_events=cash_events,
        ):
            return candidate_date

    # Full payment never becomes safe within the forecast.
    return None