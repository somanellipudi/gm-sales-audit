from __future__ import annotations

import os
from difflib import SequenceMatcher
from urllib.parse import unquote
from typing import Any

import requests
import streamlit as st


TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

DETAIL_FIELDS = (
    "name,place_id,formatted_address,formatted_phone_number,"
    "international_phone_number,website,url,rating,user_ratings_total,"
    "business_status,type,opening_hours,reviews,geometry"
)

NICHE_QUERY = {
    "Salon / Beauty": "salon",
    "Restaurant / Cafe": "restaurant",
    "Local Service": "local service",
    "Clinic / Wellness": "clinic",
    "Gym / Fitness": "gym",
    "Coach / Consultant": "coach consultant",
    "Ecommerce / D2C": "",
    "Franchise / Multi-location": "",
    "Laundry / Dry Cleaning": "laundry dry cleaning",
}

PLACE_TYPE_TO_NICHE = {
    "beauty_salon": "Salon / Beauty",
    "hair_care": "Salon / Beauty",
    "restaurant": "Restaurant / Cafe",
    "cafe": "Restaurant / Cafe",
    "meal_takeaway": "Restaurant / Cafe",
    "doctor": "Clinic / Wellness",
    "dentist": "Clinic / Wellness",
    "hospital": "Clinic / Wellness",
    "physiotherapist": "Clinic / Wellness",
    "gym": "Gym / Fitness",
    "laundry": "Laundry / Dry Cleaning",
}


def _get_secret_or_env(name: str, default: str | None = None) -> str | None:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    value = os.getenv(name, default)
    return str(value).strip() if value else None


def _maps_key() -> str | None:
    return _get_secret_or_env("GOOGLE_MAPS_API_KEY")


def _request_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=25)
        payload = response.json()
    except requests.RequestException as exc:
        return {"error": f"Google Places request failed: {exc}"}
    except ValueError as exc:
        return {"error": f"Google Places returned invalid JSON: {exc}"}

    status = payload.get("status")
    if status not in {"OK", "ZERO_RESULTS"}:
        return {"error": payload.get("error_message") or f"Google Places returned status {status}"}
    return payload


