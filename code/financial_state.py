# code/financial_state.py
"""
Stage 3 — Financial state builder.

Consumes Stage 2's `resolved` CashEvents (list of dataclasses, NOT a
DataFrame) and produces one user's point-in-time financial snapshot:
opening balance, minimum floor, and every known future cash movement
(real + recurrence-projected) converted into home_currency.

CRITICAL: current_available_balance from the profile ALREADY reflects
all settled history. historical_income/historical_expenses below are
returned for display/explanation text ONLY — never add them back into
the balance in Stage 4's simulator, or you double-count.
"""

from pathlib import Path
from decimal import Decimal
import pandas as pd

from reconcile import CashEvent
from project_recurrence import project_recurring

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"


def load_exchange_rates() -> pd.DataFrame:
    rates = pd.read_csv(DATASET / "exchange_rates.csv")
    rates["rate_date"] = pd.to_datetime(rates["rate_date"])
    rates["rate"] = rates["rate"].apply(lambda x: Decimal(str(x)))
    return rates


def find_direct_rate(
    rates: pd.DataFrame,
    from_currency: str,
    to_currency: str,
    date,
) -> Decimal | None:
    """Latest direct rate on or before date. No reverse/invented rates — spec forbids it."""
    if from_currency == to_currency:
        return Decimal("1")

    date = pd.Timestamp(date)

    matches = rates[
        (rates["from_currency"] == from_currency)
        & (rates["to_currency"] == to_currency)
        & (rates["rate_date"] <= date)
    ]

    if matches.empty:
        return None

    return matches.sort_values("rate_date").iloc[-1]["rate"]


def convert_amount(
    amount,
    from_currency: str,
    to_currency: str,
    date,
    rates: pd.DataFrame,
) -> Decimal | None:
    if amount is None:
        return None

    rate = find_direct_rate(
        rates,
        from_currency,
        to_currency,
        date,
    )

    if rate is None:
        return None

    return Decimal(str(amount)) * rate


def build_financial_state(
    user_id: str,
    request_date,
    profile: dict,
    cash_events: list[CashEvent],
    rates: pd.DataFrame,
) -> dict:
    """
    cash_events: Stage 2's build_cash_events(...)["resolved"], PRE-FILTERED
    to this user only (Stage 2 runs across all users; filter before calling
    this function).
    """

    request_ts = pd.Timestamp(request_date)
    home_currency = profile["home_currency"]

    dropped_conversions = 0
    converted: list[tuple[CashEvent, Decimal | None]] = []

    # ---------------------------------------------------------
    # 1. Convert every resolved cash event into home currency
    # ---------------------------------------------------------
    for ev in cash_events:
        amt = convert_amount(
            ev.cash_amount,
            ev.currency,
            home_currency,
            ev.cash_date,
            rates,
        )

        if amt is None:
            dropped_conversions += 1

        converted.append((ev, amt))

    # ---------------------------------------------------------
    # 2. Split historical vs future events
    # ---------------------------------------------------------
    historical = [
        (e, a)
        for e, a in converted
        if a is not None
        and pd.Timestamp(e.cash_date) <= request_ts
    ]

    future = [
        (e, a)
        for e, a in converted
        if a is not None
        and pd.Timestamp(e.cash_date) > request_ts
    ]

    def total(pairs, direction):
        return sum(
            (
                a
                for e, a in pairs
                if e.cash_direction == direction
            ),
            Decimal("0"),
        )

    # ---------------------------------------------------------
    # 3. Project recurring future cash events
    # ---------------------------------------------------------
    #
    # The forecast horizon is 90 days from the request date.
    #
    # Only settled historical events are used to infer recurrence.
    # Real future events are passed to the recurrence engine so that
    # projected occurrences do not duplicate events already present
    # in the dataset.
    # ---------------------------------------------------------

    forecast_end = request_ts.date() + pd.Timedelta(days=90)

    settled_only = [
        e
        for e in cash_events
        if e.source_status == "settled"
    ]

    real_future_raw = [
        e
        for e, a in future
    ]

    projected = project_recurring(
        settled_events=settled_only,
        request_date=request_ts.date(),
        forecast_end=forecast_end,
        real_future_events=real_future_raw,
    )

    # ---------------------------------------------------------
    # 4. Convert projected events into home currency
    # ---------------------------------------------------------

    projected_converted = []

    for ev in projected:
        amt = convert_amount(
            ev.cash_amount,
            ev.currency,
            home_currency,
            ev.cash_date,
            rates,
        )

        if amt is not None:
            projected_converted.append((ev, amt))

    # Add projected events to real future events.
    future = future + projected_converted

    # ---------------------------------------------------------
    # 5. Build final financial state
    # ---------------------------------------------------------

    return {
        "user_id": user_id,
        "request_date": request_ts.date(),
        "home_currency": home_currency,

        # This is the user's actual available balance from the profile.
        # Historical cash flows must NOT be added again.
        "current_available_balance": Decimal(
            str(profile["current_available_balance"])
        ),

        "minimum_balance_to_keep": Decimal(
            str(profile["minimum_balance_to_keep"])
        ),

        # Diagnostic / explanation values only.
        # These are already reflected in current_available_balance.
        "historical_income": total(
            historical,
            "credit",
        ),

        "historical_expenses": total(
            historical,
            "debit",
        ),

        "future_income": total(
            future,
            "credit",
        ),

        "future_expenses": total(
            future,
            "debit",
        ),

        # Stage 4 simulator consumes these directly.
        "future_events": [
            e
            for e, a in future
        ],

        "dropped_conversions": dropped_conversions,
    }


if __name__ == "__main__":
    from data_loader import load_data
    from reconcile import build_cash_events
    from build_events import events_df_to_raw_events

    data = load_data()
    profiles = data["profiles"]
    rates = load_exchange_rates()

    raw_events = events_df_to_raw_events(
        data["events"]
    )

    cash = build_cash_events(raw_events)
    resolved_all = cash["resolved"]

    if cash["unresolved"]:
        print(
            f"⚠ {len(cash['unresolved'])} events missing amount "
            f"— needs image extraction"
        )

    if cash["ambiguous_chains"]:
        print(
            f"⚠ {len(cash['ambiguous_chains'])} chains flagged "
            f"ambiguous — review manually"
        )

    TEST_USER = "user_212"
    TEST_DATE = "2025-02-05"

    profile = profiles[
        profiles["user_id"] == TEST_USER
    ].iloc[0]

    user_cash_events = [
        c
        for c in resolved_all
        if c.user_id == TEST_USER
    ]

    state = build_financial_state(
        user_id=TEST_USER,
        request_date=TEST_DATE,
        profile=profile,
        cash_events=user_cash_events,
        rates=rates,
    )

    print("\nFINANCIAL STATE")
    print("-" * 40)

    for key, value in state.items():
        if key != "future_events":
            print(f"{key}: {value}")

    print("\nFuture events:")

    for e in state["future_events"]:
        print(
            f"  {e.event_id:35} "
            f"{e.category:15} "
            f"{e.cash_date} "
            f"{e.cash_amount:>15} "
            f"{e.source_status}"
        )