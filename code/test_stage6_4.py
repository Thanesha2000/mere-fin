
# code/test_stage6_4.py

from datetime import date, timedelta

from data_loader import load_data
from build_events import events_df_to_raw_events
from reconcile import build_cash_events
from project_recurrence import project_recurring

from payment_options import build_payment_options
from payment_eligibility import filter_eligible_payment_options
from payment_candidates import generate_payment_candidates
from payment_simulation import simulate_payment_candidates


FORECAST_HORIZON_DAYS = 90


data = load_data()

requests = data["requests"]
profiles = data["profiles"]
raw_events_df = data["events"]


# ---------------------------------------------------------
# Convert the raw financial-events DataFrame into the
# RawEvent objects expected by Stage 2.
# ---------------------------------------------------------

raw_events = events_df_to_raw_events(raw_events_df)

cash_event_data = build_cash_events(raw_events)

resolved_cash_events = cash_event_data["resolved"]


# ---------------------------------------------------------
# Find a request with multiple eligible payment options.
# ---------------------------------------------------------

selected_request = None
selected_profile = None
selected_options = None

for _, request in requests.iterrows():

    user_id = request["user_id"]

    profile_rows = profiles[
        profiles["user_id"] == user_id
    ]

    if profile_rows.empty:
        continue

    profile = profile_rows.iloc[0]

    options = build_payment_options(
        data["payment_options"],
        request["request_id"],
    )

    eligible_options = filter_eligible_payment_options(
        payment_options=options,
        payment_methods_user_will_consider=profile[
            "payment_methods_user_will_consider"
        ],
        max_installment_months=profile[
            "max_installment_months"
        ],
    )

    if len(eligible_options) >= 2:
        selected_request = request
        selected_profile = profile
        selected_options = eligible_options
        break


if selected_request is None:
    raise RuntimeError(
        "Could not find a request with at least "
        "two eligible payment options."
    )


request_id = selected_request["request_id"]
user_id = selected_request["user_id"]

request_date = selected_request["request_date"]

if not isinstance(request_date, date):
    request_date = date.fromisoformat(str(request_date))


# ---------------------------------------------------------
# Select this user's reconciled financial events.
# ---------------------------------------------------------

user_cash_events = [
    event
    for event in resolved_cash_events
    if event.user_id == user_id
]


forecast_end = (
    request_date
    + timedelta(days=FORECAST_HORIZON_DAYS)
)


# Events already known to occur after the request date.
real_future_events = [
    event
    for event in user_cash_events
    if (
        event.cash_date > request_date
        and event.cash_date <= forecast_end
    )
]


# Historical settled events used to detect recurrence.
historical_events = [
    event
    for event in user_cash_events
    if (
        event.source_status == "settled"
        and event.cash_date <= request_date
    )
]


# ---------------------------------------------------------
# Project recurring financial events.
# ---------------------------------------------------------

projected_events = project_recurring(
    settled_events=historical_events,
    request_date=request_date,
    forecast_end=forecast_end,
    real_future_events=real_future_events,
)


future_cash_events = (
    real_future_events
    + projected_events
)


# ---------------------------------------------------------
# Generate payment candidates.
# ---------------------------------------------------------

candidates = generate_payment_candidates(
    request_date=request_date,
    requested_amount=selected_request[
        "requested_amount"
    ],
    eligible_payment_options=selected_options,
    payment_methods_user_will_consider=selected_profile[
        "payment_methods_user_will_consider"
    ],
)


# ---------------------------------------------------------
# Jointly simulate each complete candidate against the
# user's real future financial timeline.
# ---------------------------------------------------------

simulation_results = simulate_payment_candidates(
    candidates=candidates,
    starting_balance=selected_profile[
        "current_available_balance"
    ],
    minimum_balance_to_keep=selected_profile[
        "minimum_balance_to_keep"
    ],
    request_date=request_date,
    horizon_days=FORECAST_HORIZON_DAYS,
    cash_events=future_cash_events,
)


# ---------------------------------------------------------
# Output.
# ---------------------------------------------------------

print("=" * 70)
print("STAGE 6.4 — REAL CASH-FLOW PAYMENT PLAN SIMULATION")
print("=" * 70)

print(f"Request ID:          {request_id}")
print(f"User ID:             {user_id}")
print(f"Request date:        {request_date}")
print(
    f"Requested amount:    "
    f"{selected_request['requested_amount']}"
)
print(
    f"Starting balance:    "
    f"{selected_profile['current_available_balance']}"
)
print(
    f"Minimum balance:     "
    f"{selected_profile['minimum_balance_to_keep']}"
)
print(
    f"Eligible options:    "
    f"{len(selected_options)}"
)
print(
    f"Candidates:          "
    f"{len(candidates)}"
)
print(
    f"Resolved cash events: "
    f"{len(resolved_cash_events)}"
)
print(
    f"User cash events:    "
    f"{len(user_cash_events)}"
)
print(
    f"Real future events:  "
    f"{len(real_future_events)}"
)
print(
    f"Projected events:    "
    f"{len(projected_events)}"
)
print(
    f"Simulation events:   "
    f"{len(future_cash_events)}"
)
print()

print("SIMULATION RESULTS")
print("-" * 70)

for result in simulation_results:

    candidate = result.candidate
    simulation = result.simulation

    print(f"Candidate: {candidate.candidate_id}")
    print(f"Method:    {candidate.payment_method}")
    print(f"Total:     {candidate.total_amount}")
    print(f"Safe:      {simulation.safe}")
    print(
        f"Minimum balance reached: "
        f"{simulation.minimum_balance_reached}"
    )
    print(
        f"Minimum balance date:    "
        f"{simulation.minimum_balance_date}"
    )
    print(
        f"Failure date:            "
        f"{simulation.failure_date}"
    )
    print(
        f"Ending balance:          "
        f"{simulation.ending_balance}"
    )
    print()

print("=" * 70)