def _clean_place_details(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result", {})
    geometry = result.get("geometry", {}).get("location", {})
    return {
        "name": result.get("name"),
        "place_id": result.get("place_id"),
        "formatted_address": result.get("formatted_address"),
        "phone_number": result.get("formatted_phone_number"),
        "international_phone_number": result.get("international_phone_number"),
        "website": result.get("website"),
        "google_maps_url": result.get("url"),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "business_status": result.get("business_status"),
        "types": result.get("types", []),
        "opening_hours": result.get("opening_hours", {}),
        "reviews": result.get("reviews", []),
        "latitude": geometry.get("lat"),
        "longitude": geometry.get("lng"),
        "source": "google_places",
        "error": None,
    }


def _compact_place(result: dict[str, Any]) -> dict[str, Any]:
    geometry = result.get("geometry", {}).get("location", {})
    return {
        "name": result.get("name"),
        "place_id": result.get("place_id"),
        "formatted_address": result.get("formatted_address") or result.get("vicinity"),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "types": result.get("types", []),
        "latitude": geometry.get("lat"),
        "longitude": geometry.get("lng"),
    }


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def search_place(business_name: str, city: str) -> dict[str, Any]:
    api_key = _maps_key()
    if not api_key:
        return {"error": "Missing GOOGLE_MAPS_API_KEY"}

    payload = _request_json(
        TEXT_SEARCH_URL,
        {"query": f"{business_name} {city}".strip(), "key": api_key},
    )
    if payload.get("error"):
        return payload

    results = payload.get("results", [])
    if not results:
        return {"error": "No Google Places match found"}

    return _compact_place(results[0])


def search_place_options(business_name: str, city: str, max_results: int = 5) -> list[dict[str, Any]]:
    api_key = _maps_key()
    if not api_key:
        return [{"error": "Missing GOOGLE_MAPS_API_KEY"}]

    payload = _request_json(
        TEXT_SEARCH_URL,
        {"query": f"{business_name} {city}".strip(), "key": api_key},
    )
    if payload.get("error"):
        return [payload]
    return [_compact_place(result) for result in payload.get("results", [])[:max_results]]


def get_place_details(place_id: str) -> dict[str, Any]:
    api_key = _maps_key()
    if not api_key:
        return {"error": "Missing GOOGLE_MAPS_API_KEY"}
    if not place_id:
        return {"error": "Missing place_id"}

    payload = _request_json(
        DETAILS_URL,
        {"place_id": place_id, "fields": DETAIL_FIELDS, "reviews_sort": "newest", "key": api_key},
    )
    if payload.get("error"):
        return payload
    return _clean_place_details(payload)


def _competitor_query(niche: str) -> str:
    return NICHE_QUERY.get(niche, niche).strip()


def infer_niche_from_place(place: dict[str, Any]) -> str:
    types = place.get("types") or []
    for place_type in types:
        if place_type in PLACE_TYPE_TO_NICHE:
            return PLACE_TYPE_TO_NICHE[place_type]

    name = str(place.get("name") or "").lower()
    if "salon" in name or "beauty" in name:
        return "Salon / Beauty"
    if "restaurant" in name or "cafe" in name:
        return "Restaurant / Cafe"
    if "clinic" in name or "wellness" in name:
        return "Clinic / Wellness"
    if "gym" in name or "fitness" in name:
        return "Gym / Fitness"
    if "laundry" in name or "dry clean" in name:
        return "Laundry / Dry Cleaning"
    return "Other"


def _query_from_google_maps_link(link: str) -> str:
    decoded = unquote(link or "")
    match = re_search_patterns(decoded)
    return match.strip()


def re_search_patterns(text: str) -> str:
    import re

    for pattern in (r"/place/([^/?]+)", r"query=([^&]+)", r"q=([^&]+)"):
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace("+", " ")
    return text


def resolve_business_identity(business_name: str, city: str, google_maps_link: str = "") -> dict[str, Any]:
    search_query = business_name
    if google_maps_link:
        clue = _query_from_google_maps_link(google_maps_link)
        if clue and not clue.startswith("http"):
            search_query = clue

    options = search_place_options(search_query, city)
    if options and options[0].get("error"):
        return {"error": options[0]["error"], "place_options": options}
    if not options:
        return {"error": "No Google Places match found", "place_options": []}

    best = options[0]
    details = get_place_details(best.get("place_id", ""))
    if details.get("error"):
        details = best

    return {
        "selected_place": details,
        "place_options": options,
        "match_confidence": _similar(details.get("name", ""), business_name),
        "used_google_maps_link": bool(google_maps_link),
        "error": None,
    }


def find_nearby_competitors(
    lat: float,
    lng: float,
    niche: str,
    radius_meters: int = 3000,
    max_results: int = 5,
    exclude_name: str = "",
    exclude_place_id: str = "",
) -> list[dict[str, Any]]:
    api_key = _maps_key()
    if not api_key:
        return [{"error": "Missing GOOGLE_MAPS_API_KEY"}]

    keyword = _competitor_query(niche)
    if not keyword:
        return []

    payload = _request_json(
        NEARBY_SEARCH_URL,
        {
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "keyword": keyword,
            "key": api_key,
        },
    )
    if payload.get("error"):
        return [payload]

    competitors = []
    for result in payload.get("results", []):
        if exclude_place_id and result.get("place_id") == exclude_place_id:
            continue
        if exclude_name and _similar(result.get("name", ""), exclude_name) >= 0.72:
            continue
        details = get_place_details(result.get("place_id", ""))
        competitors.append(details if not details.get("error") else _compact_place(result))
        if len(competitors) >= max_results:
            break

    return competitors
