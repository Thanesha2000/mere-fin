"""
Stage 6.7a: Real partial-payment end-to-end test for request_273
"""
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
from build_events import events_df_to_raw_events
from payment_decision import build_payment_decision
from payment_options import build_payment_options
from project_recurrence import project_recurring
from reconcile import build_cash_events
import json 

DATASET_DIR = "dataset"

def main():
    print("=" * 70)
    print("STAGE 6.7a: PARTIAL PAYMENT E2E (request_273)")
    print("=" * 70)

    # 1. Load Data
    profiles_df = pd.read_csv(f"{DATASET_DIR}/financial_profiles.csv")
    events_df = pd.read_csv(f"{DATASET_DIR}/financial_events.csv")
    requests_df = pd.read_csv(f"{DATASET_DIR}/requests.csv")
    payment_options_df = pd.read_csv(f"{DATASET_DIR}/request_payment_options.csv")

    raw_events = events_df_to_raw_events(events_df)
    event_layers = build_cash_events(raw_events)
    resolved_events = event_layers["resolved"]

    # 2. Extract Request & Profile
    TARGET = "request_273"
    request_matches = requests_df[requests_df["request_id"] == TARGET]
    if request_matches.empty:
        print(f"Request {TARGET} not found!")
        return
    r = request_matches.iloc[0]

    p = profiles_df[profiles_df["user_id"].astype(str) == str(r["user_id"])].iloc[0]

    request_date = date.fromisoformat(str(r["request_date"]))
    forecast_end = request_date + timedelta(days=90)
    user_events = [e for e in resolved_events if e.user_id == str(r["user_id"])]
    historical = [e for e in user_events if e.source_status == "settled" and e.cash_date <= request_date]
    future = [e for e in user_events if e.cash_date > request_date and e.cash_date <= forecast_end]
    
    projected = project_recurring(
        settled_events=historical,
        request_date=request_date,
        forecast_end=forecast_end,
        real_future_events=future,
    )
    sim_events = user_events + projected

    payment_options = build_payment_options(
        payment_options_df=payment_options_df,
        request_id=TARGET,
    )

    # 3. Run Payment Decision Pipeline
    result = build_payment_decision(
        request_date=request_date,
        requested_amount=Decimal(str(r["requested_amount"])),
        starting_balance=Decimal(str(p["current_available_balance"])),
        minimum_balance_to_keep=Decimal(str(p["minimum_balance_to_keep"])),
        horizon_days=90,
        cash_events=sim_events,
        payment_options=payment_options,
        payment_methods_user_will_consider=p["payment_methods_user_will_consider"],
        max_installment_months=p["max_installment_months"],
        allows_partial_payment=bool(r["allows_partial_payment"]),
        desired_completion_date=date.fromisoformat(str(r["desired_completion_date"])),
    )

    # 4. Output Results
    print(f"Inputs:")
    print(f"  Request Date:            {request_date}")
    print(f"  Requested Amount:        {r['requested_amount']}")
    print(f"  Allows Partial Payment:  {r['allows_partial_payment']}")
    print(f"  User accepts methods:    {p['payment_methods_user_will_consider']}")
    print(f"  Starting Balance:        {p['current_available_balance']}")
    print(f"  Minimum Balance:         {p['minimum_balance_to_keep']}")
    print(f"  Desired Completion Date: {r['desired_completion_date']}")
    print()

    print(f"Stage 5 (Amounts & Dates):")
    print(f"  Amount Safe To Pay:      {result.amount_safe_to_pay}")
    print(f"  Earliest Full Pay Date:  {result.earliest_date_for_full_payment}")
    print()

    print(f"All Raw Candidates (Generated):")
    for idx, c in enumerate(result.candidates, 1):
        print(f"  {idx}. {c.candidate_id} ({c.payment_method})")
        for pd_date, amt in c.payments:
            print(f"       -> {pd_date}: {amt}")
    print()

    print(f"Simulations (Stage 6.4):")
    for s in result.simulations:
        print(f"  {s.candidate.candidate_id}: safe={s.simulation.safe} (min_bal={s.simulation.minimum_balance_reached})")
    print()

    print(f"Ranked Candidates (Stage 6.5 Safe-Only): {len(result.ranked_candidates)}")
    for rc in result.ranked_candidates:
        c = rc.simulation.candidate
        print(f"  [x] {c.candidate_id} | method={c.payment_method} | total={c.total_amount}")
    
    print("\nSelected Recommendation:")
    if result.selected_candidate:
        c = result.selected_candidate.simulation.candidate
        print(f"  => {c.candidate_id} ({c.payment_method})")
    else:
        print("  => None")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
