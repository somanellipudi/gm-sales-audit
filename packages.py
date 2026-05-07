from __future__ import annotations

from typing import Any

GROWINGMONK_OFFERS: dict[str, dict[str, Any]] = {
    "Free Growth Audit": {
        "label": "Free Growth Audit",
        "when_to_use": "When research confidence is low, public data is limited, or the prospect needs a low-risk first step before we can recommend a stronger growth path.",
        "client_description": "A focused, no-cost growth review that verifies the business profile, website, local visibility, and contact flow before recommending the next phase.",
        "internal_description": "Use this when data is limited, the business needs a safer first step, or more access is required before a stronger growth path can be scoped.",
        "pricing_mode": "No pricing shown",
        "access_required": ["GBP access", "website analytics", "booking/contact data"],
        "best_for": ["Unknown or incomplete data", "Prospects who need a low-risk first step", "Businesses with limited tracking or site access"],
        "not_for": ["Well-structured multi-location businesses", "Prospects already ready for a defined 30-day sprint", "Clients with mature analytics and tracking"],
    },
    "Tracking Setup First": {
        "label": "Tracking Setup First",
        "when_to_use": "When analytics, measurement, or conversion tracking is missing or unclear, and the business needs a measurement foundation before stronger performance claims can be made.",
        "client_description": "Set up the measurement foundation first so future growth work is based on reliable Google Analytics, Search Console, ad tracking, and contact conversion data.",
        "internal_description": "Use this when tracking gaps prevent confident recommendations and the audit cannot support a stronger growth path without measurement access.",
        "pricing_mode": "No pricing shown",
        "access_required": ["GA4 access", "Search Console access", "website tag access", "ad account access"],
        "best_for": ["Businesses with missing or incomplete analytics", "Clients without tracking or conversion setup", "Prospects who need reliable performance data first"],
        "not_for": ["Businesses with a mature measurement foundation", "Clients ready for a sprint-based growth engagement", "Multi-location brands with established reporting"],
    },
    "30-Day Growth Sprint": {
        "label": "30-Day Growth Sprint",
        "when_to_use": "When there are visible quick-win issues in contact flow, website conversion, local visibility, or offer clarity and the business is ready for a focused first growth push.",
        "client_description": "A focused 30-day sprint to improve visibility, message clarity, contact flow, and early tracking so the business can start seeing more qualified demand quickly.",
        "internal_description": "Use this as the default recommended growth path for most first-time local leads and businesses with visible website or local opportunity gaps.",
        "pricing_mode": "No pricing shown",
        "access_required": ["Website access", "GBP access", "basic analytics access"],
        "best_for": ["First-time local leads", "Businesses with visible contact or local visibility gaps", "Prospects needing a measurable first sprint"],
        "not_for": ["Businesses with fully mature tracking and ongoing growth systems", "Clients who only need measurement setup", "Highly fragmented multi-location brands without a clear first location"],
    },
    "Monthly Growth System": {
        "label": "Monthly Growth System",
        "when_to_use": "When the business shows stronger public maturity, multi-location or franchise needs, or requires ongoing content, ads, and local growth execution.",
        "client_description": "A recurring growth system focused on ongoing visibility, content, campaigns, reviews, and local performance once the initial foundation is established.",
        "internal_description": "Use this for more mature or multi-location prospects that are suited for ongoing support rather than a one-off sprint.",
        "pricing_mode": "No pricing shown",
        "access_required": ["Website access", "GBP access", "analytics access", "campaign/ads access"],
        "best_for": ["Multi-location or franchise businesses", "Prospects with stronger public maturity", "Clients seeking ongoing growth support"],
        "not_for": ["New local leads without tracking", "Businesses not ready for ongoing execution", "Prospects requiring a discovery-first approach"],
    },
}


def allowed_offer_labels() -> list[str]:
    return list(GROWINGMONK_OFFERS.keys())


def get_offer(label: str) -> dict[str, Any] | None:
    return GROWINGMONK_OFFERS.get(str(label).strip())


def offer_prompt_context() -> str:
    lines = [
        "Choose exactly one offer from the allowed list below. Do not invent package names. Do not mention pricing.",
        "Allowed offers:",
    ]
    for offer in allowed_offer_labels():
        details = get_offer(offer) or {}
        lines.append(f"- {offer}: {details.get('when_to_use', '').strip()}")
    lines.append(
        "Use the chosen offer as the recommended next step or growth path language, not as a sales package label in the client report."
    )
    lines.append(
        "Final investment will be recommended after confirming access, business goals, scope, ad budget, and execution requirements."
    )
    return "\n".join(lines)


def normalize_offer_label(value: Any) -> str:
    if not value:
        return "30-Day Growth Sprint"
    label = str(value).strip()
    normalized = label.lower()
    if normalized in [offer.lower() for offer in allowed_offer_labels()]:
        return next(offer for offer in allowed_offer_labels() if offer.lower() == normalized)
    if "free" in normalized and "audit" in normalized:
        return "Free Growth Audit"
    if "tracking" in normalized or "measurement" in normalized or "analytics" in normalized:
        return "Tracking Setup First"
    if "monthly" in normalized or "system" in normalized or "ongoing" in normalized or "retain" in normalized:
        return "Monthly Growth System"
    if "30" in normalized or "sprint" in normalized or "growth sprint" in normalized or "next step" in normalized:
        return "30-Day Growth Sprint"
    if "audit" in normalized and "free" not in normalized:
        return "30-Day Growth Sprint"
    if "path" in normalized and "growth" in normalized:
        return "30-Day Growth Sprint"
    return "30-Day Growth Sprint"
