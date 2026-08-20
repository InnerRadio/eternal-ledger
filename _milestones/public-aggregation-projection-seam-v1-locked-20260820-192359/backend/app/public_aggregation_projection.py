"""
PurPaws Public Aggregation Projection Seam v1

Purpose
-------

Convert internal platform aggregation truth into deliberately
public-safe leaderboard records.

This module is a projection boundary.

Aggregation Truth != Public Projection.

The functions in this module:

- consume already-computed aggregate dictionaries,
- create new dictionaries,
- expose only explicitly allow-listed fields,
- never mutate the source aggregate,
- never query or write the database,
- never determine organization access,
- never create membership,
- never grant permission,
- never establish relationships,
- never make publication decisions,
- never make taxonomy decisions.

Analytical input is not automatically a public field.
"""


PARTICIPANT_PUBLIC_FIELDS = frozenset(
    {
        "rank",
        "score",
    }
)


ORGANIZATION_PUBLIC_FIELDS = frozenset(
    {
        "organization_id",
        "organization_name",
        "organization_type",
        "project",
        "rank",
        "score",
    }
)


FORBIDDEN_PUBLIC_FIELDS = frozenset(
    {
        "user_id",
        "email",
        "role",
        "affiliate_id",
        "referral_code",
        "commission_points",
        "components",
    }
)


def _project_allowlisted_fields(record, allowed_fields):
    """
    Return a new dictionary containing only explicitly allowed fields.

    Missing fields are not invented.
    Source dictionaries are never mutated.
    """

    if not isinstance(record, dict):
        raise TypeError("aggregate record must be a dictionary")

    return {
        key: record[key]
        for key in allowed_fields
        if key in record
    }


def project_public_participant_ranking(record):
    """
    Project one participant ranking record.

    v1 deliberately exposes only rank and score because the current
    aggregation-truth participant record does not yet contain a
    canonical public display-identity contract.

    Internal account identity must not be promoted as public identity.
    """

    projected = _project_allowlisted_fields(
        record,
        PARTICIPANT_PUBLIC_FIELDS,
    )

    leaked = FORBIDDEN_PUBLIC_FIELDS.intersection(projected)

    if leaked:
        raise RuntimeError(
            "participant public projection leaked forbidden fields: "
            + ", ".join(sorted(leaked))
        )

    return projected


def project_public_organization_ranking(record):
    """
    Project one organization ranking record.

    Organization identity fields already present in aggregation truth
    may be projected only through this explicit allow-list.
    """

    projected = _project_allowlisted_fields(
        record,
        ORGANIZATION_PUBLIC_FIELDS,
    )

    leaked = FORBIDDEN_PUBLIC_FIELDS.intersection(projected)

    if leaked:
        raise RuntimeError(
            "organization public projection leaked forbidden fields: "
            + ", ".join(sorted(leaked))
        )

    return projected


def project_public_rankings(records, projector, limit=None):
    """
    Project a sequence of aggregate records through an explicit
    record projector.

    The source sequence and source dictionaries remain unchanged.
    """

    if records is None:
        return []

    projected = [
        projector(record)
        for record in records
    ]

    if limit is None:
        return projected

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValueError("limit must be a non-negative integer or None")

    return projected[:limit]
