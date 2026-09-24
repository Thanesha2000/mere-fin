# code/project_recurrence.py

from datetime import date
import calendar

from reconcile import CashEvent


MONTHLY_GAP_MIN = 27
MONTHLY_GAP_MAX = 32
DAY_OF_MONTH_TOLERANCE = 2
MIN_OCCURRENCES = 3

RECURRENCE_ELIGIBLE_TYPES = {
    "income",
    "expense",
    "debt_payment",
    "subscription",
}


def _modal_day(dates):
    days = [d.day for d in dates]
    return max(set(days), key=days.count)


def _passes_cadence(dates):
    if len(dates) < MIN_OCCURRENCES:
        return False

    stable_dates = dates[:-1]

    if len(stable_dates) < 2:
        return False

    stable_gaps = [
        (stable_dates[i + 1] - stable_dates[i]).days
        for i in range(len(stable_dates) - 1)
    ]

    if not all(
        MONTHLY_GAP_MIN <= g <= MONTHLY_GAP_MAX
        for g in stable_gaps
    ):
        return False

    modal = _modal_day(stable_dates)

    if not all(
        abs(d.day - modal) <= DAY_OF_MONTH_TOLERANCE
        for d in stable_dates
    ):
        return False

    last_gap = (
        dates[-1] - stable_dates[-1]
    ).days

    if last_gap <= 0 or last_gap > MONTHLY_GAP_MAX * 2:
        return False

    return True


def _passes_stability(events):
    amounts = [
        e.cash_amount
        for e in events
        if e.cash_amount is not None
    ]

    if len(amounts) < 2:
        return True

    distinct = []

    for a in amounts:
        if a not in distinct:
            distinct.append(a)

    if len(distinct) == 1:
        return True

    if len(distinct) > 2:
        return False

    first_val = amounts[0]
    switched = False
    other_val = None

    for a in amounts:
        if not switched:
            if a == first_val:
                continue

            switched = True
            other_val = a

        elif a != other_val:
            return False

    return True


def _target_month_key(user_id, category, direction, d):
    return (
        user_id,
        category,
        direction,
        d.year,
        d.month,
    )


def _safe_day_for_month(year, month, day):
    last_day = calendar.monthrange(year, month)[1]

    return date(
        year,
        month,
        min(day, last_day),
    )


def project_recurring(
    settled_events,
    request_date,
    forecast_end,
    real_future_events,
    verbose=False,
):
    history = [
        e
        for e in settled_events
        if e.source_status == "settled"
        and e.cash_date <= request_date
    ]

    groups = {}

    for e in history:
        key = (
            e.user_id,
            e.category,
            e.cash_direction,
        )

        groups.setdefault(key, []).append(e)

    real_future_months = {
        _target_month_key(
            e.user_id,
            e.category,
            e.cash_direction,
            e.cash_date,
        )
        for e in real_future_events
    }

    projected = []

    for (
        user_id,
        category,
        direction,
    ), events in groups.items():

        events = sorted(
            events,
            key=lambda e: e.cash_date,
        )

        dates = [
            e.cash_date
            for e in events
        ]

        type_ok = (
            events[0].event_type
            in RECURRENCE_ELIGIBLE_TYPES
        )

        cadence_ok = (
            _passes_cadence(dates)
            if type_ok
            else None
        )

        stability_ok = (
            _passes_stability(events)
            if (type_ok and cadence_ok)
            else None
        )

        # Optional diagnostic trace.
        # Normally verbose=False, so this produces no output.
        if verbose:
            print(
                f"[trace] "
                f"{category:15} "
                f"{direction:7} "
                f"n={len(events)} "
                f"event_type={events[0].event_type!r} "
                f"type_ok={type_ok} "
                f"cadence_ok={cadence_ok} "
                f"stability_ok={stability_ok} "
                f"dates={[d.isoformat() for d in dates]}"
            )

        if (
            not type_ok
            or not cadence_ok
            or not stability_ok
        ):
            continue

        last = events[-1]

        modal_day = _modal_day(
            dates[:-1]
        )

        cursor_year = last.cash_date.year
        cursor_month = last.cash_date.month

        cursor_month += 1

        if cursor_month > 12:
            cursor_month = 1
            cursor_year += 1

        next_date = _safe_day_for_month(
            cursor_year,
            cursor_month,
            modal_day,
        )

        while next_date <= forecast_end:

            month_key = _target_month_key(
                user_id,
                category,
                direction,
                next_date,
            )

            suppressed = (
                month_key in real_future_months
            )

            if not suppressed:
                projected.append(
                    CashEvent(
                        event_id=(
                            f"projected_"
                            f"{last.event_id}_"
                            f"{next_date.isoformat()}"
                        ),
                        user_id=user_id,
                        category=category,
                        event_type=last.event_type,
                        cash_direction=direction,
                        cash_amount=last.cash_amount,
                        cash_date=next_date,
                        currency=last.currency,
                        flexibility=last.flexibility,
                        minimum_allowed_amount=(
                            last.minimum_allowed_amount
                        ),
                        source_status="projected",
                        amount_resolved=True,
                    )
                )

            next_month = next_date.month + 1

            next_year = (
                next_date.year
                + (1 if next_month > 12 else 0)
            )

            next_month = (
                next_month
                if next_month <= 12
                else 1
            )

            next_date = _safe_day_for_month(
                next_year,
                next_month,
                modal_day,
            )

    return projected