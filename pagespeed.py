from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
VALID_STRATEGIES = {"mobile", "desktop"}


def _get_secret(name: str) -> str:
    try:
        value = st.secrets[name]
    except (FileNotFoundError, KeyError):
        value = os.getenv(name, "")
    return str(value).strip()


def _score(categories: dict[str, Any], key: str) -> int | None:
    score = categories.get(key, {}).get("score")
    if score is None:
        return None
    return round(score * 100)


def _audit_display_value(audits: dict[str, Any], key: str) -> str | None:
    value = audits.get(key, {}).get("displayValue")
    return value if value else None


def _top_opportunities(audits: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    opportunities = []
    for audit_id, audit in audits.items():
        details = audit.get("details", {})
        savings = details.get("overallSavingsMs")
        if audit.get("score") == 1 or savings is None:
            continue
        opportunities.append(
            {
                "id": audit_id,
                "title": audit.get("title"),
                "description": audit.get("description"),
                "estimated_savings_ms": savings,
                "display_value": audit.get("displayValue"),
            }
        )

    return sorted(
        opportunities,
        key=lambda item: item.get("estimated_savings_ms") or 0,
        reverse=True,
    )[:limit]


def get_pagespeed_summary(url: str, strategy: str = "mobile") -> dict[str, Any]:
    if strategy not in VALID_STRATEGIES:
        strategy = "mobile"

    params: dict[str, Any] = {
        "url": url,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices", "seo"],
    }

    api_key = _get_secret("PAGESPEED_API_KEY")
    if api_key:
        params["key"] = api_key

    try:
        response = requests.get(PAGESPEED_ENDPOINT, params=params, timeout=45)
    except requests.RequestException as exc:
        return {
            "final_url": url,
            "strategy": strategy,
            "error": f"PageSpeed request failed: {exc}",
        }

    try:
        payload = response.json()
    except ValueError as exc:
        return {
            "final_url": url,
            "strategy": strategy,
            "error": f"PageSpeed returned invalid JSON: {exc}",
        }

    if not response.ok or "error" in payload:
        message = payload.get("error", {}).get("message", response.reason)
        return {
            "final_url": url,
            "strategy": strategy,
            "error": f"PageSpeed request failed: {message}",
        }

    lighthouse = payload.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    return {
        "final_url": lighthouse.get("finalUrl", url),
        "strategy": strategy,
        "performance_score": _score(categories, "performance"),
        "accessibility_score": _score(categories, "accessibility"),
        "best_practices_score": _score(categories, "best-practices"),
        "seo_score": _score(categories, "seo"),
        "first_contentful_paint": _audit_display_value(audits, "first-contentful-paint"),
        "largest_contentful_paint": _audit_display_value(audits, "largest-contentful-paint"),
        "total_blocking_time": _audit_display_value(audits, "total-blocking-time"),
        "cumulative_layout_shift": _audit_display_value(audits, "cumulative-layout-shift"),
        "speed_index": _audit_display_value(audits, "speed-index"),
        "top_opportunities": _top_opportunities(audits),
        "error": None,
    }
