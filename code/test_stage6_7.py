from datetime import date
from decimal import Decimal

import pandas as pd

from build_events import events_df_to_raw_events
from payment_decision import build_payment_decision
from payment_options import build_payment_options
from project_recurrence import project_recurring
from reconcile import build_cash_events


DATASET_DIR = "dataset"
FORECAST_HORIZON_DAYS = 90


def main():
    profiles_df = pd.read_csv(
        f"{DATASET_DIR}/financial_profiles.csv"
    )

    events_df = pd.read_csv(
        f"{DATASET_DIR}/financial_events.csv"
    )

    requests_df = pd.read_csv(
        f"{DATASET_DIR}/requests.csv"
    )

    payment_options_df = pd.read_csv(
        f"{DATASET_DIR}/request_payment_options.csv"
    )

    print("=" * 80)
    print("STAGE 6.7 — REAL REQUEST CASE DISCOVERY")
    print("=" * 80)
    print()

    # ---------------------------------------------------------------
    # Build cash events once.
    # ---------------------------------------------------------------

    print("Building resolved cash events...")

    raw_events = events_df_to_raw_events(events_df)
    event_layers = build_cash_events(raw_events)

    resolved_events = event_layers["resolved"]

    print(
        f"Resolved cash events: {len(resolved_events)}"
    )
    print()

    # ---------------------------------------------------------------
    # Group events by user.
    # ---------------------------------------------------------------

    events_by_user = {}

    for event in resolved_events:
        events_by_user.setdefault(
            event.user_id,
            [],
        ).append(event)

    # ---------------------------------------------------------------
    # Track discovered cases.
    # ---------------------------------------------------------------

    case_rows = []

    from datetime import timedelta

    for index, request_row in requests_df.iterrows():

        request_id = str(request_row["request_id"])
        user_id = str(request_row["user_id"])

        request_date = date.fromisoformat(
            str(request_row["request_date"])
        )

        requested_amount = Decimal(
            str(request_row["requested_amount"])
        )

        desired_completion_date = date.fromisoformat(
            str(request_row["desired_completion_date"])
        )

        # Use fixed 90-day financial forecast, NOT
        # desired_completion_date as the horizon.
        forecast_end = (
            request_date
            + timedelta(days=FORECAST_HORIZON_DAYS)
        )

        profile_matches = profiles_df[
            profiles_df["user_id"] == user_id
        ]

        if profile_matches.empty:
            continue

        profile_row = profile_matches.iloc[0]

        user_events = events_by_user.get(
            user_id,
            [],
        )

        historical_events = [
            event
            for event in user_events
            if (
                event.source_status == "settled"
                and event.cash_date <= request_date
            )
        ]

        real_future_events = [
            event
            for event in user_events
            if (
                event.cash_date > request_date
                and event.cash_date <= forecast_end
            )
        ]

        projected_events = project_recurring(
            settled_events=historical_events,
            request_date=request_date,
            forecast_end=forecast_end,
            real_future_events=real_future_events,
        )

        simulation_events = (
            user_events
            + projected_events
        )

        # -----------------------------------------------------------
        # Load payment options for this request.
        # -----------------------------------------------------------

        payment_options = build_payment_options(
            payment_options_df=payment_options_df,
            request_id=request_id,
        )

        # -----------------------------------------------------------
        # Complete Stage 6 payment decision.
        # -----------------------------------------------------------

        result = build_payment_decision(
            request_date=request_date,
            requested_amount=requested_amount,
            starting_balance=Decimal(
                str(
                    profile_row[
                        "current_available_balance"
                    ]
                )
            ),
            minimum_balance_to_keep=Decimal(
                str(
                    profile_row[
                        "minimum_balance_to_keep"
                    ]
                )
            ),
            horizon_days=FORECAST_HORIZON_DAYS,
            cash_events=simulation_events,
            payment_options=payment_options,
            payment_methods_user_will_consider=(
                profile_row[
                    "payment_methods_user_will_consider"
                ]
            ),
            max_installment_months=(
                profile_row["max_installment_months"]
            ),
            allows_partial_payment=bool(
                request_row["allows_partial_payment"]
            ),
            desired_completion_date=(
                desired_completion_date
            ),
        )

        # -----------------------------------------------------------
        # Use ranked (safe) candidates only.
        # -----------------------------------------------------------

        safe_candidates = [
            rc.simulation.candidate
            for rc in result.ranked_candidates
        ]

        candidate_methods = sorted(
            {
                candidate.payment_method
                for candidate in safe_candidates
            }
        )

        eligible_methods = sorted(
            {
                option.payment_method
                for option in result.eligible_options
            }
        )

        case_rows.append(
            {
                "request_id": request_id,
                "user_id": user_id,
                "requested_amount": requested_amount,
                "safe_today": result.amount_safe_to_pay,
                "earliest_safe_date": (
                    result.earliest_date_for_full_payment
                ),
                "allows_partial": bool(
                    request_row["allows_partial_payment"]
                ),
                "eligible_methods": "|".join(
                    eligible_methods
                ),
                "candidate_methods": "|".join(
                    candidate_methods
                ),
                "candidate_count": len(safe_candidates),
                "total_generated": len(result.candidates),
                "unsafe_count": sum(
                    1
                    for sim in result.simulations
                    if not sim.simulation.safe
                ),
            }
        )

    # ---------------------------------------------------------------
    # Print summary.
    # ---------------------------------------------------------------

    results_df = pd.DataFrame(case_rows)

    print("REQUEST COVERAGE")
    print("-" * 80)

    print(
        f"Requests processed: "
        f"{len(results_df)}"
    )

    print(
        f"Requests with safe candidates: "
        f"{(results_df['candidate_count'] > 0).sum()}"
    )

    print(
        f"Requests without safe candidates: "
        f"{(results_df['candidate_count'] == 0).sum()}"
    )

    total_generated = results_df["total_generated"].sum()
    total_unsafe = results_df["unsafe_count"].sum()

    print(
        f"Total candidates generated:    {total_generated}"
    )

    print(
        f"Candidates failed simulation:  {total_unsafe}"
    )

    print()

    # ---------------------------------------------------------------
    # Candidate-method coverage.
    # ---------------------------------------------------------------

    method_counts = {
        "full_payment": 0,
        "partial_payment": 0,
        "installments": 0,
        "wait": 0,
    }

    for methods in results_df["candidate_methods"]:
        if not methods:
            continue

        for method in methods.split("|"):
            method_counts[method] += 1

    print("SAFE CANDIDATE METHOD COVERAGE")
    print("-" * 80)

    for method, count in method_counts.items():
        print(
            f"{method:20} {count}"
        )

    print()

    # ---------------------------------------------------------------
    # Show useful real cases.
    # ---------------------------------------------------------------

    for method in [
        "full_payment",
        "partial_payment",
        "installments",
        "wait",
    ]:
        matches = results_df[
            results_df["candidate_methods"].str.contains(
                method,
                regex=False,
                na=False,
            )
        ]

        print(
            f"{method.upper()} CASES"
        )
        print("-" * 80)

        if matches.empty:
            print("None found.")
        else:
            print(
                matches[
                    [
                        "request_id",
                        "user_id",
                        "requested_amount",
                        "safe_today",
                        "earliest_safe_date",
                        "eligible_methods",
                        "candidate_methods",
                    ]
                ].head(10).to_string(index=False)
            )

        print()

    # ---------------------------------------------------------------
    # Show no-candidate cases.
    # ---------------------------------------------------------------

    no_candidate = results_df[
        results_df["candidate_count"] == 0
    ]

    print("NO-CANDIDATE CASES")
    print("-" * 80)

    if no_candidate.empty:
        print("None found.")
    else:
        print(
            no_candidate[
                [
                    "request_id",
                    "user_id",
                    "requested_amount",
                    "safe_today",
                    "earliest_safe_date",
                    "eligible_methods",
                ]
            ].head(10).to_string(index=False)
        )

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()