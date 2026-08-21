"""
PurPaws Dashboard Ranking Consumer Seam v1

Purpose
-------

Select canonical ranking records relevant to dashboard presentation.

This module does NOT calculate ranking truth.

Canonical ranking truth is owned by:

    build_platform_ranking_aggregation(db)

This seam only selects:

- creator ranking record for a user_id,
- rescue ranking record for a user_id,
- partner ranking records for already-visible organization_ids.

IMPORTANT:

Organization visibility is determined elsewhere.

This seam does NOT decide:
- organization access,
- membership,
- permissions,
- campaign authority,
- relationship authority,
- publication authority,
- taxonomy authority.

RANKING TRUTH != DASHBOARD PRESENTATION.
"""

from backend.app.platform_ranking_aggregation import (
    build_platform_ranking_aggregation,
)


def get_dashboard_ranking_context(
    db,
    user_id,
    organization_ids=None,
):
    organization_ids = {
        int(organization_id)
        for organization_id in (
            organization_ids
            or []
        )
        if organization_id is not None
    }

    aggregation = build_platform_ranking_aggregation(
        db
    )

    leaderboards = aggregation.get(
        "leaderboards",
        {},
    )

    creator_record = next(
        (
            record
            for record in leaderboards.get(
                "creators",
                [],
            )
            if record.get("user_id") == user_id
        ),
        None,
    )

    rescue_record = next(
        (
            record
            for record in leaderboards.get(
                "rescues",
                [],
            )
            if record.get("user_id") == user_id
        ),
        None,
    )

    partner_records = [
        record
        for record in leaderboards.get(
            "partners",
            [],
        )
        if record.get("organization_id")
        in organization_ids
    ]

    partner_records.sort(
        key=lambda record: (
            record.get("rank")
            if record.get("rank") is not None
            else 10**12,
            record.get("organization_id")
            if record.get("organization_id") is not None
            else 10**12,
        )
    )

    return {
        "creator":
            creator_record,

        "rescue":
            rescue_record,

        "partners":
            partner_records,
    }
