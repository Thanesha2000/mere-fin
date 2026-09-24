# code/test_stage5.py

from decimal import Decimal
from datetime import date

from data_loader import load_data
from build_events import events_df_to_raw_events
from reconcile import build_cash_events
from financial_state import build_financial_state, load_exchange_rates
from safe_amount import find_max_safe_amount


TEST_USER = "user_212"
TEST_DATE = date(2025, 2, 5)

# We will ask:
# "What is the maximum amount this user can safely pay today,
#  considering everything that happens during the forecast?"
UPPER_BOUND = Decimal("100000000")


# ---------------------------------------------------------
# STAGE 1 — Load data
# ---------------------------------------------------------

data = load_data()

profiles = data["profiles"]
events_df = data["events"]


# ---------------------------------------------------------
# STAGE 2 — Build and reconcile cash events
# ---------------------------------------------------------

raw_events = events_df_to_raw_events(events_df)

cash_result = build_cash_events(raw_events)

resolved_events = cash_result["resolved"]


# ---------------------------------------------------------
# Select our test user's profile and events
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
# Extract inputs needed by Stage 5
# ---------------------------------------------------------

starting_balance = Decimal(
    str(state["current_available_balance"])
)

minimum_balance = Decimal(
    str(state["minimum_balance_to_keep"])
)

future_events = state["future_events"]


# ---------------------------------------------------------
# STAGE 5 — Find maximum safe amount
# ---------------------------------------------------------

maximum_safe_amount = find_max_safe_amount(
    starting_balance=starting_balance,
    minimum_balance_to_keep=minimum_balance,
    start_date=TEST_DATE,
    horizon_days=90,
    cash_events=future_events,
    upper_bound=UPPER_BOUND,
)


# ---------------------------------------------------------
# Display result
# ---------------------------------------------------------

print("\n" + "=" * 55)
print("STAGE 5 — MAXIMUM SAFE AMOUNT")
print("=" * 55)

print(f"User:                  {TEST_USER}")
print(f"Request date:          {TEST_DATE}")
print(f"Starting balance:      {starting_balance}")
print(f"Minimum balance:       {minimum_balance}")
print(f"Search upper bound:    {UPPER_BOUND}")
print(f"Maximum safe amount:   {maximum_safe_amount}")

print("=" * 55)