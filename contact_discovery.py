from __future__ import annotations

import re
from urllib.parse import parse_qs, quote_plus, urlparse


PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
WHATSAPP_RE = re.compile(r"https?://(?:wa\.me|api\.whatsapp\.com|web\.whatsapp\.com)/[^\s)>\"]+", re.I)


def extract_phone_numbers(text: str) -> list[str]:
    found = []
    for match in PHONE_RE.findall(text or ""):
        cleaned = re.sub(r"\s+", " ", match).strip(" .,-")
        if cleaned not in found:
            found.append(cleaned)
    return found


def extract_whatsapp_links(text: str) -> list[str]:
    links = []
    for match in WHATSAPP_RE.findall(text or ""):
        normalized = normalize_whatsapp_url(match)
        if normalized and normalized not in links:
            links.append(normalized)
    return links


def normalize_whatsapp_url(url: str, default_country_code: str = "91") -> str | None:
    value = (url or "").strip().rstrip(".,)")
    if not value:
        return None
    parsed = urlparse(value)
    host = parsed.netloc.lower().replace("www.", "")
    if host == "wa.me":
        phone = parsed.path.strip("/")
    elif host in {"api.whatsapp.com", "web.whatsapp.com"}:
        query_phone = parse_qs(parsed.query).get("phone", [""])[0]
        phone = query_phone or parsed.path.strip("/")
    else:
        return None
    normalized = normalize_phone_number(phone, default_country_code)
    return f"https://wa.me/{normalized}" if normalized else None


def normalize_phone_number(phone: str, default_country_code: str = "91") -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None

    if default_country_code == "91":
        if digits.startswith("0091"):
            digits = digits[2:]
        if digits.startswith("091") and len(digits) == 13:
            digits = digits[1:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10 and digits[0] in "6789":
            digits = f"91{digits}"
        if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
            return digits
        return None

    if len(digits) == 10:
        digits = f"{default_country_code}{digits}"
    if len(digits) < 10 or digits.startswith("0"):
        return None
    return digits


def build_whatsapp_link(phone: str, message: str = "") -> str | None:
    normalized = normalize_phone_number(phone)
    if not normalized:
        return None
    suffix = f"?text={quote_plus(message)}" if message else ""
    return f"https://wa.me/{normalized}{suffix}"


def merge_contact_sources(
    places_data: dict,
    web_research: dict,
    website_snapshot: dict | None = None,
    default_country_code: str = "91",
) -> dict:
    google_phone = places_data.get("phone_number")
    google_international = places_data.get("international_phone_number")
    text_blob = " ".join(
        " ".join(str(result.get(key, "")) for key in ("title", "link", "snippet"))
        for result in web_research.get("results", [])
    )
    if website_snapshot:
        text_blob = " ".join(
            [
                text_blob,
                " ".join(website_snapshot.get("visible_phone_numbers", [])),
                " ".join(website_snapshot.get("whatsapp_links", [])),
                " ".join(website_snapshot.get("tel_links", [])),
            ]
        )

    phones_from_web = extract_phone_numbers(text_blob)
    whatsapp_links = extract_whatsapp_links(text_blob)
    if website_snapshot:
        whatsapp_links.extend(
            link for link in website_snapshot.get("whatsapp_links", []) if link not in whatsapp_links
        )
    all_phones = [phone for phone in [google_phone, google_international, *phones_from_web] if phone]
    possible_links = []
    for phone in all_phones:
        normalized = normalize_phone_number(phone, default_country_code)
        link = f"https://wa.me/{normalized}" if normalized else None
        if link and link not in possible_links:
            possible_links.append(link)

    google_normalized = normalize_phone_number(google_international or google_phone or "", default_country_code)
    web_normalized = {normalize_phone_number(phone, default_country_code) for phone in phones_from_web}
    web_normalized.discard(None)

    if google_normalized and google_normalized in web_normalized:
        confidence = "high"
    elif google_phone or google_international or phones_from_web:
        confidence = "medium"
    else:
        confidence = "low"

    sources = []
    if google_phone or google_international:
        sources.append("google_places")
    if phones_from_web or whatsapp_links:
        sources.append("web_snippets")

    return {
        "google_phone": google_phone,
        "google_international_phone": google_international,
        "phones_from_web": phones_from_web,
        "whatsapp_links_from_web": whatsapp_links,
        "verified_whatsapp_links": whatsapp_links,
        "possible_whatsapp_links_from_phone_numbers": [
            {"link": link, "label": "possible WhatsApp link - needs manual verification"}
            for link in possible_links
        ],
        "confidence": confidence,
        "sources": sources,
        "note": "Phone numbers are not claimed as WhatsApp unless a public WhatsApp link was found. Possible links are only outreach conveniences to verify manually.",
    }
