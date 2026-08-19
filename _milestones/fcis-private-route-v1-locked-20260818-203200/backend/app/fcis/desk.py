"""
FCIS Private Intelligence Desk v1

Read-only internal HTML renderer for structured Opportunity Cards.

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

from backend.app.fcis.opportunity_cards import (
    assemble_opportunity_cards,
)


DESK_SCHEMA_VERSION = "fcis_private_intelligence_desk_v1"


def _esc(value):
    if value is None:
        return ""

    return escape(
        str(value),
        quote=True,
    )


def _relationship_label(relationship):
    status = (
        relationship.get("relationship_status")
        or "unknown"
    ).upper()

    relationship_type = (
        relationship.get("relationship_type")
        or "unspecified"
    )

    basis = (
        relationship.get("relationship_basis")
        or "unspecified"
    )

    return (
        f"{status} · "
        f"{relationship_type.replace('_', ' ')} · "
        f"{basis.replace('_', ' ')}"
    )


def render_opportunity_card(card):
    need_subject = card[
        "participants"
    ]["need_subject"]

    offer_subject = card[
        "participants"
    ]["offer_subject"]

    relationships = card.get(
        "relationship_context",
        [],
    )

    relationship_html = ""

    if relationships:
        items = []

        for relationship in relationships:
            status = (
                relationship.get(
                    "relationship_status"
                )
                or "unknown"
            )

            status_class = (
                "active"
                if status == "active"
                else "caution"
            )

            items.append(
                f"""
                <div class="relationship-row">
                    <span class="status-pill {status_class}">
                        {_esc(status.upper())}
                    </span>
                    <span>
                        {_esc(_relationship_label(relationship))}
                    </span>
                </div>
                """
            )

        relationship_html = "\n".join(items)

    else:
        relationship_html = (
            '<div class="relationship-row muted">'
            'No canonical relationship currently connects these subjects.'
            '</div>'
        )

    caution_html = ""

    if card.get("caution"):
        caution_html = f"""
        <div class="caution-box">
            <div class="eyebrow">CAUTION</div>
            <div>{_esc(card["caution"])}</div>
        </div>
        """

    return f"""
    <article class="opportunity-card" id="{_esc(card["card_id"])}">

        <div class="card-topline">
            <div>
                <div class="eyebrow">WORTH A LOOK</div>
                <div class="status-pill new">NEW</div>
            </div>

            <div class="private-label">
                OUR EYES ONLY
            </div>
        </div>

        <h2>
            {_esc(need_subject["name"])}
            <span class="arrow">↔</span>
            {_esc(offer_subject["name"])}
        </h2>

        <div class="signal">
            {_esc(card["signal"]["display"])}
        </div>

        <section>
            <div class="section-label">
                WHY THIS SURFACED
            </div>

            <p>
                {_esc(card["why_surfaced"]["summary"])}
            </p>
        </section>

        <section class="context-grid">

            <div class="context-panel">
                <div class="section-label">
                    NEED
                </div>

                <strong>
                    {_esc(card["need_context"]["subject_name"])}
                </strong>

                <p>
                    {_esc(card["need_context"]["context_value"])}
                </p>

                <div class="meta">
                    scope · {_esc(card["need_context"]["scope"])}
                </div>
            </div>

            <div class="context-panel">
                <div class="section-label">
                    OFFER
                </div>

                <strong>
                    {_esc(card["offer_context"]["subject_name"])}
                </strong>

                <p>
                    {_esc(card["offer_context"]["context_value"])}
                </p>

                <div class="meta">
                    scope · {_esc(card["offer_context"]["scope"])}
                </div>
            </div>

        </section>

        <section>
            <div class="section-label">
                RELATIONSHIP CONTEXT
            </div>

            {relationship_html}
        </section>

        {caution_html}

        <section class="human-review">

            <div class="section-label">
                HUMAN QUESTION
            </div>

            <p>
                {_esc(card["human_question"])}
            </p>

            <div class="review-required">
                HUMAN REVIEW REQUIRED
            </div>

        </section>

        <details class="inspect">
            <summary>INSPECT</summary>

            <div class="inspect-body">

                <div>
                    Card ID:
                    <code>{_esc(card["card_id"])}</code>
                </div>

                <div>
                    Need context:
                    <code>{_esc(card["need_context"]["context_id"])}</code>
                </div>

                <div>
                    Offer context:
                    <code>{_esc(card["offer_context"]["context_id"])}</code>
                </div>

                <div>
                    Canonical fact created:
                    <strong>NO</strong>
                </div>

                <div>
                    Relationship created:
                    <strong>NO</strong>
                </div>

                <div>
                    Action authorized:
                    <strong>NO</strong>
                </div>

                <div>
                    Workflow persisted:
                    <strong>NO</strong>
                </div>

            </div>
        </details>

    </article>
    """


def render_private_intelligence_desk(db):
    cards = assemble_opportunity_cards(db)

    card_html = "\n".join(
        render_opportunity_card(card)
        for card in cards
    )

    count = len(cards)

    return f"""<!doctype html>
<html lang="en">

<head>

<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>FCIS Private Intelligence Desk</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #060606;
    color: #f3efe4;
    font-family: Inter, Arial, sans-serif;
}}

.shell {{
    width: min(1180px, 92vw);
    margin: 0 auto;
    padding: 48px 0 80px;
}}

