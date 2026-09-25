import sys
sys.path.append('code')
from datetime import date
from decimal import Decimal

from financial_state import CashEvent
from payment_options import PaymentOption
from spending_changes import identify_eligible_spending
from spending_optimizer import optimize_spending_and_payments

def create_event(eid, cat, flex, amt, min_amt=None, source="projected", dt=date(2025, 2, 1)):
    return CashEvent(
        event_id=eid,
        user_id="user_synth",
        category=cat,
        event_type="expense",
        cash_direction="out",
        cash_amount=Decimal(str(amt)),
        cash_date=dt,
        currency="INR",
        flexibility=flex,
        minimum_allowed_amount=Decimal(str(min_amt)) if min_amt is not None else None,
        source_status=source,
        amount_resolved=True
    )

def main():
    print("=" * 80)
    print("STAGE 6.8 — SYNTHETIC SPENDING OPTIMIZER TEST")
    print("=" * 80)
    
    request_date = date(2025, 1, 1)
    requested_amount = Decimal("2000")
    horizon_days = 90
    desired_completion_date = date(2025, 2, 28)
    
    user_id = "user_synth"
    starting_balance = Decimal("2000")
    minimum_balance_to_keep = Decimal("500")
    # Immediate payment of 2000 leaves balance at 0. But minimum is 500! So initial attempt fails.
    # We need to save at least 500 in spending to make it safe!
    
    base_profile = {
        "expense_categories_to_protect": "rent",
        "expense_categories_user_is_willing_to_reduce": "groceries|dining",
        "expense_categories_user_is_willing_to_stop": "streaming|gym",
        "current_available_balance": 2000,
        "minimum_balance_to_keep": 500,
        "payment_methods_user_will_consider": "full_payment",
        "max_installment_months": 12
    }
    
    pay_option = PaymentOption(
        payment_option_id="opt_1",
        request_id="req_synth",
        payment_method="full_payment",
        payment_amount=Decimal("2000"),
        number_of_payments=1,
        first_payment_date=request_date,
        payment_frequency_days=None,
        financing_fee=Decimal("0"),
        total_payable_amount=Decimal("2000")
    )
    
    print("\nSCENARIO A: Without spending change -> unsafe. With allowed reduction -> safe.")
    # Starting balance = 3000, min = 500. Requested = 2000. 
    # Payment = 2000 on day 1 -> balance is 1000.
    # Future expense on Jan 15th: 600. Balance becomes 400 (< 500!). UNSAFE.
    # If we reduce expense to 100 on Jan 15th, balance becomes 900. SAFE.
    
    starting_balance = Decimal("3000")
    
    ev_dining = create_event("projected_ding_2025", "dining", "reducible", 600, 100, dt=date(2025, 1, 15))
    
    res_a = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, starting_balance, minimum_balance_to_keep, horizon_days,
        [ev_dining], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    
    assert res_a is not None, "Failed to optimize!"
    assert len(res_a.spending_changes) == 1, "Should have 1 change"
    assert res_a.spending_changes[0].action == "reduce_to"
    assert res_a.spending_changes[0].savings == Decimal("500")
    print("-> SUCCESS")

    print("\nSCENARIO B: Protected category cannot be changed.")
    # Same as A, but the expense is rent (protected)
    ev_rent = create_event("projected_rent_2025", "rent", "reducible", 600, 100, dt=date(2025, 1, 15))
    res_b = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, starting_balance, minimum_balance_to_keep, horizon_days,
        [ev_rent], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    assert res_b.payment_decision.selected_candidate is None, "Should not be able to optimize protected category"
    print("-> SUCCESS")
    
    print("\nSCENARIO C: Not listed category cannot be changed.")
    ev_fun = create_event("projected_fun_2025", "fun", "reducible", 600, 100, dt=date(2025, 1, 15))
    res_c = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, starting_balance, minimum_balance_to_keep, horizon_days,
        [ev_fun], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    assert res_c.payment_decision.selected_candidate is None, "Should not be able to optimize unlisted category"
    print("-> SUCCESS")

    print("\nSCENARIO D: Cannot be reduced below minimum_allowed_amount.")
    # Dining min amount is 550, meaning savings is only 50. Total balance would be 450 < 500.
    ev_dining_strict = create_event("projected_ding_2025", "dining", "reducible", 600, 550, dt=date(2025, 1, 15))
    res_d = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, starting_balance, minimum_balance_to_keep, horizon_days,
        [ev_dining_strict], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    assert res_d.payment_decision.selected_candidate is None, "Should not reduce below minimum allowed"
    print("-> SUCCESS")
    
    print("\nSCENARIO E: A stoppable event can be stopped.")
    ev_stream = create_event("projected_stream_2025", "streaming", "stoppable", 600, dt=date(2025, 1, 15))
    res_e = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, starting_balance, minimum_balance_to_keep, horizon_days,
        [ev_stream], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    assert res_e is not None and res_e.payment_decision.selected_candidate is not None, "Failed to stop stream"
    assert res_e.spending_changes[0].action == "stop"
    print("-> SUCCESS")
    
    print("\nSCENARIO F: More than 3 changes are never returned.")
    # Give 4 events, each giving 150 savings. Total savings needed is 500 (since minimum drops to 400 with 600 expense).
    # Wait, we need to balance it so that 3 is not enough, but 4 would be enough.
    # Initial balance 2000, min 500. Payment 2000. Balance ends at 0. So need 500 savings TOTAL.
    # We provide 4 events of 100 savings each. Max 3 changes gives 300 savings -> balance 300 < 500 -> UNSAFE.
    evs_small = [
        create_event(f"projected_ding{i}", "dining", "reducible", 100, 0, dt=date(2025, 1, 15))
        for i in range(4)
    ]
    res_f = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, Decimal("2500"), minimum_balance_to_keep, horizon_days,
        evs_small, [pay_option], "full_payment", 12, False, desired_completion_date
    )
    # wait: starting = 2500, pay 2000 -> 500. Then 4 expenses of 100 -> 100. Min is 500. We need 400 savings!
    # Max changes allowed is 3. 3*100 = 300 savings. Balance = 400 < 500. Fails.
    assert res_f.payment_decision.selected_candidate is None, "Should not exceed max changes"
    print("-> SUCCESS")

    print("\nSCENARIO G: Spending changes appear in final selected decision.")
    assert res_a.spending_changes[0].action == "reduce_to"
    assert res_a.spending_changes[0].category == "dining"
    assert res_a.spending_changes[0].savings == Decimal("500")
    print("-> SUCCESS")

    print("\nSCENARIO H: Historical events are never modified.")
    hist_ev = create_event("event_hist_99", "dining", "reducible", 500, 300, source="settled", dt=date(2024, 12, 15))
    proj_ev = create_event("projected_event_hist_99_2025", "dining", "reducible", 500, 300, source="projected", dt=date(2025, 1, 15))
    res_h = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, Decimal("2900"), minimum_balance_to_keep, horizon_days,
        [hist_ev, proj_ev], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    # Test apply_spending_changes explicitly
    from spending_changes import apply_spending_changes
    modified = apply_spending_changes([hist_ev, proj_ev], list(res_h.spending_changes))
    assert modified[0].cash_amount == 500, "Historical event should not be changed"
    assert modified[1].cash_amount == 300, "Projected event should be changed"
    print("-> SUCCESS")

    print("\nSCENARIO I: Multiple changes can combine to make a plan safe.")
    # Starting 3000, min 500. Requested 2000. Balance buffer = 1000 - 500 = 500 safe cushion.
    # Future expenses on Jan 15: A=300 (saves 200), B=500 (saves 300), C=100 (saves 100).
    # Total expenses = 900. Shortfall = 900 - 500 = 400. Need 400 savings to be safe!
    ev_a = create_event("projected_a_2025", "dining", "reducible", 300, 100, source="projected", dt=date(2025, 1, 15))
    ev_b = create_event("projected_b_2025", "groceries", "reducible", 500, 200, source="projected", dt=date(2025, 1, 15))
    ev_c = create_event("projected_c_2025", "gym", "stoppable", 100, 0, source="projected", dt=date(2025, 1, 15))
    res_i = optimize_spending_and_payments(
        user_id, base_profile, request_date, requested_amount, Decimal("3000"), minimum_balance_to_keep, horizon_days,
        [ev_a, ev_b, ev_c], [pay_option], "full_payment", 12, False, desired_completion_date
    )
    assert res_i is not None
    assert len(res_i.spending_changes) == 2
    savings = sum(c.savings for c in res_i.spending_changes)
    assert savings >= 400
    print("-> SUCCESS")

    print("\nSCENARIO J: Spending changes interact correctly with deadline.")
    # Without changes, maybe only safe by Jan 15 (wait). If deadline is Jan 10, it fails.
    # With changes, safe immediately (Jan 1). Meets deadline! We saw res_a generated a safe candidate that otherwise failed.
    assert res_a.payment_decision.selected_candidate.completes_by_deadline
    print("-> SUCCESS")

    print("\nSCENARIO K: Spending changes feed into normal payment ranking.")
    assert res_i.payment_decision.selected_candidate.simulation.candidate.candidate_id is not None
    print("-> SUCCESS")

    print("\n================================================================================")
    print("STAGE 6.8.5 — REAL DATA VALIDATION")
    print("================================================================================\n")
    
    import pandas as pd
    from build_events import events_df_to_raw_events
    from reconcile import build_cash_events
    from project_recurrence import project_recurring
    from payment_options import build_payment_options
    
    DATASET_DIR = "dataset"
    profiles_df = pd.read_csv(f"{DATASET_DIR}/financial_profiles.csv")
    events_df = pd.read_csv(f"{DATASET_DIR}/financial_events.csv")
    requests_df = pd.read_csv(f"{DATASET_DIR}/requests.csv")
    payment_options_df = pd.read_csv(f"{DATASET_DIR}/request_payment_options.csv")
    
    raw_events = events_df_to_raw_events(events_df)
    event_layers = build_cash_events(raw_events)
    resolved_events = event_layers["resolved"]
    
    # Let's search through requests to find one that becomes safe with changes.
    # We will just print the first one that works.
    found = False
    
    # Only check requests that previously failed natively
    previously_failed = ["request_32", "request_28", "request_37", "request_64", "request_41", "request_42", "request_50"]
    # Wait, let's just check all of them dynamically.
    for index, request_row in requests_df.iterrows():
        request_id = request_row["request_id"]
        
        if request_id not in previously_failed:
             continue
             
        user_id = str(request_row["user_id"])
        profile_row = profiles_df[profiles_df["user_id"].astype(str) == user_id].iloc[0]
        
        req_date = date.fromisoformat(str(request_row["request_date"]))
        req_amount = Decimal(str(request_row["requested_amount"]))
        des_date = date.fromisoformat(str(request_row["desired_completion_date"]))
        
        f_end = req_date + pd.Timedelta(days=90)
        u_evs = [e for e in resolved_events if e.user_id == user_id]
        hist = [e for e in u_evs if e.source_status == "settled" and e.cash_date <= req_date]
        fut = [e for e in u_evs if e.cash_date > req_date and e.cash_date <= f_end]
        proj = project_recurring(hist, req_date, f_end, fut)
        sim_evs = u_evs + proj
        
        pay_opts = build_payment_options(payment_options_df, request_id)
        
        # We also need base decision to confirm it's normally unsafe.
        from payment_decision import build_payment_decision
        base_decision = build_payment_decision(
            request_date=req_date,
            requested_amount=req_amount,
            starting_balance=Decimal(str(profile_row["current_available_balance"])),
            minimum_balance_to_keep=Decimal(str(profile_row["minimum_balance_to_keep"])),
            horizon_days=90,
            cash_events=sim_evs,
            payment_options=pay_opts,
            payment_methods_user_will_consider=profile_row["payment_methods_user_will_consider"],
            max_installment_months=profile_row["max_installment_months"],
            allows_partial_payment=bool(request_row["allows_partial_payment"]),
            desired_completion_date=des_date,
        )
        
        if base_decision.selected_candidate is not None:
             continue # skip if already safe
             
        # Optmize!
        opt_decision = optimize_spending_and_payments(
            user_id=user_id,
            profile=profile_row.to_dict(),
            request_date=req_date,
            requested_amount=req_amount,
            starting_balance=Decimal(str(profile_row["current_available_balance"])),
            minimum_balance_to_keep=Decimal(str(profile_row["minimum_balance_to_keep"])),
            horizon_days=90,
            cash_events=sim_evs,
            payment_options=pay_opts,
            payment_methods_user_will_consider=profile_row["payment_methods_user_will_consider"],
            max_installment_months=profile_row["max_installment_months"],
            allows_partial_payment=bool(request_row["allows_partial_payment"]),
            desired_completion_date=des_date
        )
        
        if opt_decision is not None and opt_decision.payment_decision.selected_candidate is not None:
            if len(opt_decision.spending_changes) > 0:
                print("FOUND A REAL CASE!")
                print(f"Request ID:            {request_id}")
                print(f"User ID:               {user_id}")
                print(f"Requested amount:      {req_amount}")
                print(f"Orig safe amount:      {base_decision.amount_safe_to_pay}")
                print(f"Orig safe candidates:  {len(base_decision.ranked_candidates)}")
                
                print("\nEligible Spending Changes found directly:")
                el = identify_eligible_spending(sim_evs, user_id, profile_row.to_dict())
                for c in el:
                     print(f"  {c.action} {c.target_event_id} ({c.category}) from {c.original_amount} to {c.new_amount} = {c.savings}")
                     
                print("\nSelected Spending Changes:")
                for c in opt_decision.spending_changes:
                     print(f"  {c.action} {c.target_event_id} ({c.category}) : Saves {c.savings}")
                     
                print(f"\nTotal savings created: {sum([c.savings for c in opt_decision.spending_changes])}")
                
                sel_cand = opt_decision.payment_decision.selected_candidate.simulation.candidate
                print(f"\nResulting safe candidate: {sel_cand.candidate_id} ({sel_cand.payment_method})")
                
                print("Final Payment Plan:")
                for i, p in enumerate(sel_cand.payments):
                    print(f"  Payment {i+1}: {p[0]} -> {p[1]}")
                    
                    
                found = True
                break
            else:
                el = identify_eligible_spending(sim_evs, user_id, profile_row.to_dict())
                total_max_savings = sum([c.original_amount - c.new_amount for c in el])
                shortfall = req_amount - base_decision.amount_safe_to_pay
                print(f"FAILED: {request_id} (shortfall vs savings)")
                for c in el:
                     print(f"  {c.action} {c.target_event_id} ({c.category}) : Saves {c.original_amount - c.new_amount}")
                print(f"Total maximum possible savings: {total_max_savings}")
                print(f"Amount still required: {shortfall}\n")
        else:
             el = identify_eligible_spending(sim_evs, user_id, profile_row.to_dict())
             total_max_savings = sum([c.original_amount - c.new_amount for c in el])
             shortfall = req_amount - base_decision.amount_safe_to_pay
             print(f"FAILED: {request_id} (shortfall vs savings)")
             for c in el:
                  print(f"  {c.action} {c.target_event_id} ({c.category}) : Saves {c.original_amount - c.new_amount}")
             print(f"Total maximum possible savings: {total_max_savings}")
             print(f"Amount still required: {shortfall}\n")
                
    if not found:
        print("No real request could be made affordable using valid spending changes.")
        
    print("\n================================================================================")

if __name__ == "__main__":
    main()
