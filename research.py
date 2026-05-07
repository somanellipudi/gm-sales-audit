from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import requests
import streamlit as st


SERPAPI_URL = "https://serpapi.com/search.json"


def _get_secret_or_env(name: str, default: str | None = None) -> str | None:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value).strip()
    except Exception:
        pass
    value = os.getenv(name, default)
    return str(value).strip() if value else None


def _source_domain(link: str) -> str:
    return urlparse(link).netloc.replace("www.", "")


def build_manual_search_queries(
    business_name: str,
    city: str,
    niche: str,
    website: str = "",
    instagram: str = "",
) -> list[str]:
    queries = [
        f"{business_name} {city} phone",
        f"{business_name} {city} WhatsApp",
        f"{business_name} {city} reviews",
        f"{business_name} {city} services",
        f"{business_name} {city} price",
        f"{business_name} near me reviews",
        f'site:instagram.com "{business_name}"',
        f'site:justdial.com "{business_name}" "{city}"',
        f'site:sulekha.com "{business_name}" "{city}"',
    ]
    if website:
        queries.append(f'"{business_name}" "{website}"')
    if instagram:
        queries.append(f'"{business_name}" "{instagram}"')
    if niche == "Restaurant / Cafe":
        queries.extend(
            [
                f'site:zomato.com "{business_name}" "{city}"',
                f'site:swiggy.com "{business_name}" "{city}"',
            ]
        )
    if niche == "Clinic / Wellness":
        queries.append(f'site:practo.com "{business_name}" "{city}"')
    return queries


def web_search(query: str, num_results: int = 5) -> list[dict[str, Any]]:
    api_key = _get_secret_or_env("SERPAPI_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            SERPAPI_URL,
            params={"engine": "google", "q": query, "num": num_results, "api_key": api_key},
            timeout=25,
        )
        payload = response.json()
    except requests.RequestException:
        return []
    except ValueError:
        return []

    results = []
    for item in payload.get("organic_results", [])[:num_results]:
        link = item.get("link", "")
        results.append(
            {
                "title": item.get("title"),
                "link": link,
                "snippet": item.get("snippet"),
                "source_domain": _source_domain(link),
                "query": query,
            }
        )
    return results


def research_business_public_presence(
    business_name: str,
    city: str,
    website: str,
    instagram: str,
    niche: str,
) -> dict[str, Any]:
    queries = build_manual_search_queries(business_name, city, niche, website, instagram)
    api_key = _get_secret_or_env("SERPAPI_API_KEY")
    if not api_key:
        return {
            "available": False,
            "error": "SERPAPI_API_KEY missing. Automated public web search skipped.",
            "results": [],
            "suggested_manual_search_queries": queries,
        }

    results = []
    for query in queries:
        results.extend(web_search(query, num_results=4))

    return {
        "available": True,
        "results": results,
        "suggested_manual_search_queries": queries,
        "error": None,
    }
