from datetime import date
from decimal import Decimal

from payment_options import PaymentOption
from financial_state import CashEvent
from payment_decision import build_payment_decision

def main():
    print("=" * 80)
    print("STAGE 6.7b — HORIZON VS DEADLINE VALIDATION")
    print("=" * 80)
    print()

    request_date = date(2025, 1, 1)
    requested_amount = Decimal("2000")
    
    # 90-day horizon goes out to ~April 1, 2025.
    HORIZON_DAYS = 90
    
    starting_balance = Decimal("10000")
    minimum_balance_to_keep = Decimal("2000")

    # =========================================================================
    # SCENARIO A: Safe within 90 days, but misses desired completion deadline
    # =========================================================================
    print("SCENARIO A: Misses strict deadline")
    print("-" * 80)
    
    # Deadline is tight: end of January
    deadline_a = date(2025, 1, 31)

    # Offer an installment plan that finishes on Feb 15 (after deadline, but within 90 days).
    option_a = PaymentOption(
        payment_option_id="opt_A",
        request_id="req_synthetic",
        payment_method="installments",
        payment_amount=Decimal("1000"),
        number_of_payments=2,
        first_payment_date=date(2025, 1, 15),
        payment_frequency_days=31,  # Second payment on Feb 15
        financing_fee=Decimal("0"),
        total_payable_amount=Decimal("2000")
    )

    # No future expenses, so financially it's perfectly safe over 90 days.
    result_a = build_payment_decision(
        request_date=request_date,
        requested_amount=requested_amount,
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        horizon_days=HORIZON_DAYS,
        cash_events=[],  # No stress
        payment_options=[option_a],
        payment_methods_user_will_consider="installments",
        max_installment_months=12,
        allows_partial_payment=False,
        desired_completion_date=deadline_a,
    )

    # Since it finishes after deadline_a, it shouldn't even be a candidate!
    candidates_a_methods = [c.candidate_id for c in result_a.candidates]
    print(f"Deadline: {deadline_a}")
    print(f"Installments finish: 2025-02-15")
    print(f"Candidates generated: {candidates_a_methods}")
    if not candidates_a_methods:
        print("-> SUCCESS: Installment plan rejected during generation due to deadline.")
    else:
        print("-> FAILURE: Installment plan wrongly accepted.")
    print()


    # =========================================================================
    # SCENARIO B: Meets deadline, but fails 90-day financial horizon safety
    # =========================================================================
    print("SCENARIO B: Meets deadline, fails 90-day safety horizon")
    print("-" * 80)
    
    # Generous deadline
    deadline_b = date(2025, 2, 28)

    # Offer an installment plan that completes quickly
    option_b = PaymentOption(
        payment_option_id="opt_B",
        request_id="req_synthetic",
        payment_method="installments",
        payment_amount=Decimal("2000"),
        number_of_payments=1,
        first_payment_date=request_date,
        payment_frequency_days=30,
        financing_fee=Decimal("0"),
        total_payable_amount=Decimal("2000")
    )

    # Add a massive future expense well AFTER the deadline_b, but WITHIN 90 days.
    # Date: March 15, 2025.
    expense_date = date(2025, 3, 15)
    cash_events_b = [
        CashEvent(
            event_id="future_expense",
            user_id="user_synth",
            category="tax_payment",
            event_type="expense",
            cash_direction="out",
            cash_amount=Decimal("7000"),
            cash_date=expense_date,
            currency="INR",
            flexibility="inflexible",
            minimum_allowed_amount=Decimal("7000"),
            source_status="projected",
            amount_resolved=True
        )
    ]

    # Without the payment, balance drops to 10000 - 7000 = 3000 (safe, >= 2000)
    # WITH the 2000 payment, balance drops to 10000 - 2000 - 7000 = 1000 (UNSAFE, < 2000)
    
    result_b = build_payment_decision(
        request_date=request_date,
        requested_amount=requested_amount,
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        horizon_days=HORIZON_DAYS,
        cash_events=cash_events_b,
        payment_options=[option_b],
        payment_methods_user_will_consider="installments",
        max_installment_months=12,
        allows_partial_payment=False,
        desired_completion_date=deadline_b,
    )

    candidates_b = [c.candidate_id for c in result_b.candidates]
    ranked_b = [rc.simulation.candidate.candidate_id for rc in result_b.ranked_candidates]
    print(f"Deadline: {deadline_b}")
    print(f"Payment finishes: {request_date}")
    print(f"Future expense on: {expense_date} (Drops balance to 1000, under 2000 min)")
    print(f"Candidates generated: {candidates_b}")
    print(f"Ranked (Safe) candidates: {ranked_b}")
    
    if candidates_b and not ranked_b:
        print("-> SUCCESS: Payment plan meets deadline, generated, but rejected by 90-day simulation safety.")
    else:
        print("-> FAILURE: Payment plan safety improperly evaluated.")
        
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