.masthead {{
    border-bottom: 1px solid rgba(212,175,55,.28);
    padding-bottom: 26px;
    margin-bottom: 30px;
}}

.kicker {{
    color: #d4af37;
    font-size: 12px;
    letter-spacing: .18em;
    font-weight: 700;
}}

h1 {{
    font-family: Georgia, serif;
    font-weight: 400;
    font-size: clamp(34px, 5vw, 58px);
    margin: 10px 0 8px;
}}

.subhead {{
    color: #aaa;
    line-height: 1.6;
}}

.desk-summary {{
    display: flex;
    gap: 18px;
    margin: 24px 0 34px;
}}

.summary-box {{
    border: 1px solid #242424;
    padding: 16px 20px;
    background: #0d0d0d;
    border-radius: 8px;
}}

.summary-number {{
    color: #d4af37;
    font-size: 30px;
    font-family: Georgia, serif;
}}

.summary-label {{
    color: #888;
    font-size: 12px;
    letter-spacing: .12em;
    text-transform: uppercase;
}}

.cards {{
    display: grid;
    gap: 24px;
}}

.opportunity-card {{
    background: #111;
    border: 1px solid #262626;
    border-radius: 12px;
    padding: 28px;
}}

.card-topline {{
    display: flex;
    justify-content: space-between;
    gap: 20px;
}}

.eyebrow,
.section-label {{
    color: #d4af37;
    font-size: 11px;
    letter-spacing: .16em;
    font-weight: 700;
    text-transform: uppercase;
}}

.private-label {{
    color: #777;
    font-size: 11px;
    letter-spacing: .14em;
}}

h2 {{
    font-family: Georgia, serif;
    font-size: 30px;
    font-weight: 400;
    margin: 22px 0 8px;
}}

.arrow {{
    color: #d4af37;
    padding: 0 8px;
}}

.signal {{
    color: #d4af37;
    font-size: 19px;
    margin-bottom: 28px;
    text-transform: capitalize;
}}

section {{
    border-top: 1px solid #252525;
    margin-top: 20px;
    padding-top: 20px;
}}

p {{
    line-height: 1.65;
    color: #ccc;
}}

.context-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}}

.context-panel {{
    background: #0b0b0b;
    border: 1px solid #222;
    padding: 18px;
    border-radius: 8px;
}}

.meta {{
    color: #777;
    font-size: 12px;
}}

.relationship-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    color: #bbb;
    margin-top: 10px;
}}

.status-pill {{
    display: inline-block;
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 10px;
    letter-spacing: .12em;
    font-weight: 700;
}}

.status-pill.new {{
    margin-top: 8px;
    background: #17130a;
    color: #d4af37;
    border: 1px solid rgba(212,175,55,.4);
}}

.status-pill.active {{
    border: 1px solid #444;
    color: #eee;
}}

.status-pill.caution {{
    border: 1px solid #6e5a20;
    color: #d4af37;
}}

.caution-box {{
    margin-top: 20px;
    border-left: 3px solid #d4af37;
    background: #17130a;
    padding: 16px;
    line-height: 1.6;
}}

.human-review {{
    background: #0b0b0b;
    padding: 20px;
    border: 1px solid #222;
    border-radius: 8px;
}}

.review-required {{
    display: inline-block;
    color: #d4af37;
    font-size: 11px;
    letter-spacing: .12em;
    font-weight: 700;
}}

.inspect {{
    margin-top: 20px;
    border-top: 1px solid #252525;
    padding-top: 20px;
}}

.inspect summary {{
    display: inline-block;
    cursor: pointer;
    color: #d4af37;
    border: 1px solid #d4af37;
    border-radius: 6px;
    padding: 9px 14px;
    font-size: 12px;
    letter-spacing: .12em;
    font-weight: 700;
}}

.inspect-body {{
    margin-top: 16px;
    background: #080808;
    border: 1px solid #222;
    padding: 16px;
    line-height: 1.8;
    color: #aaa;
}}

code {{
    color: #ddd;
}}

.muted {{
    color: #777;
}}

.footer {{
    margin-top: 36px;
    border-top: 1px solid rgba(212,175,55,.28);
    padding-top: 22px;
    color: #888;
    font-size: 13px;
}}

@media (max-width: 760px) {{

    .context-grid {{
        grid-template-columns: 1fr;
    }}

    .card-topline {{
        flex-direction: column;
    }}

}}

</style>

</head>

<body>

<div class="shell">

    <header class="masthead">

        <div class="kicker">
            FCIS · PRIVATE
        </div>

        <h1>
            Intelligence Desk
        </h1>

        <div class="subhead">
            Our eyes only. Verified network context and
            correlation signals requiring human review.
        </div>

    </header>

    <div class="desk-summary">

        <div class="summary-box">

            <div class="summary-number">
                {count}
            </div>

            <div class="summary-label">
                New signals
            </div>

        </div>

    </div>

    <main class="cards">
        {card_html}
    </main>

    <footer class="footer">
        FCIS discovers opportunity. Humans authorize action.
        No workflow action is persisted by Desk v1.
    </footer>

</div>

</body>
</html>
"""


def write_private_intelligence_desk(
    db,
    destination,
):
    html = render_private_intelligence_desk(
        db
    )

    destination.write_text(
        html,
        encoding="utf-8",
    )

    return {
        "destination": str(destination),
        "card_count": len(
            assemble_opportunity_cards(db)
        ),
        "schema_version": DESK_SCHEMA_VERSION,
    }
