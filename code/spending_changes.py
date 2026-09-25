from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Optional, Set
import re
import pandas as pd

from financial_state import CashEvent

@dataclass
class SpendingChange:
    action: str  # "stop" or "reduce_to"
    target_event_id: str
    category: str
    original_amount: Decimal
    new_amount: Decimal
    savings: Decimal

def _parse_categories(profile_string: str) -> Set[str]:
    if not profile_string or pd.isna(profile_string):
        return set()
    return {c.strip() for c in str(profile_string).split('|') if c.strip()}

def get_base_event_id(event: CashEvent) -> str:
    """
    Extract the base event ID from a projected event, or return the event ID directly.
    projected event IDs look like: projected_event_123_2025-01-01
    """
    if event.source_status == "projected" and event.event_id.startswith("projected_"):
        # Match 'projected_event_123_2025-01-01' -> 'event_123'
        match = re.match(r"^projected_(.+)_\d{4}-\d{2}-\d{2}$", event.event_id)
        if match:
            return match.group(1)
    return event.event_id

def identify_eligible_spending(
    simulation_events: List[CashEvent],
    user_id: str,
    profile: dict
) -> List[SpendingChange]:
    """
    Identify valid hypothetical spending changes for a user based on their profile.
    """
    import pandas as pd
    
    willing_to_reduce = _parse_categories(profile.get("expense_categories_user_is_willing_to_reduce", ""))
    willing_to_stop = _parse_categories(profile.get("expense_categories_user_is_willing_to_stop", ""))
    protected = _parse_categories(profile.get("expense_categories_to_protect", ""))
    
    eligible_changes = []
    
    # Track base event IDs we've already processed to avoid duplicating
    # actions for every single month's projected instance of the same subscription.
    processed_base_ids = set()
    
    for event in simulation_events:
        if event.user_id != user_id:
            continue
            
        # Only debits (spending)
        if event.cash_direction != "out":
            continue
            
        # Do not modify protected categories
        if event.category in protected:
            continue
            
        # We only look at future events (projected or pending)
        if event.source_status not in ["projected", "pending"]:
            continue
            
        base_id = get_base_event_id(event)
        
        if base_id in processed_base_ids:
            continue
            
        processed_base_ids.add(base_id)
        
        original_amount = event.cash_amount
        if original_amount is None or original_amount <= 0:
            continue
            
        # Check if user is willing to stop
        if event.category in willing_to_stop:
            # Event flexibility must allow it
            if event.flexibility in ["stoppable", "reducible_or_stoppable"]:
                eligible_changes.append(
                    SpendingChange(
                        action="stop",
                        target_event_id=base_id,
                        category=event.category,
                        original_amount=original_amount,
                        new_amount=Decimal("0"),
                        savings=original_amount
                    )
                )
                
        # Check if user is willing to reduce
        if event.category in willing_to_reduce:
            if event.flexibility in ["reducible", "reducible_or_stoppable"]:
                min_amount = event.minimum_allowed_amount
                
                # If there's a minimum allowed amount and it's less than original, we can reduce
                if min_amount is not None and min_amount < original_amount:
                    eligible_changes.append(
                        SpendingChange(
                            action="reduce_to",
                            target_event_id=base_id,
                            category=event.category,
                            original_amount=original_amount,
                            new_amount=min_amount,
                            savings=original_amount - min_amount
                        )
                    )
                # If there's no strict minimum, we'll arbitrarily reduce by half
                # or find some deterministic value. But the challenge strictly states:
                # "new amount must be >= event.minimum_allowed_amount when that field exists"
                # If there's NO minimum amount provided, what is deterministic?
                # For this challenge, we assume minimum_allowed_amount MUST exist for reducible,
                # as otherwise we don't know how much to reduce. But if it lacks it, we don't reduce blindly.
                # Actually, some cases might have minimum_allowed_amount. We'll stick to using that.

    return eligible_changes

def apply_spending_changes(
    simulation_events: List[CashEvent],
    changes: List[SpendingChange]
) -> List[CashEvent]:
    """
    Apply a set of hypothetical spending changes to the simulation events.
    Returns a new list of CashEvents, without mutating the original.
    """
    
    # Build dictionary of actions for fast lookup
    # e.g., actions["event_123"] = SpendingChange(action="stop", ...)
    actions = {change.target_event_id: change for change in changes}
    
    modified_events = []
    
    for event in simulation_events:
        base_id = get_base_event_id(event)
        
        change = actions.get(base_id)
        
        if not change:
            modified_events.append(event)
            continue
            
        # We process the change.
        # But changes should only affect FUTURE events (projected or pending).
        # We don't revise history!
        if event.source_status not in ["projected", "pending"]:
            modified_events.append(event)
            continue
            
        if change.action == "stop":
            # Stopping means the event is entirely eliminated from cash flow
            continue
            
        if change.action == "reduce_to":
            # Create a shallow modified copy for the new amount
            import dataclasses
            mod_event = dataclasses.replace(event, cash_amount=change.new_amount)
            modified_events.append(mod_event)
            
    return modified_events
