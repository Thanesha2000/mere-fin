from pathlib import Path
from decimal import Decimal
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"


def load_exchange_rates():
    rates = pd.read_csv(DATASET / "exchange_rates.csv")
    rates["rate_date"] = pd.to_datetime(rates["rate_date"])

    rates["rate"] = rates["rate"].apply(
        lambda x: Decimal(str(x))
    )

    return rates


def find_direct_rate(
    rates: pd.DataFrame,
    from_currency: str,
    to_currency: str,
    date
):
    """
    Find the latest available direct exchange rate
    on or before the given date.
    """

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

    row = matches.sort_values("rate_date").iloc[-1]

    return row["rate"]


def convert_amount(
    amount,
    from_currency: str,
    to_currency: str,
    date,
    rates: pd.DataFrame
):
    """
    Convert using a direct rate supplied by the dataset.

    No reverse or invented rates are created.
    """

    if pd.isna(amount):
        return None

    rate = find_direct_rate(
        rates,
        from_currency,
        to_currency,
        date
    )

    if rate is None:
        return None

    return Decimal(str(amount)) * rate


def build_financial_state(
    user_id,
    request_date,
    profile,
    reconciled_events,
    rates
):
    """
    Build the user's financial state as of request_date.
    """

    request_date = pd.Timestamp(request_date)

    home_currency = profile["home_currency"]

    user_events = reconciled_events[
        reconciled_events["user_id"] == user_id
    ].copy()

    # Events whose cash impact is already known
    relevant = user_events[
        user_events["cash_relevant"]
        & user_events["cash_amount"].notna()
    ].copy()

    # Convert all known cash flows into home currency
    converted_amounts = []

    for _, event in relevant.iterrows():

        converted = convert_amount(
            event["cash_amount"],
            event["currency"],
            home_currency,
            event["cash_date"],
            rates
        )

        converted_amounts.append(converted)

    relevant["home_amount"] = converted_amounts

    # Historical settled cash flows
    historical = relevant[
        relevant["cash_date"] <= request_date
    ]

    historical = historical[
        historical["home_amount"].notna()
    ]

    historical_income = historical[
        historical["cash_direction"] == "credit"
    ]["home_amount"].sum()

    historical_expenses = historical[
        historical["cash_direction"] == "debit"
    ]["home_amount"].sum()

    # Future cash flows
    future = relevant[
        relevant["cash_date"] > request_date
    ]

    future = future[
        future["home_amount"].notna()
    ]

    future_income = future[
        future["cash_direction"] == "credit"
    ]["home_amount"].sum()

    future_expenses = future[
        future["cash_direction"] == "debit"
    ]["home_amount"].sum()

    return {
        "user_id": user_id,
        "request_date": request_date.date(),
        "home_currency": home_currency,

        "current_available_balance": Decimal(
            str(profile["current_available_balance"])
        ),

        "minimum_balance_to_keep": Decimal(
            str(profile["minimum_balance_to_keep"])
        ),

        "historical_income": historical_income,
        "historical_expenses": historical_expenses,

        "future_income": future_income,
        "future_expenses": future_expenses,

        "future_events": future,
    }


if __name__ == "__main__":

    profiles = pd.read_csv(
        DATASET / "financial_profiles.csv"
    )

    events = pd.read_csv(
        DATASET / "financial_events.csv"
    )

    rates = load_exchange_rates()

    # Reuse Stage 2
    from event_reconciler import reconcile_events

    reconciled = reconcile_events(events)

    profile = profiles.iloc[0]

    state = build_financial_state(
        user_id=profile["user_id"],
        request_date="2026-01-01",
        profile=profile,
        reconciled_events=reconciled,
        rates=rates,
    )

    print("\nFINANCIAL STATE")
    print("-" * 40)

    for key, value in state.items():

        if key != "future_events":
            print(f"{key}: {value}")

    print(
        "\nFuture events:",
        len(state["future_events"])
    )