CREATE TABLE canonical_organization_resolution_reviews (
            id INTEGER NOT NULL PRIMARY KEY,
            source_type VARCHAR NOT NULL,
            source_id INTEGER NOT NULL,
            target_type VARCHAR NOT NULL,
            target_id INTEGER NOT NULL,
            decision VARCHAR NOT NULL,
            basis TEXT NOT NULL,
            evidence_summary TEXT,
            reviewer_user_id INTEGER NOT NULL,
            reviewed_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME
        );

CREATE INDEX ix_canonical_org_resolution_review_reviewer
        ON canonical_organization_resolution_reviews (
            reviewer_user_id
        );

CREATE INDEX ix_canonical_org_resolution_review_source
        ON canonical_organization_resolution_reviews (
            source_type,
            source_id
        );

CREATE INDEX ix_canonical_org_resolution_review_source_target
        ON canonical_organization_resolution_reviews (
            source_type,
            source_id,
            target_type,
            target_id
        );

CREATE INDEX ix_canonical_org_resolution_review_target
        ON canonical_organization_resolution_reviews (
            target_type,
            target_id
        );
