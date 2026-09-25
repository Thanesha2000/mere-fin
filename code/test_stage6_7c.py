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
    print("STAGE 6.7c — REAL-DATA RANKING VALIDATION")
    print("=" * 80)
    
    profiles_df = pd.read_csv(f"{DATASET_DIR}/financial_profiles.csv")
    events_df = pd.read_csv(f"{DATASET_DIR}/financial_events.csv")
    requests_df = pd.read_csv(f"{DATASET_DIR}/requests.csv")
    payment_options_df = pd.read_csv(f"{DATASET_DIR}/request_payment_options.csv")
    
    raw_events = events_df_to_raw_events(events_df)
    event_layers = build_cash_events(raw_events)
    resolved_events = event_layers["resolved"]

    request_id = "request_273"
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
    
    print(f"Request ID:               {request_id}")
    print(f"User ID:                  {user_id}")
    print(f"Requested amount:         {requested_amount}")
    print(f"Desired completion:       {desired_completion_date}")
    print(f"Amount safe today:        {result.amount_safe_to_pay}")
    print(f"Earliest safe full date:  {result.earliest_date_for_full_payment}")
    print()
    
    print("Generated Candidates:")
    for c in result.candidates:
        print(f"  {c.candidate_id} | method: {c.payment_method} | total: {c.total_amount} | num_payments: {len(c.payments)}")
        for i, p in enumerate(c.payments):
            print(f"      Payment {i+1}: {p[0]} -> {p[1]}")
            
    print("\nSimulations:")
    for sim in result.simulations:
        print(f"  {sim.candidate.candidate_id} -> Safe: {sim.simulation.safe}")
        
    print("\nProduction Ranking:")
    for i, rc in enumerate(result.ranked_candidates, 1):
        print(f"  {i}. {rc.simulation.candidate.candidate_id}")
        
    # Independently compute expected ranking
    # Priority:
    # 1. Complete by deadline
    # 2. Require no spending changes (none do here)
    # 3. Lowest total payable amount
    # 4. Earliest first payment
    # 5. Fewest payments
    # 6. Lowest payment option ID
    
    safe_sims = [sim for sim in result.simulations if sim.simulation.safe]
    
    def ranking_key(sim):
        candidate = sim.candidate
        
        last_payment_date = max(p_date for p_date, _ in candidate.payments)
        not_completes = not (last_payment_date <= desired_completion_date)
        
        first_payment_date = min(p_date for p_date, _ in candidate.payments)
        
        opt_id = candidate.source_payment_option_id or candidate.candidate_id
        
        return (
            not_completes,
            False, # no spending changes yet
            candidate.total_amount,
            first_payment_date,
            len(candidate.payments),
            opt_id
        )
        
    expected_order = sorted(safe_sims, key=ranking_key)
    
    print("\nExpected Ranking:")
    for i, sim in enumerate(expected_order, 1):
        print(f"  {i}. {sim.candidate.candidate_id}")
        
    assert len(safe_sims) >= 2, "Must have at least 2 safe candidates to test ranking"
    
    production_ids = [rc.simulation.candidate.candidate_id for rc in result.ranked_candidates]
    expected_ids = [sim.candidate.candidate_id for sim in expected_order]
    
    assert production_ids == expected_ids, f"Ranking mismatch! Prod: {production_ids}, Exp: {expected_ids}"
    
    selected_id = result.selected_candidate.simulation.candidate.candidate_id if result.selected_candidate else None
    print(f"\nSelected Candidate:      {selected_id}")
    assert selected_id == expected_order[0].candidate.candidate_id, "Selected candidate is not the highest ranked one"
    
    print("\n-> SUCCESS: Ranking independently validated on real data.")
    print("=" * 80)

if __name__ == "__main__":
    main()
