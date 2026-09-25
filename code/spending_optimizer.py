import itertools
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal

from financial_state import CashEvent
from payment_options import PaymentOption
from payment_decision import build_payment_decision, PaymentDecisionResult
from spending_changes import identify_eligible_spending, apply_spending_changes, SpendingChange

@dataclass
class OptimizedDecision:
    spending_changes: tuple[SpendingChange, ...]
    payment_decision: PaymentDecisionResult

def _is_valid_combination(combination: tuple[SpendingChange, ...]) -> bool:
    """
    Ensure no two changes target the same event.
    """
    targets = [change.target_event_id for change in combination]
    return len(targets) == len(set(targets))

def _ranking_key(opt: OptimizedDecision):
    """
    Sort optimized decisions. Lower values preferred.
    """
    selected = opt.payment_decision.selected_candidate
    if not selected:
        # Should not happen since we only keep those with a safe candidate,
        # but just in case, rank them worst.
        return (float('inf'),)
        
    simulation = selected.simulation
    candidate = simulation.candidate
    
    first_payment_date = min(p[0] for p in candidate.payments)
    
    total_savings = sum(c.savings for c in opt.spending_changes)
    
    # Tie-breaker deterministic string
    sorted_change_ids = tuple(sorted([c.target_event_id for c in opt.spending_changes]))
    
    source_option_id = candidate.source_payment_option_id or candidate.candidate_id
    
    return (
        len(opt.spending_changes),
        not selected.completes_by_deadline,
        candidate.total_amount,
        first_payment_date,
        len(candidate.payments),
        total_savings,
        source_option_id,
        sorted_change_ids
    )

def optimize_spending_and_payments(
    user_id: str,
    profile: dict,
    request_date,
    requested_amount: Decimal,
    starting_balance: Decimal,
    minimum_balance_to_keep: Decimal,
    horizon_days: int,
    cash_events: List[CashEvent],
    payment_options: List[PaymentOption],
    payment_methods_user_will_consider: str,
    max_installment_months: float,
    allows_partial_payment: bool,
    desired_completion_date
) -> Optional[OptimizedDecision]:
    """
    Finds the best combination of payment plan and spending changes (if needed)
    to make the requested payment safe.
    """
    
    # 1. Base test (no spending changes)
    base_decision = build_payment_decision(
        request_date=request_date,
        requested_amount=requested_amount,
        starting_balance=starting_balance,
        minimum_balance_to_keep=minimum_balance_to_keep,
        horizon_days=horizon_days,
        cash_events=cash_events,
        payment_options=payment_options,
        payment_methods_user_will_consider=payment_methods_user_will_consider,
        max_installment_months=max_installment_months,
        allows_partial_payment=allows_partial_payment,
        desired_completion_date=desired_completion_date
    )
    
    if base_decision.selected_candidate is not None:
        return OptimizedDecision(
            spending_changes=tuple(),
            payment_decision=base_decision
        )
        
    # 2. Extract eligible changes
    eligible_changes = identify_eligible_spending(
        simulation_events=cash_events,
        user_id=user_id,
        profile=profile
    )
    
    if not eligible_changes:
        return OptimizedDecision(
            spending_changes=tuple(),
            payment_decision=base_decision
        )
        
    valid_decisions = []
    
    # Generate combinations up to size 3
    max_changes = min(3, len(eligible_changes))
    
    for r in range(1, max_changes + 1):
        for combo in itertools.combinations(eligible_changes, r):
            if not _is_valid_combination(combo):
                continue
                
            modified_events = apply_spending_changes(cash_events, list(combo))
            
            decision = build_payment_decision(
                request_date=request_date,
                requested_amount=requested_amount,
                starting_balance=starting_balance,
                minimum_balance_to_keep=minimum_balance_to_keep,
                horizon_days=horizon_days,
                cash_events=modified_events,
                payment_options=payment_options,
                payment_methods_user_will_consider=payment_methods_user_will_consider,
                max_installment_months=max_installment_months,
                allows_partial_payment=allows_partial_payment,
                desired_completion_date=desired_completion_date
            )
            
            if decision.selected_candidate is not None:
                valid_decisions.append(OptimizedDecision(
                    spending_changes=combo,
                    payment_decision=decision
                ))
                
    if not valid_decisions:
        return OptimizedDecision(
            spending_changes=tuple(),
            payment_decision=base_decision
        )
        
    valid_decisions.sort(key=_ranking_key)
    
    return valid_decisions[0]
