from __future__ import annotations

import re
from urllib.parse import urljoin

import requests

from contact_discovery import extract_phone_numbers, extract_whatsapp_links


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _soup(html: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser")


def extract_basic_seo(html: str, url: str) -> dict:
    soup = _soup(html)
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    h1 = soup.find("h1")
    h2s = [h2.get_text(" ", strip=True) for h2 in soup.find_all("h2")[:10]]
    return {
        "page_title": title,
        "meta_description": meta.get("content", "").strip() if meta else "",
        "h1_text": h1.get_text(" ", strip=True) if h1 else "",
        "h2_texts": h2s,
        "source_url": url,
    }


def extract_visible_contact_signals(html: str) -> dict:
    soup = _soup(html)
    text = soup.get_text(" ", strip=True)
    links = [a.get("href", "") for a in soup.find_all("a")]
    joined_links = " ".join(links)
    return {
        "visible_phone_numbers": extract_phone_numbers(f"{text} {joined_links}"),
        "whatsapp_links": extract_whatsapp_links(" ".join(links + [html])),
        "email_addresses": sorted(set(EMAIL_RE.findall(f"{text} {joined_links}"))),
        "tel_links": [href for href in links if href.lower().startswith("tel:")],
        "mailto_links": [href for href in links if href.lower().startswith("mailto:")],
    }


def extract_social_links(html: str) -> dict:
    soup = _soup(html)
    instagram = []
    facebook = []
    contact_pages = []
    booking_links = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True).lower()
        lower = href.lower()
        if "instagram.com" in lower:
            instagram.append(href)
        if "facebook.com" in lower or "fb.com" in lower:
            facebook.append(href)
        if "contact" in lower or "contact" in text:
            contact_pages.append(href)
        if any(word in lower or word in text for word in ("book", "appointment", "reservation")):
            booking_links.append(href)
    return {
        "instagram_links": sorted(set(instagram)),
        "facebook_links": sorted(set(facebook)),
        "contact_page_links": sorted(set(contact_pages)),
        "booking_links": sorted(set(booking_links)),
    }


def fetch_website_snapshot(url: str) -> dict:
    if not url:
        return {"error": "No website URL provided."}

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "MonkAudit/3.0 (+internal research)"},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"source_url": url, "error": f"Website snapshot failed: {exc}"}

    html = response.text
    try:
        seo = extract_basic_seo(html, response.url)
        contact = extract_visible_contact_signals(html)
        socials = extract_social_links(html)
    except Exception as exc:
        return {"final_url": response.url, "source_url": url, "error": f"Website snapshot parsing failed: {exc}"}

    def absolute_list(values: list[str]) -> list[str]:
        return [urljoin(response.url, value) for value in values if value]

    socials["contact_page_links"] = absolute_list(socials["contact_page_links"])
    socials["booking_links"] = absolute_list(socials["booking_links"])

    return {
        "final_url": response.url,
        **seo,
        **contact,
        **socials,
        "error": None,
    }
