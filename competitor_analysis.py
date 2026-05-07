from __future__ import annotations

from statistics import mean
from typing import Any


THEMES = {
    "Salon / Beauty": [
        "haircut",
        "hair color",
        "keratin",
        "bridal",
        "facial",
        "waxing",
        "stylist",
        "staff",
        "hygiene",
        "appointment",
        "waiting",
        "price",
        "clean",
        "service",
    ],
    "Restaurant / Cafe": [
        "taste",
        "service",
        "ambience",
        "waiting",
        "delivery",
        "price",
        "hygiene",
        "quantity",
        "staff",
        "parking",
        "family",
        "biryani",
        "breakfast",
        "buffet",
    ],
    "Local Service": [
        "response time",
        "pricing",
        "quality",
        "punctuality",
        "staff",
        "professionalism",
        "trust",
        "service delay",
    ],
}

CONCERN_WORDS = {"bad", "poor", "delay", "late", "waiting", "expensive", "rude", "dirty", "slow", "issue", "problem"}


def _rating(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _review_count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def compare_google_review_position(business: dict, competitors: list[dict]) -> dict:
    valid_competitors = [c for c in competitors if not c.get("error")]
    competitor_ratings = [_rating(c.get("rating")) for c in valid_competitors if _rating(c.get("rating")) is not None]
    competitor_counts = [_review_count(c.get("user_ratings_total")) for c in valid_competitors]

    client_count = _review_count(business.get("user_ratings_total"))
    avg_count = round(mean(competitor_counts), 1) if competitor_counts else None
    avg_rating = round(mean(competitor_ratings), 2) if competitor_ratings else None
    top_by_reviews = max(valid_competitors, key=lambda c: _review_count(c.get("user_ratings_total")), default={})
    top_by_rating = max(valid_competitors, key=lambda c: _rating(c.get("rating")) or 0, default={})
    gap_avg = round((avg_count or 0) - client_count, 1) if avg_count is not None else None
    gap_top = _review_count(top_by_reviews.get("user_ratings_total")) - client_count if top_by_reviews else None

    if avg_count is None:
        summary = "Competitor review data is limited, so local trust position should be reviewed manually."
    elif gap_avg and gap_avg > 0:
        summary = "The business appears to have a review-volume gap versus nearby competitors."
    else:
        summary = "The business does not appear behind the sampled competitors on review volume."

    return {
        "client_rating": business.get("rating"),
        "client_review_count": client_count,
        "avg_competitor_rating": avg_rating,
        "avg_competitor_review_count": avg_count,
        "top_competitor_by_reviews": top_by_reviews,
        "top_competitor_by_rating": top_by_rating,
        "review_volume_gap_vs_average": gap_avg,
        "review_volume_gap_vs_top": gap_top,
        "trust_gap_summary": summary,
    }


def summarize_review_themes(reviews: list[dict], niche: str) -> dict:
    keywords = THEMES.get(niche, THEMES["Local Service"])
    counts = {keyword: 0 for keyword in keywords}
    concern_counts = {keyword: 0 for keyword in keywords}

    for review in reviews or []:
        text = str(review.get("text", "")).lower()
        is_concern = any(word in text for word in CONCERN_WORDS)
        for keyword in keywords:
            if keyword in text:
                counts[keyword] += 1
                if is_concern:
                    concern_counts[keyword] += 1

    praised = [key for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count > 0][:6]
    concerns = [key for key, count in sorted(concern_counts.items(), key=lambda item: item[1], reverse=True) if count > 0][:6]

    return {
        "praised_themes": praised,
        "concern_themes": concerns,
        "raw_theme_counts": counts,
        "sample_size": len(reviews or []),
        "note": "Review sample is limited because Google Places returns only a small public sample."
        if len(reviews or []) < 10
        else "",
    }


def analyze_competitors(business: dict, competitors: list[dict], niche: str) -> dict:
    valid_competitors = [c for c in competitors if not c.get("error")]
    table = [
        {
            "name": c.get("name"),
            "rating": c.get("rating"),
            "review_count": c.get("user_ratings_total"),
            "address": c.get("formatted_address"),
            "website": c.get("website"),
            "google_maps_url": c.get("google_maps_url"),
        }
        for c in valid_competitors
    ]

    strengths = {}
    weaknesses = {}
    for c in valid_competitors:
        name = c.get("name", "Competitor")
        strengths[name] = []
        weaknesses[name] = []
        if _review_count(c.get("user_ratings_total")) > _review_count(business.get("user_ratings_total")):
            strengths[name].append("Higher visible Google review volume")
        if (_rating(c.get("rating")) or 0) >= (_rating(business.get("rating")) or 0):
            strengths[name].append("Comparable or stronger visible rating")
        if not c.get("website"):
            weaknesses[name].append("Website not found in Places data")
        if not c.get("phone_number"):
            weaknesses[name].append("Phone not found in Places details")

    all_reviews = list(business.get("reviews", []) or [])
    for competitor in valid_competitors:
        all_reviews.extend(competitor.get("reviews", []) or [])

    return {
        "review_position": compare_google_review_position(business, valid_competitors),
        "review_themes": summarize_review_themes(all_reviews, niche),
        "competitor_table_data": table,
        "strengths_by_competitor": strengths,
        "possible_weaknesses_by_competitor": weaknesses,
        "what_client_can_learn": [
            "Improve review volume and recency if competitors are visibly ahead.",
            "Make contact, booking, and offer clarity easier than competitors.",
            "Use review themes as content and service-improvement inputs.",
        ],
        "limitations": "Competitor and review analysis uses public Google Places data and may be a limited sample.",
    }
