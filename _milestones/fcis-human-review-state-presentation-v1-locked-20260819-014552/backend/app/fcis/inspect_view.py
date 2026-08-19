"""
FCIS Inspect View v1

Read-only private HTML renderer for one FCIS Inspect Detail.

BOUNDARY

This module does not:
- create canonical facts
- create canonical context
- create canonical relationships
- persist workflow state
- authorize external action
- expose a public endpoint
"""

from html import escape


INSPECT_VIEW_SCHEMA_VERSION = "fcis_inspect_view_v1"


def _esc(value):
    if value is None:
        return ""

    return escape(
        str(value),
        quote=True,
    )


def _display(value):
    if value is None:
        return "—"

    return str(value)


def _evidence_label(source_type):
    if source_type == "synthetic_test_fixture":
        return "Synthetic Test Fixture"

    return (
        str(source_type or "unknown")
        .replace("_", " ")
        .strip()
        .title()
    )


def _render_context_panel(label, detail):
    if not detail.get("resolved"):
        return f"""
        <section class="context-panel unresolved">

            <div class="eyebrow">
                {_esc(label)}
            </div>

            <h2>
                Context #{_esc(detail.get("context_id"))}
            </h2>

            <div class="warning">
                {_esc(detail.get("warning") or "Context could not be resolved.")}
            </div>

        </section>
        """

    context = detail["context"]
    subject = context.get("subject") or {}
    evidence = context.get("evidence") or {}

    source_type = evidence.get("source_type")

    synthetic_notice = ""

    if source_type == "synthetic_test_fixture":
        synthetic_notice = """
        <div class="synthetic-notice">
            SYNTHETIC TEST EVIDENCE — NOT A REAL-WORLD ASSERTION
        </div>
        """

    source_record = (
        "Not independently resolvable in Evidence Resolution v1"
        if source_type == "synthetic_test_fixture"
        else "No independent source resolver is asserted by INSPECT v1"
    )

    return f"""
    <section class="context-panel">

        <div class="eyebrow">
            {_esc(label)}
        </div>

        <div class="context-heading">

            <div>

                <h2>
                    {_esc(subject.get("name") or "Unresolved subject")}
                </h2>

                <div class="meta">
                    canonical context #{_esc(context.get("id"))}
                    · {_esc(context.get("context_type"))}
                    · {_esc(context.get("context_status"))}
                    · scope {_esc(context.get("scope") or "unspecified")}
                </div>

            </div>

            <div class="status-pill">
                {_esc((context.get("context_status") or "unknown").upper())}
            </div>

        </div>

        <div class="assertion">

            <div class="section-label">
                CANONICAL ASSERTION
            </div>

            <p>
                {_esc(context.get("context_value") or "No context value recorded.")}
            </p>

        </div>

        <div class="evidence">

            <div class="section-label">
                EVIDENCE
            </div>

            {synthetic_notice}

            <dl>

                <dt>Evidence Type</dt>
                <dd>{_esc(_evidence_label(source_type))}</dd>

                <dt>Evidence Source ID</dt>
                <dd>{_esc(_display(evidence.get("source_id")))}</dd>

                <dt>Evidence Reference</dt>
                <dd>{_esc(_display(evidence.get("reference")))}</dd>

                <dt>Evidence Notes</dt>
                <dd>{_esc(_display(evidence.get("notes")))}</dd>

                <dt>Source Record</dt>
                <dd>{_esc(source_record)}</dd>

                <dt>Effective At</dt>
                <dd>{_esc(_display(context.get("effective_at")))}</dd>

                <dt>Expires At</dt>
                <dd>{_esc(_display(context.get("expires_at")))}</dd>

                <dt>Created At</dt>
                <dd>{_esc(_display(context.get("created_at")))}</dd>

                <dt>Updated At</dt>
                <dd>{_esc(_display(context.get("updated_at")))}</dd>

            </dl>

        </div>

    </section>
    """


def _render_relationships(relationships):
    if not relationships:
        return """
        <div class="relationship-row muted">
            No canonical relationship currently connects these subjects.
        </div>
        """

    items = []

    for relationship in relationships:

        status = (
            relationship.get("relationship_status")
            or "unknown"
        )

        relationship_type = (
            relationship.get("relationship_type")
            or "unspecified"
        )

        basis = (
            relationship.get("relationship_basis")
            or "unspecified"
        )

        scope = (
            relationship.get("scope")
            or "unspecified"
        )

        relationship_id = relationship.get(
            "relationship_id"
        )

        items.append(
            f"""
            <div class="relationship-row">

                <div class="relationship-main">

                    <span class="status-pill">
                        {_esc(status.upper())}
                    </span>

                    <strong>
                        {_esc(relationship_type.replace("_", " "))}
                    </strong>

                </div>

                <div class="meta">
                    canonical relationship #{_esc(relationship_id)}
                    · basis {_esc(basis.replace("_", " "))}
                    · scope {_esc(scope)}
                </div>

            </div>
            """
        )

    return "\n".join(items)


