# code/state/reconcile.py
"""
Stage 2 — Reconciliation.

Two layers, two separate jobs, never mixed:
  1. Lifecycle layer  — decides which record(s) in a linked_event_id chain
                         survive. ONLY collapses on documented, defensible
                         status pairs. Anything else stays as-is and gets
                         flagged for review. No guessing.
  2. Cash-flow layer   — applies the problem statement's UNCONDITIONAL,
                         per-record rules (ignore cancelled/failed/pending-
                         credit/unrealized/non-cash) regardless of what the
                         lifecycle layer did. This is explicit spec, not a
                         guess, so it applies no matter the chain shape.

No invented fields. Real CSV schema has no record_date, no is_amendment,
no is_cancellation — none of that is used here.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import date


# ---------- schema-accurate models ----------

@dataclass
class RawEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str              # debit | credit | non_cash
    amount: Decimal | None      # None = blank, must NOT become 0
    currency: str
    event_date: date
    settlement_date: date | None
    status: str                 # settled | pending | scheduled | cancelled | failed | unrealized
    linked_event_id: str | None
    flexibility: str | None     # flexible | essential | None
    minimum_allowed_amount: Decimal | None


@dataclass
class CashEvent:
    event_id: str
    user_id: str
    category: str
    cash_direction: str          # debit | credit
    cash_amount: Decimal | None  # None if amount still unresolved
    cash_date: date
    flexibility: str | None
    minimum_allowed_amount: Decimal | None
    source_status: str
    amount_resolved: bool


TERMINAL_STATUS = {"cancelled", "failed"}
DROP_ALWAYS = {"unrealized"}   # never a cash movement, regardless of chain shape

# Only pairs defensible from documented lifecycle meaning.
# (loser_status, winner_status): loser dropped, winner kept.
KNOWN_COLLAPSES = {
    ("pending", "settled"),
    ("scheduled", "settled"),
    ("failed", "scheduled"),
    ("failed", "settled"),
}


# ---------- lifecycle layer ----------

def build_chains(events: list[RawEvent]) -> dict[str, list[RawEvent]]:
    """Group events into lifecycle chains via linked_event_id → root."""
    by_id = {e.event_id: e for e in events}

    def find_root(eid: str) -> str:
        seen = set()
        cur = eid
        while True:
            e = by_id.get(cur)
            if not e or not e.linked_event_id or cur in seen:
                return cur
            seen.add(cur)
            cur = e.linked_event_id

    chains: dict[str, list[RawEvent]] = {}
    for e in events:
        root = find_root(e.event_id)
        chains.setdefault(root, []).append(e)
    return chains


def resolve_chain(chain: list[RawEvent]) -> list[RawEvent]:
    """
    Returns survivors for one chain.
    Usually 1. Can be 0 (lone terminal record — dead) or >1 (genuinely
    ambiguous, caller flags it). Collapses ONLY on KNOWN_COLLAPSES pairs.
    Does NOT special-case cancellation across a multi-record chain —
    no evidence that "cancelled anywhere" kills siblings. That per-record
    exclusion is enforced later, unconditionally, in classify_cash_flow.
    """
    if len(chain) == 1:
        e = chain[0]
        return [] if e.status in TERMINAL_STATUS else [e]

    survivors = list(chain)
    changed = True
    while changed:
        changed = False
        for a in survivors:
            for b in survivors:
                if a is b:
                    continue
                if (a.status, b.status) in KNOWN_COLLAPSES:
                    survivors.remove(a)
                    changed = True
                    break
            if changed:
                break

    return survivors  # no post-filtering — ambiguous leftovers stay, unchanged


def reconcile_lifecycle(
    events: list[RawEvent],
) -> tuple[list[RawEvent], list[list[RawEvent]]]:
    """Returns (clean_survivors_flat, ambiguous_chains_for_review)."""
    chains = build_chains(events)
    clean: list[RawEvent] = []
    flagged: list[list[RawEvent]] = []

    for chain in chains.values():
        survivors = resolve_chain(chain)
        if len(survivors) <= 1:
            clean.extend(survivors)
        else:
            flagged.append(survivors)
            clean.extend(survivors)  # kept in the flow — safer than silently dropping data

    return clean, flagged


# ---------- cash-flow layer ----------

def classify_cash_flow(e: RawEvent) -> CashEvent | None:
    """
    Turns a surviving RawEvent into a forecast-ready CashEvent, or None
    if it never touches the balance. These checks are the problem
    statement's explicit, unconditional rules — applied per record,
    regardless of what the lifecycle layer decided about its chain.
    """
    if e.status in TERMINAL_STATUS:
        return None                          # spec: ignore failed/cancelled, always
    if e.direction == "non_cash" or e.status in DROP_ALWAYS:
        return None                          # investments etc — never cash
    if e.status == "pending" and e.direction == "credit":
        return None                          # can't spend money not yet received

    cash_date = e.settlement_date or e.event_date
    resolved = e.amount is not None

    return CashEvent(
        event_id=e.event_id,
        user_id=e.user_id,
        category=e.category,
        cash_direction=e.direction,
        cash_amount=abs(e.amount) if resolved else None,
        cash_date=cash_date,
        flexibility=e.flexibility,
        minimum_allowed_amount=e.minimum_allowed_amount,
        source_status=e.status,
        amount_resolved=resolved,
    )


# ---------- stage 2 entry point ----------

def build_cash_events(raw_events: list[RawEvent]) -> dict[str, list]:
    """
    Full Stage 2 pipeline for one user's events.
    Returns:
      resolved         -> CashEvents ready for the simulator
      unresolved        -> CashEvents missing amount, needs image-extraction fill-in
      ambiguous_chains  -> raw chains lifecycle layer couldn't confidently collapse
                           (kept in the data anyway — cash-flow layer still
                           applies its unconditional rules to each record)
    """
    clean, ambiguous_chains = reconcile_lifecycle(raw_events)

    cash_events = [c for c in (classify_cash_flow(e) for e in clean) if c is not None]
    resolved = [c for c in cash_events if c.amount_resolved]
    unresolved = [c for c in cash_events if not c.amount_resolved]

    return {
        "resolved": resolved,
        "unresolved": unresolved,
        "ambiguous_chains": ambiguous_chains,
    }