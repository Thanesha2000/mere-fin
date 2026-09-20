# code/run_pipeline_demo.py

"""
Stage 1 -> Stage 2 -> Stage 3 -> Stage 4

End-to-end smoke test for one known user.

Pipeline:

    data_loader
        ↓
    build_events
        ↓
    reconcile
        ↓
    financial_state
        ↓
    simulator
"""

from datetime import date
from decimal import Decimal

from data_loader import load_data
from build_events import events_df_to_raw_events
from reconcile import build_cash_events
from financial_state import (
    build_financial_state,
    load_exchange_rates,
)
from simulator import simulate


# ============================================================
# TEST CASE
# ============================================================

TEST_USER = "user_212"

TEST_DATE = date(2025, 2, 5)

REQUESTED_AMOUNT = Decimal("10000000")


# ============================================================
# STAGE 1 — DATA LOADING
# ============================================================

print("=" * 70)
print("STAGE 1 — DATA LOADING")
print("=" * 70)

data = load_data()

profiles = data["profiles"]
events_df = data["events"]

print("Profiles:", len(profiles))
print("Events:", len(events_df))


# ============================================================
# STAGE 2A — CONVERT DATAFRAME TO RAW EVENTS
# ============================================================

print()
print("=" * 70)
print("STAGE 2A — BUILD RAW EVENTS")
print("=" * 70)

raw_events = events_df_to_raw_events(events_df)

print("Raw events:", len(raw_events))


# ============================================================
# STAGE 2B — RECONCILE EVENT LIFECYCLES
# ============================================================

print()
print("=" * 70)
print("STAGE 2B — EVENT RECONCILIATION")
print("=" * 70)

cash_result = build_cash_events(raw_events)

resolved_events = cash_result["resolved"]

print("Resolved cash events:", len(resolved_events))

if "ambiguous" in cash_result:
    print(
        "Ambiguous chains:",
        len(cash_result["ambiguous"])
    )


# ============================================================
# FILTER EVENTS FOR TEST USER
# ============================================================

user_cash_events = [
    event
    for event in resolved_events
    if event.user_id == TEST_USER
]

print("User cash events:", len(user_cash_events))


# ============================================================
# STAGE 3 — FINANCIAL STATE + FORECAST
# ============================================================

print()
print("=" * 70)
print("STAGE 3 — FINANCIAL STATE + FORECAST")
print("=" * 70)

profile_rows = profiles[
    profiles["user_id"] == TEST_USER
]

if profile_rows.empty:
    raise ValueError(
        f"Profile not found for user: {TEST_USER}"
    )

profile = profile_rows.iloc[0]

rates = load_exchange_rates()

state = build_financial_state(
    user_id=TEST_USER,
    request_date=TEST_DATE,
    profile=profile,
    cash_events=user_cash_events,
    rates=rates,
)


# ============================================================
# EXTRACT FINANCIAL STATE
# ============================================================

starting_balance = Decimal(
    str(state["current_available_balance"])
)

minimum_balance = Decimal(
    str(state["minimum_balance_to_keep"])
)

future_events = state["future_events"]


print(
    "Starting available balance:",
    starting_balance
)

print(
    "Minimum balance to keep:",
    minimum_balance
)

print(
    "Future cash events:",
    len(future_events)
)


# ============================================================
# SHOW FUTURE EVENTS
# ============================================================

print()
print("-" * 70)
print("FUTURE EVENTS USED BY SIMULATOR")
print("-" * 70)

for event in sorted(
    future_events,
    key=lambda e: e.cash_date
):

    print(
        f"{event.cash_date} | "
        f"{event.category:20} | "
        f"{event.cash_direction:7} | "
        f"{event.cash_amount} | "
        f"{event.source_status}"
    )


# ============================================================
# STAGE 4A — FULL PAYMENT TODAY
# ============================================================

print()
print("=" * 70)
print("STAGE 4 — FULL PAYMENT TODAY")
print("=" * 70)

result_today = simulate(
    starting_balance=starting_balance,
    minimum_balance_to_keep=minimum_balance,
    start_date=TEST_DATE,
    horizon_days=90,
    cash_events=future_events,
    candidate_payments=[
        (
            TEST_DATE,
            REQUESTED_AMOUNT
        )
    ],
)

print(
    "Requested amount:",
    REQUESTED_AMOUNT
)

print(
    "Safe:",
    result_today.safe
)

print(
    "Minimum balance reached:",
    result_today.minimum_balance_reached
)

print(
    "Minimum balance date:",
    result_today.minimum_balance_date
)

print(
    "Ending balance:",
    result_today.ending_balance
)

if result_today.failure_date is not None:

    print(
        "Failure date:",
        result_today.failure_date
    )


# ============================================================
# STAGE 4B — BASELINE / NO PAYMENT
# ============================================================

print()
print("=" * 70)
print("STAGE 4 — BASELINE / NO PAYMENT")
print("=" * 70)

result_baseline = simulate(
    starting_balance=starting_balance,
    minimum_balance_to_keep=minimum_balance,
    start_date=TEST_DATE,
    horizon_days=90,
    cash_events=future_events,
    candidate_payments=[],
)

print(
    "Safe:",
    result_baseline.safe
)

print(
    "Minimum balance reached:",
    result_baseline.minimum_balance_reached
)

print(
    "Minimum balance date:",
    result_baseline.minimum_balance_date
)

print(
    "Ending balance:",
    result_baseline.ending_balance
)

if result_baseline.failure_date is not None:

    print(
        "Failure date:",
        result_baseline.failure_date
    )


# ============================================================
# FINAL PIPELINE STATUS
# ============================================================

print()
print("=" * 70)
print("PIPELINE COMPLETE")
print("=" * 70)

print("Stage 1 — Data loading       ✓")
print("Stage 2 — Raw event building ✓")
print("Stage 2 — Reconciliation     ✓")
print("Stage 3 — Financial state    ✓")
print("Stage 4 — Simulation         ✓")

print()
print("Next step: Stage 5 — maximum safe amount.")