def render_inspect_detail(detail):
    participants = detail["participants"]

    need_subject = participants[
        "need_subject"
    ]

    offer_subject = participants[
        "offer_subject"
    ]

    safety = detail[
        "safety_boundary"
    ]

    relationship_html = _render_relationships(
        detail.get(
            "relationship_context",
            [],
        )
    )

    warnings = detail.get(
        "warnings",
        [],
    )

    warning_html = ""

    if warnings:
        warning_html = """
        <section class="warning-box">
            <div class="section-label">WARNINGS</div>
            {}
        </section>
        """.format(
            "".join(
                f"<p>{_esc(warning)}</p>"
                for warning in warnings
            )
        )

    caution_html = ""

    if detail.get("caution"):
        caution_html = f"""
        <section class="warning-box">

            <div class="section-label">
                CAUTION
            </div>

            <p>
                {_esc(detail["caution"])}
            </p>

        </section>
        """

    need_html = _render_context_panel(
        "NEED EVIDENCE",
        detail["need"],
    )

    offer_html = _render_context_panel(
        "OFFER EVIDENCE",
        detail["offer"],
    )

    return f"""<!doctype html>
<html lang="en">

<head>

<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width, initial-scale=1"
>

<title>FCIS Inspect · {_esc(detail["signal"]["display"])}</title>

<style>

* {{
    box-sizing: border-box;
}}

html,
body {{
    margin: 0;
    min-height: 100%;
    background: #060606;
    color: #eee;
    font-family: Inter, Arial, sans-serif;
}}

body {{
    padding: 42px 24px 72px;
}}

.shell {{
    width: min(1120px, 100%);
    margin: 0 auto;
}}

.masthead {{
    padding-bottom: 26px;
    border-bottom: 1px solid #262626;
}}

.kicker,
.eyebrow,
.section-label {{
    color: #d4af37;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .16em;
}}

h1 {{
    margin: 10px 0 8px;
    font-family: Georgia, serif;
    font-size: clamp(34px, 5vw, 54px);
    font-weight: 400;
}}

h2 {{
    margin: 8px 0;
    font-family: Georgia, serif;
    font-size: 25px;
    font-weight: 400;
}}

.arrow {{
    color: #d4af37;
    padding: 0 8px;
}}

.subhead {{
    color: #888;
    line-height: 1.65;
}}

.identity {{
    margin-top: 26px;
    padding: 24px;
    border: 1px solid #262626;
    background: #101010;
    border-radius: 12px;
}}

.signal {{
    margin-top: 16px;
    color: #d4af37;
    font-size: 18px;
}}

.why {{
    margin-top: 18px;
    line-height: 1.7;
    color: #bbb;
}}

.context-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 22px;
    margin-top: 24px;
}}

.context-panel {{
    background: #101010;
    border: 1px solid #262626;
    border-radius: 12px;
    padding: 24px;
}}

.context-panel.unresolved {{
    border-color: #6e5a20;
}}

.context-heading {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
}}

.assertion,
.evidence {{
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid #242424;
}}

.assertion p {{
    line-height: 1.7;
    color: #ddd;
}}

dl {{
    display: grid;
    grid-template-columns: minmax(140px, 190px) 1fr;
    gap: 10px 20px;
    margin-bottom: 0;
}}

dt {{
    color: #777;
}}

dd {{
    margin: 0;
    color: #ccc;
    overflow-wrap: anywhere;
}}

.status-pill {{
    display: inline-block;
    padding: 5px 9px;
    border-radius: 999px;
    border: 1px solid #444;
    font-size: 10px;
    letter-spacing: .12em;
    color: #eee;
}}

.synthetic-notice {{
    margin-top: 14px;
    padding: 12px;
    border-left: 3px solid #d4af37;
    background: #17130a;
    color: #d4af37;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .08em;
    line-height: 1.5;
}}

.panel {{
    margin-top: 24px;
    padding: 24px;
    border: 1px solid #262626;
    border-radius: 12px;
    background: #101010;
}}

.relationship-row {{
    margin-top: 14px;
    padding: 16px;
    border: 1px solid #242424;
    border-radius: 8px;
    background: #0b0b0b;
}}

.relationship-main {{
    display: flex;
    align-items: center;
    gap: 12px;
}}

.meta {{
    margin-top: 7px;
    color: #777;
    font-size: 12px;
    line-height: 1.5;
}}

.human-question {{
    margin-top: 24px;
    padding: 24px;
    background: #0b0b0b;
    border: 1px solid #262626;
    border-radius: 12px;
}}

.human-question p {{
    margin-bottom: 10px;
    font-family: Georgia, serif;
    font-size: 25px;
}}

.review-required {{
    color: #d4af37;
    font-size: 11px;
    letter-spacing: .12em;
    font-weight: 700;
}}


.review-controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 18px;
}}

.review-button {{
    appearance: none;
    padding: 10px 14px;
    border: 1px solid #d4af37;
    border-radius: 6px;
    background: transparent;
    color: #d4af37;
    cursor: pointer;
    font-family: Inter, Arial, sans-serif;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .1em;
}}

.review-button:hover {{
    background: #d4af37;
    color: #060606;
}}

.review-button:disabled {{
    opacity: .45;
    cursor: default;
}}

.review-feedback {{
    min-height: 20px;
    margin-top: 14px;
    color: #888;
    font-size: 12px;
    line-height: 1.5;
}}

.review-feedback.error {{
    color: #d4af37;
}}

.warning-box {{
    margin-top: 24px;
    padding: 20px;
    border-left: 3px solid #d4af37;
    background: #17130a;
    line-height: 1.6;
}}

.safety {{
    margin-top: 24px;
    padding: 24px;
    border: 1px solid #262626;
    border-radius: 12px;
    background: #080808;
}}

.safety-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-top: 18px;
}}

.safety-item {{
    padding: 14px;
    border: 1px solid #222;
    border-radius: 8px;
    text-align: center;
}}

.safety-label {{
    color: #777;
    font-size: 10px;
    letter-spacing: .08em;
}}

.safety-value {{
    margin-top: 7px;
    font-weight: 700;
    color: #d4af37;
}}

.footer {{
    margin-top: 36px;
    padding-top: 20px;
    border-top: 1px solid #262626;
    color: #666;
    line-height: 1.6;
}}

code {{
    color: #ccc;
}}

.muted {{
    color: #777;
}}

@media (max-width: 800px) {{

    .context-grid {{
        grid-template-columns: 1fr;
    }}

    .safety-grid {{
        grid-template-columns: 1fr 1fr;
    }}

    dl {{
        grid-template-columns: 1fr;
    }}

}}

</style>

</head>

<body>

<div class="shell">

    <header class="masthead">

        <div class="kicker">
            FCIS · PRIVATE · INSPECT
        </div>

        <h1>
            {_esc(need_subject["name"])}
            <span class="arrow">↔</span>
            {_esc(offer_subject["name"])}
        </h1>

        <div class="subhead">
            Read-only inspection of the canonical context and
            evidence supporting this FCIS opportunity signal.
        </div>

    </header>

    <section class="identity">

        <div class="eyebrow">
            OPPORTUNITY SIGNAL
        </div>

        <div class="signal">
            {_esc(detail["signal"]["display"])}
        </div>

        <div class="meta">
            Card ID · <code>{_esc(detail["card_id"])}</code>
        </div>

        <div class="why">

            <div class="section-label">
                WHY FCIS SURFACED THIS
            </div>

            <p>
                {_esc(detail["why_surfaced"]["summary"])}
            </p>

        </div>

    </section>

    <div class="context-grid">

        {need_html}

        {offer_html}

    </div>

    <section class="panel">

        <div class="section-label">
            CANONICAL RELATIONSHIP CONTEXT
        </div>

        {relationship_html}

    </section>

    {caution_html}

    {warning_html}

    <section class="human-question">

        <div class="section-label">
            HUMAN QUESTION
        </div>

        <p>
            {_esc(detail["human_question"])}
        </p>

        <div class="review-required">
            HUMAN REVIEW REQUIRED
        </div>

        <div
            class="review-controls"
            data-card-id="{_esc(detail["card_id"])}"
        >
            <button
                class="review-button"
                type="button"
                data-review-disposition="investigating"
            >
                INVESTIGATE
            </button>

            <button
                class="review-button"
                type="button"
                data-review-disposition="held"
            >
                HOLD
            </button>

            <button
                class="review-button"
                type="button"
                data-review-disposition="dismissed"
            >
                DISMISS
            </button>
        </div>

        <div
            id="reviewFeedback"
            class="review-feedback"
            aria-live="polite"
        ></div>

        <div
            id="currentHumanReview"
            style="
                margin-top: 18px;
                padding-top: 16px;
                border-top: 1px solid rgba(255,255,255,0.12);
            "
        >
            <div
                class="section-label"
                style="margin-bottom: 8px;"
            >
                CURRENT HUMAN REVIEW
            </div>

            {
                (
                    '<div style="font-size: 13px; line-height: 1.7;">'
                    '<strong>Disposition:</strong> '
                    + _esc(
                        str(
                            detail["human_review"]["disposition"]
                        ).upper()
                    )
                    + '<br>'
                    '<strong>Reviewed by:</strong> '
                    + _esc(
                        detail["human_review"]["reviewer_email"]
                    )
                    + '<br>'
                    '<strong>Reviewed at:</strong> '
                    + _esc(
                        str(
                            detail["human_review"]["reviewed_at"]
                        )
                    )
                    + (
                        '<br><strong>Note:</strong> '
                        + _esc(
                            detail["human_review"]["reviewer_note"]
                        )
                        if detail["human_review"]["reviewer_note"]
                        else ''
                    )
                    + '</div>'
                )
                if detail.get("human_review")
                else (
                    '<div style="font-size: 13px; opacity: 0.72;">'
                    'No durable Human Review has been recorded.'
                    '</div>'
                )
            }
        </div>

    </section>

    <section class="safety">

        <div class="section-label">
            SAFETY BOUNDARY
        </div>

        <div class="safety-grid">

            <div class="safety-item">
                <div class="safety-label">
                    CANONICAL FACT CREATED
                </div>
                <div class="safety-value">
                    {"YES" if safety["canonical_fact_created"] else "NO"}
                </div>
            </div>

            <div class="safety-item">
                <div class="safety-label">
                    RELATIONSHIP CREATED
                </div>
                <div class="safety-value">
                    {"YES" if safety["relationship_created"] else "NO"}
                </div>
            </div>

            <div class="safety-item">
                <div class="safety-label">
                    ACTION AUTHORIZED
                </div>
                <div class="safety-value">
                    {"YES" if safety["action_authorized"] else "NO"}
                </div>
            </div>

            <div class="safety-item">
                <div class="safety-label">
                    WORKFLOW PERSISTED
                </div>
                <div class="safety-value">
                    {"YES" if safety["workflow_persisted"] else "NO"}
                </div>
            </div>

            <div class="safety-item">
                <div class="safety-label">
                    PUBLIC
                </div>
                <div class="safety-value">
                    {"YES" if safety["public"] else "NO"}
                </div>
            </div>

        </div>

    </section>

    <footer class="footer">
        FCIS INSPECT v1 is read-only.
        Evidence is displayed exactly from existing canonical context.
        No workflow action is created by viewing this inspection.
    </footer>

</div>

<script>
(function () {{
    const controls = document.querySelector(
        ".review-controls"
    );

    const feedback = document.getElementById(
        "reviewFeedback"
    );

    if (!controls) {{
        return;
    }}

    const cardId = controls.dataset.cardId || "";

    function setFeedback(text, isError) {{
        if (!feedback) {{
            return;
        }}

        feedback.textContent = text || "";

        feedback.classList.toggle(
            "error",
            Boolean(isError)
        );
    }}

    function setDisabled(disabled) {{
        controls.querySelectorAll(
            "[data-review-disposition]"
        ).forEach(function (button) {{
            button.disabled = Boolean(disabled);
        }});
    }}

    controls.addEventListener(
        "click",
        function (event) {{
            const button = event.target.closest(
                "[data-review-disposition]"
            );

            if (!button) {{
                return;
            }}

            const disposition =
                button.dataset.reviewDisposition || "";

            if (!cardId || !disposition) {{
                setFeedback(
                    "Unable to submit Human Review.",
                    true
                );

                return;
            }}

            setDisabled(true);

            setFeedback(
                "Submitting Human Review…",
                false
            );

            window.parent.postMessage(
                {{
                    type: "fcis-human-review",
                    card_id: cardId,
                    disposition: disposition
                }},
                "*"
            );
        }}
    );

    window.addEventListener(
        "message",
        function (event) {{
            if (event.source !== window.parent) {{
                return;
            }}

            const data = event.data || {{}};

            if (data.type !== "fcis-human-review-result") {{
                return;
            }}

            if (data.card_id !== cardId) {{
                return;
            }}

            setDisabled(false);

            if (data.ok) {{
                setFeedback(
                    "Human Review saved.",
                    false
                );

                window.setTimeout(
                    function () {{
                        setFeedback(
                            "",
                            false
                        );
                    }},
                    1800
                );
            }} else {{
                setFeedback(
                    data.error || "Human Review could not be saved.",
                    true
                );
            }}
        }}
    );
}})();
</script>

</body>
</html>
"""
