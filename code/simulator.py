# code/simulator.py

"""
Stage 4 — 90-day deterministic balance simulator.

Purpose:
    Given:
        - starting available balance
        - minimum balance that must be preserved
        - future cash events
        - candidate payment(s)

    determine whether the user's balance ever falls below
    the required minimum.

No LLM.
No external API.
No randomness.
Same inputs -> same result.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass
class SimulationResult:
    safe: bool
    minimum_balance_reached: Decimal
    minimum_balance_date: date
    failure_date: date | None
    ending_balance: Decimal


def simulate(
    starting_balance,
    minimum_balance_to_keep,
    start_date,
    horizon_days,
    cash_events,
    candidate_payments=None,
):
    """
    Simulate the user's balance over a fixed horizon.

    Parameters
    ----------
    starting_balance:
        Available balance on start_date.

    minimum_balance_to_keep:
        Balance that must never be breached.

    start_date:
        First date of the simulation.

    horizon_days:
        Number of days to simulate.

    cash_events:
        Reconciled/projected CashEvent objects.

    candidate_payments:
        List of:
            (payment_date, payment_amount)

        Payments are treated as debits.

    Returns
    -------
    SimulationResult
    """

    start_date = (
        start_date
        if isinstance(start_date, date)
        else date.fromisoformat(str(start_date))
    )

    starting_balance = Decimal(str(starting_balance))
    minimum_balance_to_keep = Decimal(str(minimum_balance_to_keep))

    end_date = start_date + timedelta(days=horizon_days)

    candidate_payments = candidate_payments or []

    timeline = []

    # ------------------------------------------------------------
    # 1. Add future cash events
    # ------------------------------------------------------------

    for event in cash_events:
        if event.cash_date < start_date:
            continue

        if event.cash_date > end_date:
            continue

        if event.cash_amount is None:
            continue

        amount = Decimal(str(event.cash_amount))

        if event.cash_direction == "credit":
            delta = amount
        else:
            delta = -amount

        timeline.append(
            (
                event.cash_date,
                delta,
                f"cash_event:{event.event_id}",
            )
        )

    # ------------------------------------------------------------
    # 2. Add candidate payments
    # ------------------------------------------------------------

    for payment_date, payment_amount in candidate_payments:

        if not isinstance(payment_date, date):
            payment_date = date.fromisoformat(str(payment_date))

        if payment_date < start_date:
            continue

        if payment_date > end_date:
            continue

        amount = Decimal(str(payment_amount))

        timeline.append(
            (
                payment_date,
                -abs(amount),
                "candidate_payment",
            )
        )

    # ------------------------------------------------------------
    # 3. Sort chronologically
    # ------------------------------------------------------------

    timeline.sort(key=lambda item: item[0])

    # ------------------------------------------------------------
    # 4. Run simulation
    # ------------------------------------------------------------

    balance = starting_balance

    minimum_balance_reached = balance
    minimum_balance_date = start_date

    failure_date = None

    for event_date, delta, _source in timeline:

        balance += delta

        if balance < minimum_balance_reached:
            minimum_balance_reached = balance
            minimum_balance_date = event_date

        if (
            balance < minimum_balance_to_keep
            and failure_date is None
        ):
            failure_date = event_date

    # ------------------------------------------------------------
    # 5. Return deterministic result
    # ------------------------------------------------------------

    return SimulationResult(
        safe=(failure_date is None),
        minimum_balance_reached=minimum_balance_reached,
        minimum_balance_date=minimum_balance_date,
        failure_date=failure_date,
        ending_balance=balance,
    )