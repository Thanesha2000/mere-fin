# code/test_stage5b.py

from decimal import Decimal
from datetime import date

from data_loader import load_data
from build_events import events_df_to_raw_events
from reconcile import build_cash_events
from financial_state import (
    build_financial_state,
    load_exchange_rates,
)
from earliest_safe_date import find_earliest_safe_date


TEST_USER = "user_212"
TEST_DATE = date(2025, 2, 5)

# We deliberately choose an amount larger than the
# Stage 5 maximum safe amount of ₹14,107,500.
#
# This should force Stage 5b to search future dates.
REQUESTED_AMOUNT = Decimal("20000000")

HORIZON_DAYS = 90


# ---------------------------------------------------------
# STAGE 1 — Load data
# ---------------------------------------------------------

data = load_data()

profiles = data["profiles"]
events_df = data["events"]


# ---------------------------------------------------------
# STAGE 2 — Build and reconcile cash events
# ---------------------------------------------------------

raw_events = events_df_to_raw_events(
    events_df
)

cash_result = build_cash_events(
    raw_events
)

resolved_events = cash_result["resolved"]


# ---------------------------------------------------------
# Select test user's profile and events
# ---------------------------------------------------------

profile = profiles[
    profiles["user_id"] == TEST_USER
].iloc[0]

user_cash_events = [
    event
    for event in resolved_events
    if event.user_id == TEST_USER
]


# ---------------------------------------------------------
# STAGE 3 — Build financial state
# ---------------------------------------------------------

rates = load_exchange_rates()

state = build_financial_state(
    user_id=TEST_USER,
    request_date=TEST_DATE,
    profile=profile,
    cash_events=user_cash_events,
    rates=rates,
)


# ---------------------------------------------------------
# Extract Stage 3 financial inputs
# ---------------------------------------------------------

starting_balance = Decimal(
    str(
        state["current_available_balance"]
    )
)

minimum_balance = Decimal(
    str(
        state["minimum_balance_to_keep"]
    )
)

future_events = state["future_events"]


# ---------------------------------------------------------
# STAGE 5b — Find earliest safe date
# ---------------------------------------------------------

earliest_date = find_earliest_safe_date(
    requested_amount=REQUESTED_AMOUNT,
    starting_balance=starting_balance,
    minimum_balance_to_keep=minimum_balance,
    request_date=TEST_DATE,
    horizon_days=HORIZON_DAYS,
    cash_events=future_events,
)


# ---------------------------------------------------------
# Display result
# ---------------------------------------------------------

print("\n" + "=" * 55)
print("STAGE 5b — EARLIEST SAFE DATE")
print("=" * 55)

print(
    f"User:                  {TEST_USER}"
)

print(
    f"Request date:          {TEST_DATE}"
)

print(
    f"Requested amount:      {REQUESTED_AMOUNT}"
)

print(
    f"Starting balance:      {starting_balance}"
)

print(
    f"Minimum balance:       {minimum_balance}"
)

print(
    f"Forecast horizon:      {HORIZON_DAYS} days"
)

print(
    f"Earliest safe date:    {earliest_date}"
)

print("=" * 55)