import sys
sys.path.append('code')
from datetime import date
from decimal import Decimal
import pandas as pd
from build_events import events_df_to_raw_events
from reconcile import build_cash_events
from project_recurrence import project_recurring
from payment_options import build_payment_options
from payment_decision import build_payment_decision

DATASET_DIR = "dataset"

def main():
    print("=" * 80)
    print("STAGE 6.7d — NO-CANDIDATE SANITY VALIDATION")
    print("=" * 80)
    
    profiles_df = pd.read_csv(f"{DATASET_DIR}/financial_profiles.csv")
    events_df = pd.read_csv(f"{DATASET_DIR}/financial_events.csv")
    requests_df = pd.read_csv(f"{DATASET_DIR}/requests.csv")
    payment_options_df = pd.read_csv(f"{DATASET_DIR}/request_payment_options.csv")
    
    raw_events = events_df_to_raw_events(events_df)
    event_layers = build_cash_events(raw_events)
    resolved_events = event_layers["resolved"]

    request_ids = [
        "request_32",
        "request_28",
        "request_37",
        "request_64",
        "request_41"
    ]
    
    for request_id in request_ids:
        request_row = requests_df[requests_df["request_id"] == request_id].iloc[0]
        user_id = str(request_row["user_id"])
        profile_row = profiles_df[profiles_df["user_id"].astype(str) == user_id].iloc[0]
        
        request_date = date.fromisoformat(str(request_row["request_date"]))
        requested_amount = Decimal(str(request_row["requested_amount"]))
        desired_completion_date = date.fromisoformat(str(request_row["desired_completion_date"]))
        
        forecast_end = request_date + pd.Timedelta(days=90)
        user_events = [e for e in resolved_events if e.user_id == user_id]
        
        historical = [e for e in user_events if e.source_status == "settled" and e.cash_date <= request_date]
        future = [e for e in user_events if e.cash_date > request_date and e.cash_date <= forecast_end]
        
        projected = project_recurring(
            settled_events=historical,
            request_date=request_date,
            forecast_end=forecast_end,
            real_future_events=future
        )
        simulation_events = user_events + projected

        payment_options = build_payment_options(payment_options_df, request_id)
        
        result = build_payment_decision(
            request_date=request_date,
            requested_amount=requested_amount,
            starting_balance=Decimal(str(profile_row["current_available_balance"])),
            minimum_balance_to_keep=Decimal(str(profile_row["minimum_balance_to_keep"])),
            horizon_days=90,
            cash_events=simulation_events,
            payment_options=payment_options,
            payment_methods_user_will_consider=profile_row["payment_methods_user_will_consider"],
            max_installment_months=profile_row["max_installment_months"],
            allows_partial_payment=bool(request_row["allows_partial_payment"]),
            desired_completion_date=desired_completion_date,
        )
        
        print(f"\nRequest ID:               {request_id}")
        print(f"User ID:                  {user_id}")
        print(f"Requested amount:         {requested_amount}")
        print(f"Amount safe today:        {result.amount_safe_to_pay}")
        print(f"Earliest safe full date:  {result.earliest_date_for_full_payment}")
        print(f"Desired deadline:         {desired_completion_date}")
        print(f"User preferences:         {profile_row['payment_methods_user_will_consider']}")
        print(f"Eligible payment options: {len(result.eligible_options)}")
        print(f"Generated candidates:     {len(result.candidates)}")
        print(f"Safe after simulation:    {len(result.ranked_candidates)}")
        
        if result.selected_candidate:
            print(f"Selected candidate:       {result.selected_candidate.simulation.candidate.candidate_id}")
        else:
            print("Selected candidate:       None")
            
        assert len(result.ranked_candidates) == 0, f"Expected 0 safe candidates for {request_id}, got {len(result.ranked_candidates)}"
        assert result.selected_candidate is None, f"Expected None selected candidate for {request_id}"
        
        # Simple reason heuristics
        if result.amount_safe_to_pay == 0 and result.earliest_date_for_full_payment is None and len(result.candidates) == 0:
            print("Reason: safe amount = 0, no earliest safe date, meaning full amount never safe in horizon. 0 generated candidates.")
        elif result.amount_safe_to_pay < requested_amount and len(result.candidates) == 0:
            if not request_row["allows_partial_payment"]:
                print("Reason: amount safe to pay is < requested amount, but allows_partial_payment=False prevents partial payment plan.")
            else:
                print("Reason: amount safe to pay < requested amount, user preference blocks alternatives.")
        elif len(result.candidates) > 0 and len(result.ranked_candidates) == 0:
            print("Reason: candidate(s) was generated, but failed safety simulation over 90-day horizon.")
        else:
            print("Reason: Other combination of user preferences, safety amount, or eligible options blocked candidates.")
            
    print("\n-> SUCCESS: 5 No-candidate cases verified correctly.")
    print("=" * 80)

if __name__ == "__main__":
    main()
