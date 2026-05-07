from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from io import BytesIO
from datetime import datetime, timezone
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile
from urllib.parse import parse_qs, urlparse

import streamlit as st
import google.auth
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from analytics_ga4 import get_ga4_summary
from auth import require_login
from competitor_analysis import analyze_competitors
from contact_discovery import merge_contact_sources
from llm import generate_text
from pagespeed import get_pagespeed_summary
from pdf_generator import generate_audit_pdf
from places import find_nearby_competitors, get_place_details, infer_niche_from_place, resolve_business_identity
from prompts import (
    build_audit_prompt,
    build_client_due_diligence_prompt,
    build_internal_sales_diligence_prompt,
    build_sales_call_brief_prompt,
)
from research import research_business_public_presence
from search_console import get_search_console_summary
from source_utils import dedupe_sources, make_source
from sales_ops import DEFAULT_OWNER, LEAD_STATUSES, list_audit_records, save_audit_record, update_audit_record
from website_research import fetch_website_snapshot


APP_VERSION = "v3"
QUICK_MODE = "Quick Audit Mode"
DEEP_MODE = "Deep Research Mode"
CLIENT_REPORT_FILE_LABEL = "Client_Growth_Due_Diligence_Report"
INTERNAL_REPORT_FILE_LABEL = "Internal_Sales_Diligence_Report"
SALES_BRIEF_FILE_LABEL = "Internal_Sales_Call_Brief"
SALES_PACK_FILE_LABEL = "GrowingMonk_Sales_Enablement_Pack"
CUSTOMER_PACK_FILE_LABEL = "GrowingMonk_Client_Share_Pack"
RESEARCH_JSON_FILE_LABEL = "Verified_Research_Evidence_File"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
CLIENT_SAFE_REVIEW_LABEL = (
    "I reviewed the client-facing report and confirmed it is safe to share externally."
)


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets[name]
    except (FileNotFoundError, KeyError):
        value = os.getenv(name, default)
    return str(value or default).strip()


def safe_filename(name: str, suffix: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return f"{cleaned or 'Prospect'}_MonkAudit.{suffix}"


def safe_named_file(name: str, label: str, suffix: str) -> str:
    cleaned_name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "Prospect"
    cleaned_label = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_") or "MonkAudit"
    return f"{cleaned_name}_{cleaned_label}.{suffix}"


def report_file_name(name: str, report_label: str, suffix: str) -> str:
    cleaned_name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "Business"
    return f"{cleaned_name}_{report_label}.{suffix}"


def safe_folder_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return cleaned or "Prospect"


def add_download_button(label: str, data: Any, file_name: str, mime: str, **kwargs: Any) -> bool:
    return st.download_button(
        label,
        data=data,
        file_name=file_name,
        mime=mime,
        on_click="ignore",
        **kwargs,
    )


def build_zip(files: dict[str, bytes | str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            if isinstance(content, str):
                archive.writestr(file_name, content.encode("utf-8"))
            else:
                archive.writestr(file_name, content)
    return buffer.getvalue()


def get_drive_service() -> Any:
    credentials, _ = google.auth.default(scopes=[DRIVE_SCOPE])
    if not credentials.valid and credentials.refresh_token:
        credentials.refresh(Request())
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def escape_drive_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_drive_folder_by_name(service: Any, folder_name: str) -> str:
    if not folder_name:
        return ""
    escaped_name = escape_drive_query_value(folder_name)
    result = (
        service.files()
        .list(
            q=(
                "mimeType = 'application/vnd.google-apps.folder' "
                f"and name = '{escaped_name}' and trashed = false"
            ),
            fields="files(id, name)",
            pageSize=10,
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0]["id"] if files else ""


def create_drive_folder(service: Any, folder_name: str, parent_id: str = "") -> str:
    metadata: dict[str, Any] = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def resolve_drive_parent_folder(service: Any, folder_input: str) -> tuple[str, str]:
    raw = (folder_input or "").strip()
    if not raw:
        return "", "My Drive"
    folder_id = extract_drive_folder_id(raw)
    if "drive.google.com" in raw:
        return folder_id, folder_id

    folder_by_name = find_drive_folder_by_name(service, raw)
    if folder_by_name:
        return folder_by_name, raw
    if len(raw) < 10:
        raise ValueError(
            f"Drive folder '{raw}' was not found by name. Paste the full folder URL or use the long folder ID."
        )
    return folder_id, folder_id


def build_drive_client_folder_name(business_name: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"{safe_folder_name(business_name)}_{timestamp}"


def upload_file_to_drive(
    file_name: str,
    payload: bytes,
    mime_type: str,
    folder_id: str = "",
    share_anyone_with_link: bool = False,
    client_folder_name: str = "",
) -> str:
    service = get_drive_service()
    parent_id, _ = resolve_drive_parent_folder(service, folder_id)
    upload_parent_id = parent_id
    if client_folder_name:
        upload_parent_id = create_drive_folder(service, client_folder_name, parent_id)
    metadata: dict[str, Any] = {"name": file_name}
    if upload_parent_id:
        metadata["parents"] = [upload_parent_id]
    media = MediaIoBaseUpload(BytesIO(payload), mimetype=mime_type, resumable=False)
    uploaded = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink",
        )
        .execute()
    )
    if share_anyone_with_link:
        service.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()
    return uploaded.get("webViewLink") or f"https://drive.google.com/file/d/{uploaded.get('id')}/view"


def extract_drive_folder_id(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "drive.google.com" not in raw:
        return raw

    parsed = urlparse(raw)
    folder_match = re.search(r"/folders/([^/?#]+)", parsed.path)
    if folder_match:
        return folder_match.group(1)
    query_id = parse_qs(parsed.query).get("id", [""])[0]
    return query_id.strip()


def validate_drive_folder_id(folder_id: str) -> str:
    if not folder_id:
        return ""
    if len(folder_id) < 10 or not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
        return (
            "Enter a real Google Drive folder ID or paste the full folder URL. "
            "Folder names like 'JH' will not work."
        )
    return ""


def drive_error_help(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, ValueError):
        return message
    if isinstance(exc, HttpError) and "accessNotConfigured" in message:
        return (
            "Google Drive API is disabled for the active Google Cloud project. Enable it here:\n\n"
            "https://console.developers.google.com/apis/api/drive.googleapis.com/overview\n\n"
            "Or run:\n\n"
            "gcloud services enable drive.googleapis.com\n\n"
            "After enabling, wait a few minutes and retry the upload. If it still fails, restart Streamlit."
        )
    if isinstance(exc, HttpError) and exc.resp.status == 403 and "insufficient" in message.lower():
        return (
            "Google Drive credentials are missing the Drive upload scope. Run this once in your terminal, "
            "then restart Streamlit:\n\n"
            "gcloud auth application-default login "
            '--scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.file"\n\n'
            "If you also use GA4/Search Console, include those scopes in the same command."
        )
    if isinstance(exc, HttpError) and exc.resp.status == 404:
        return (
            "The Drive folder ID was not found or this Google account does not have access to that folder. "
            "Paste the full Google Drive folder URL, or copy the long ID after /folders/ in the URL. "
            "Do not enter the folder name."
        )
    if isinstance(exc, HttpError) and exc.resp.status == 401:
        return "Google credentials are expired or unavailable. Re-run gcloud auth application-default login and restart Streamlit."
    return "Check Google Drive API enablement, ADC credentials, folder access, and the selected sharing option."


def smtp_configured() -> bool:
    return bool(get_secret("SMTP_HOST") and get_secret("SMTP_USER") and get_secret("SMTP_PASSWORD"))


def smtp_missing_settings() -> list[str]:
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"]
    missing = [name for name in required if not get_secret(name)]
    if not get_secret("SMTP_FROM") and not get_secret("SMTP_USER"):
        missing.append("SMTP_FROM")
    return missing


def smtp_security_mode(port: int) -> str:
    configured = get_secret("SMTP_SECURITY", "").lower()
    if configured in {"starttls", "ssl", "none"}:
        return configured
    return "ssl" if port == 465 else "starttls"


def send_email_with_attachment(
    recipient: str,
    subject: str,
    body: str,
    attachment_name: str,
    attachment_bytes: bytes,
    attachment_mime: str = "application/zip",
) -> None:
    smtp_host = get_secret("SMTP_HOST")
    smtp_port = int(get_secret("SMTP_PORT", "587") or "587")
    smtp_user = get_secret("SMTP_USER")
    smtp_password = get_secret("SMTP_PASSWORD")
    sender = get_secret("SMTP_FROM", smtp_user)
    if not smtp_host or not smtp_user or not smtp_password or not sender:
        raise RuntimeError("SMTP is not configured. Add SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    maintype, subtype = attachment_mime.split("/", 1)
    message.add_attachment(
        attachment_bytes,
        maintype=maintype,
        subtype=subtype,
        filename=attachment_name,
    )

    context = ssl.create_default_context()
    security_mode = smtp_security_mode(smtp_port)
    if security_mode == "ssl":
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        if security_mode == "starttls":
            server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def normalize_url(url: str) -> str:
    value = url.strip()
    if value and not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def collect_form_data(mode: str) -> dict[str, Any]:
    niche_options = [
        "",
        "Salon / Beauty",
        "Restaurant / Cafe",
        "Local Service",
        "Clinic / Wellness",
        "Gym / Fitness",
        "Coach / Consultant",
        "Ecommerce / D2C",
        "Franchise / Multi-location",
        "Other",
    ]
    business_structure_options = [
        "Single location/store",
        "Local brand with multiple locations",
        "Regional master franchise",
        "Franchise location",
        "Online-first brand",
        "Other / unsure",
    ]

    with st.form("prospect_form"):
        st.info("Leave optional fields blank. MonkAudit will try to discover public business data automatically.")
        st.subheader("Required identification")
        col_1, col_2 = st.columns(2)
        with col_1:
            business_name = st.text_input("Business name *")
            business_structure = st.selectbox("Business structure *", business_structure_options)
        with col_2:
            location = st.text_input("City / Country or area *", placeholder="MVP Colony, Visakhapatnam")

        st.subheader("Optional overrides")
        col_1, col_2 = st.columns(2)
        with col_1:
            gbp_link = st.text_input("Google Maps / GBP link, optional")
            niche = st.selectbox("Selected niche, optional", niche_options)
            website_url = st.text_input("Website URL override, optional", placeholder="https://example.com")
            instagram_handle = st.text_input("Instagram override, optional")
        with col_2:
            pagespeed_strategy = st.radio("PageSpeed strategy", ["mobile", "desktop"], horizontal=True)
            main_offer = st.text_input("Main offer / notes")
            target_audience = st.text_input("Target audience notes")
            whatsapp_contact = st.text_input("Contact override, optional")

        with st.expander("Additional optional notes"):
            known_competitors = st.text_area("Known competitors")
            current_problem = st.text_area("Current problem the business may have")
            existing_ad_activity = st.text_area("Existing ad activity, if known")
            strategist_notes = st.text_area("Notes from strategist")

        submitted = st.form_submit_button(
            "Generate Deep Research Reports" if mode == DEEP_MODE else "Generate Mini Audit",
            type="primary",
        )

    return {
        "submitted": submitted,
        "business_name": business_name.strip(),
        "business_structure": business_structure,
        "website_url": normalize_url(website_url),
        "niche": niche,
        "location": location.strip(),
        "pagespeed_strategy": pagespeed_strategy,
        "gbp_link": gbp_link.strip(),
        "instagram_handle": instagram_handle.strip(),
        "main_offer": main_offer.strip(),
        "target_audience": target_audience.strip(),
        "known_competitors": known_competitors.strip(),
        "strategist_notes": strategist_notes.strip(),
        "current_problem": current_problem.strip(),
        "existing_ad_activity": existing_ad_activity.strip(),
        "whatsapp_contact": whatsapp_contact.strip(),
    }


def validate_required_fields(data: dict[str, Any], require_website: bool = True) -> list[str]:
    missing = []
    for field, label in {
        "business_name": "Business name",
        "location": "City / Country",
    }.items():
        if not data.get(field):
            missing.append(label)
    if require_website and not data.get("website_url"):
        missing.append("Website URL")
    return missing


def build_manual_overrides(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_structure": data.get("business_structure"),
        "website": data.get("website_url"),
        "instagram": data.get("instagram_handle"),
        "selected_niche": data.get("niche"),
        "main_offer": data.get("main_offer"),
        "target_audience": data.get("target_audience"),
        "contact": data.get("whatsapp_contact"),
        "google_maps_link": data.get("gbp_link"),
        "known_competitors": data.get("known_competitors"),
        "strategist_notes": data.get("strategist_notes"),
        "current_problem": data.get("current_problem"),
        "existing_ad_activity": data.get("existing_ad_activity"),
    }


def _first_or_empty(values: list[str] | None) -> str:
    return values[0] if values else ""


def discover_instagram(data: dict[str, Any], website_snapshot: dict[str, Any], web_research: dict[str, Any]) -> dict[str, Any]:
    if data.get("instagram_handle"):
        return {"selected": data["instagram_handle"], "source": "manual_override", "candidates": [], "confidence": "manual"}

    candidates = list(website_snapshot.get("instagram_links", []) or [])
    for result in web_research.get("results", []):
        link = result.get("link", "")
        if "instagram.com" in link and link not in candidates:
            candidates.append(link)

    business_name = data.get("business_name", "").lower().replace(" ", "")
    confidence = "low"
    if candidates:
        normalized = candidates[0].lower().replace("_", "").replace(".", "")
        confidence = "high" if business_name and business_name in normalized else "medium"

    return {"selected": _first_or_empty(candidates), "source": "public_discovery", "candidates": candidates, "confidence": confidence}


def build_final_data_used(
    data: dict[str, Any],
    business: dict[str, Any],
    website: str,
    effective_niche: str,
    instagram: dict[str, Any],
    contact: dict[str, Any],
) -> dict[str, Any]:
    return {
        "business_name": business.get("name") or data.get("business_name"),
        "input_business_name": data.get("business_name"),
        "business_structure": data.get("business_structure"),
        "location": data.get("location"),
        "effective_niche": effective_niche,
        "manual_selected_niche": data.get("niche"),
        "address": business.get("formatted_address"),
        "phone": data.get("whatsapp_contact") or business.get("international_phone_number") or business.get("phone_number"),
        "website": data.get("website_url") or website,
        "instagram": data.get("instagram_handle") or instagram.get("selected"),
        "google_maps_url": data.get("gbp_link") or business.get("google_maps_url"),
        "rating": business.get("rating"),
        "review_count": business.get("user_ratings_total"),
        "contact_override_used": bool(data.get("whatsapp_contact")),
        "website_override_used": bool(data.get("website_url")),
        "instagram_override_used": bool(data.get("instagram_handle")),
        "verified_whatsapp_links": contact.get("verified_whatsapp_links", []),
        "possible_whatsapp_links_from_phone_numbers": contact.get("possible_whatsapp_links_from_phone_numbers", []),
    }


def infer_website_from_web_research(web_research: dict[str, Any], business_name: str) -> str:
    skip_domains = ("instagram.com", "facebook.com", "justdial.com", "sulekha.com", "zomato.com", "swiggy.com", "practo.com")
    name_tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", business_name) if len(token) > 2]
    for result in web_research.get("results", []):
        link = result.get("link", "")
        lower_link = link.lower()
        if not link or any(domain in lower_link for domain in skip_domains):
            continue
        if not name_tokens or any(token in lower_link for token in name_tokens):
            return normalize_url(link)
    return ""


def extract_section(markdown: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*(.*?)(?=\n##\s+|\Z)"
    match = re.search(pattern, markdown, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def build_download_payload(data: dict[str, Any], pagespeed: dict[str, Any], audit: str) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prospect": {key: value for key, value in data.items() if key != "submitted"},
        "pagespeed": pagespeed,
        "audit_markdown": audit,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_research_payload(
    data: dict[str, Any],
    research_data: dict[str, Any],
    client_report: str = "",
    internal_report: str = "",
    sales_brief: str = "",
) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prospect": {key: value for key, value in data.items() if key != "submitted"},
        "research": research_data,
        "client_due_diligence_markdown": client_report,
        "internal_sales_diligence_markdown": internal_report,
        "sales_brief_markdown": sales_brief,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def clean_generated_report(markdown: str, client_safe: bool = False) -> str:
    cleaned = markdown or ""
    replacements = {
        "Missing Data": "Data Requiring Client Access / Confirmation",
        "missing data": "data requiring client access / confirmation",
        "Website appears to lack": "Our lightweight website snapshot did not detect",
        "website appears to lack": "our lightweight website snapshot did not detect",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    cleaned = re.sub(
        r"https?://(?:www\.)?wa\.me/0+\d+",
        "possible WhatsApp link removed - needs manual verification",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(Our lightweight website snapshot did not detect[^.\n]*\.)",
        r"\1 This should be verified with a deeper website review.",
        cleaned,
    )
    cleaned = re.sub(r"(?<![A-Za-z])e\.me\b", "WhatsApp link text removed - needs manual verification", cleaned)
    cleaned = re.sub(r"https?://(?:www\.)?wa\.me/(\d{1,11})(?!\d)", "possible WhatsApp link removed - needs manual verification", cleaned)

    if client_safe:
        guardrail_replacements = {
            "Your competitors are beating you": "Some nearby businesses appear to have stronger public visibility signals",
            "your competitors are beating you": "some nearby businesses appear to have stronger public visibility signals",
            "You are losing customers": "This may influence customer trust during quick comparisons",
            "you are losing customers": "this may influence customer trust during quick comparisons",
            "You are behind": "There is an opportunity to strengthen visibility",
            "you are behind": "there is an opportunity to strengthen visibility",
            "Significantly boost": "Can help improve",
            "significantly boost": "can help improve",
            "Guaranteed": "Potential",
            "guaranteed": "potential",
            "capture a larger share": "improve visibility with relevant prospects",
        }
        for old, new in guardrail_replacements.items():
            cleaned = cleaned.replace(old, new)

    return cleaned


def confidence_label(research_data: dict[str, Any]) -> str:
    business = research_data.get("business", {})
    final_data = research_data.get("final_data_used", {})
    pagespeed = research_data.get("pagespeed", {})
    website_snapshot = research_data.get("website_snapshot", {})
    competitors = research_data.get("competitors", [])

    has_places = bool(business.get("place_id") or business.get("google_maps_url"))
    has_website = bool(final_data.get("website") and not website_snapshot.get("error"))
    has_pagespeed = bool(pagespeed and not pagespeed.get("error"))
    has_competitors = bool([competitor for competitor in competitors if not competitor.get("error")])

    score = sum([has_places, has_website, has_pagespeed, has_competitors])
    if score >= 3:
        return "High"
    if score == 2:
        return "Medium"
    return "Low"


def recommended_offer(research_data: dict[str, Any]) -> str:
    pagespeed = research_data.get("pagespeed", {})
    final_data = research_data.get("final_data_used", {})
    structure = final_data.get("business_structure") or ""
    analytics = research_data.get("analytics_access", {})
    contact = research_data.get("contact_discovery", {})
    review_position = research_data.get("competitor_analysis", {}).get("review_position", {})

    tracking_available = analytics.get("ga4", {}).get("available") or analytics.get("search_console", {}).get("available")
    has_contact_signal = bool(
        final_data.get("phone")
        or contact.get("emails")
        or contact.get("verified_whatsapp_links")
        or contact.get("possible_whatsapp_links_from_phone_numbers")
    )
    performance_score = _number(pagespeed.get("performance_score"))
    review_gap = _number(review_position.get("review_volume_gap_vs_top"))

    if structure in {"Regional master franchise", "Local brand with multiple locations"}:
        return "Monthly Growth System"
    if not tracking_available:
        return "Tracking Setup First"
    if not has_contact_signal or (performance_score is not None and performance_score < 55):
        return "30-Day Growth Sprint"
    if review_gap is not None and review_gap > 50:
        return "30-Day Growth Sprint"
    return "Monthly Growth System"


def extract_main_pitch_angle(internal_report: str, sales_brief: str = "") -> str:
    for markdown, heading in (
        (sales_brief, "Main Pitch Angle"),
        (internal_report, "10. Main Sales Pitch Angle"),
        (internal_report, "Main Sales Pitch Angle"),
    ):
        section = extract_section(markdown, heading)
        if section:
            return section.splitlines()[0].strip("- ").strip()
    return "Use the verified public data to open a practical growth-systems conversation."


def build_sales_action_card(
    research_data: dict[str, Any],
    internal_report: str,
    sales_brief: str,
) -> dict[str, Any]:
    final_data = research_data.get("final_data_used", {})
    business_name = final_data.get("business_name") or research_data.get("prospect", {}).get("business_name") or "Prospect"
    confidence = confidence_label(research_data)
    offer = recommended_offer(research_data)
    pitch = extract_main_pitch_angle(internal_report, sales_brief)
    outreach = extract_section(internal_report, "11. Outreach Messages")
    questions = extract_section(sales_brief, "5 Smart Questions to Ask the Owner") or extract_section(
        internal_report,
        "12. Sales Call Questions",
    )
    cautions = extract_section(sales_brief, "What Not To Claim Yet") or extract_section(
        internal_report,
        "15. Proof Needed Before Claims",
    )

    return {
        "business_name": business_name,
        "business_structure": final_data.get("business_structure") or "Single location/store",
        "confidence_label": confidence,
        "recommended_offer": offer,
        "pitch_angle": pitch,
        "best_channel": best_outreach_channel(research_data),
        "outreach": outreach.strip(),
        "questions": first_markdown_items(questions, limit=3),
        "cautions": first_markdown_items(cautions, limit=3),
    }


def best_outreach_channel(research_data: dict[str, Any]) -> str:
    final_data = research_data.get("final_data_used", {})
    contact = research_data.get("contact_discovery", {})
    instagram = research_data.get("social_discovery", {}).get("instagram", {})
    if contact.get("verified_whatsapp_links"):
        return "WhatsApp"
    if final_data.get("instagram") or instagram.get("selected"):
        return "Instagram DM"
    if contact.get("emails"):
        return "Email"
    if final_data.get("phone"):
        return "Phone call"
    return "Manual research needed"


def first_markdown_items(markdown: str, limit: int = 3) -> list[str]:
    items: list[str] = []
    for line in markdown.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^[-*\d.\s]+", "", cleaned).strip()
        if cleaned:
            items.append(cleaned)
        if len(items) >= limit:
            break
    return items


def save_generated_audit_record(
    mode: str,
    data: dict[str, Any],
    research_data: dict[str, Any] | None = None,
    client_report: str = "",
    internal_report: str = "",
    sales_brief: str = "",
    quick_audit: str = "",
    pagespeed: dict[str, Any] | None = None,
) -> str:
    research_data = research_data or {}
    final_data = research_data.get("final_data_used", {})
    action_card = build_sales_action_card(research_data, internal_report, sales_brief) if research_data else {}
    website = final_data.get("website") or data.get("website_url") or ""
    payload = {
        "prospect": {key: value for key, value in data.items() if key != "submitted"},
        "research_data": research_data,
        "client_report": client_report,
        "internal_report": internal_report,
        "sales_brief": sales_brief,
        "quick_audit": quick_audit,
        "pagespeed": pagespeed or {},
        "sales_action_card": action_card,
    }
    return save_audit_record(
        {
            "mode": mode,
            "business_name": final_data.get("business_name") or data.get("business_name") or "Unknown business",
            "location": data.get("location", ""),
            "website": website,
            "niche": " | ".join(
                value
                for value in (
                    final_data.get("effective_niche") or data.get("niche", ""),
                    final_data.get("business_structure") or data.get("business_structure", ""),
                )
                if value
            ),
            "status": "Audited",
            "owner": DEFAULT_OWNER,
            "confidence_label": action_card.get("confidence_label") or ("Medium" if quick_audit else ""),
            "recommended_offer": action_card.get("recommended_offer") or "",
            "pitch_angle": action_card.get("pitch_angle") or "",
            "next_step": "Review report and contact prospect.",
            "payload": payload,
        }
    )


def render_sales_action_card(
    research_data: dict[str, Any],
    internal_report: str,
    sales_brief: str,
) -> dict[str, Any]:
    action_card = build_sales_action_card(research_data, internal_report, sales_brief)
    st.subheader("Sales Action Card")
    col_1, col_2, col_3 = st.columns(3)
    col_1.metric("Source confidence", action_card["confidence_label"])
    col_2.metric("Best channel", action_card["best_channel"])
    col_3.metric("Recommended offer", action_card["recommended_offer"])
    st.write(f"**Business structure:** {action_card['business_structure']}")
    st.write(f"**Main pitch angle:** {action_card['pitch_angle']}")
    if action_card["questions"]:
        st.write("**Ask on the call:**")
        for question in action_card["questions"]:
            st.write(f"- {question}")
    if action_card["cautions"]:
        st.write("**Do not claim yet:**")
        for caution in action_card["cautions"]:
            st.write(f"- {caution}")
    if action_card["outreach"]:
        st.text_area("Copy first outreach block", action_card["outreach"], height=220)
    return action_card


def render_pipeline_dashboard() -> None:
    records = list_audit_records(limit=100)
    with st.expander("Lead Pipeline & Audit History", expanded=False):
        if not records:
            st.info("No saved audits yet. Generated audits will appear here automatically.")
            return

        status_counts = {status: 0 for status in LEAD_STATUSES}
        for record in records:
            status_counts[record.get("status", "New")] = status_counts.get(record.get("status", "New"), 0) + 1
        metric_cols = st.columns(min(4, len(LEAD_STATUSES)))
        for index, status in enumerate(("Audited", "Contacted", "Replied", "Call Booked")):
            metric_cols[index].metric(status, status_counts.get(status, 0))

        table_rows = [
            {
                "Created": record.get("created_at", "")[:10],
                "Business": record.get("business_name"),
                "Status": record.get("status"),
                "Confidence": record.get("confidence_label"),
                "Offer": record.get("recommended_offer"),
                "Reviewed": "Yes" if record.get("client_reviewed") else "No",
                "Next step": record.get("next_step"),
            }
            for record in records
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        labels = [
            f"{record['created_at'][:10]} | {record['business_name']} | {record['status']}"
            for record in records
        ]
        selected_label = st.selectbox("Update lead", labels, key="pipeline_selected_record")
        selected_record = records[labels.index(selected_label)]
        with st.form(f"pipeline_update_{selected_record['id']}"):
            new_status = st.selectbox(
                "Lead status",
                LEAD_STATUSES,
                index=LEAD_STATUSES.index(selected_record.get("status", "Audited"))
                if selected_record.get("status") in LEAD_STATUSES
                else 1,
            )
            owner = st.text_input("Owner", value=selected_record.get("owner") or DEFAULT_OWNER)
            next_step = st.text_input("Next step", value=selected_record.get("next_step") or "")
            notes = st.text_area("Notes", value=selected_record.get("notes") or "", height=90)
            reviewed = st.checkbox("Client-safe report reviewed", value=bool(selected_record.get("client_reviewed")))
            submitted = st.form_submit_button("Save lead update")
        if submitted:
            update_audit_record(
                selected_record["id"],
                status=new_status,
                owner=owner.strip() or DEFAULT_OWNER,
                next_step=next_step.strip(),
                notes=notes.strip(),
                client_reviewed=reviewed,
            )
            st.success("Lead updated.")
            st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### MonkAudit")
        st.caption("Internal GrowingMonk prospect audit assistant.")
        st.divider()
        render_pipeline_dashboard()
        st.divider()
        st.markdown("**Tool notes**")
        st.write("Use this for fast prospect research, outreach prep, and sales call framing.")
        st.write("Review the output before sending anything externally.")
        st.divider()
        st.caption(f"Version {APP_VERSION}")


def render_results(data: dict[str, Any], pagespeed: dict[str, Any], audit: str) -> None:
    outreach = extract_section(audit, "5. Suggested Outreach Message")
    sales_notes = extract_section(audit, "6. Sales Call Talking Points")

    tab_audit, tab_outreach, tab_sales, tab_pagespeed = st.tabs(
        ["Audit", "Outreach", "Sales Notes", "Raw PageSpeed"]
    )

    with tab_audit:
        col_md, col_pdf = st.columns(2)
        with col_md:
            add_download_button(
                "Download audit as Markdown",
                data=audit,
                file_name=safe_named_file(data["business_name"], "MonkAudit", "md"),
                mime="text/markdown",
            )
        with col_pdf:
            try:
                pdf_bytes = generate_audit_pdf(audit, data["business_name"], "MonkAudit Report")
                add_download_button(
                    "Download audit as PDF",
                    data=pdf_bytes,
                    file_name=safe_named_file(data["business_name"], "MonkAudit", "pdf"),
                    mime="application/pdf",
                )
            except Exception as exc:
                st.warning(f"PDF generation failed. Markdown download is still available. {exc}")
        st.markdown(audit)

    with tab_outreach:
        if outreach:
            st.text_area("Copy outreach message", outreach, height=220)
        else:
            st.info("The outreach section could not be extracted cleanly. Use the full audit tab.")

    with tab_sales:
        if sales_notes:
            st.markdown(sales_notes)
        else:
            st.info("The sales notes section could not be extracted cleanly. Use the full audit tab.")

    with tab_pagespeed:
        st.json(pagespeed)

    add_download_button(
        "Download prospect data as JSON",
        data=build_download_payload(data, pagespeed, audit),
        file_name=safe_filename(data["business_name"], "json"),
        mime="application/json",
    )


def run_quick_audit(data: dict[str, Any]) -> None:
    missing = validate_required_fields(data, require_website=False)
    if missing:
        st.error(f"Please complete required fields: {', '.join(missing)}.")
        return

    with st.spinner("Checking PageSpeed and preparing the audit..."):
        discovered = {}
        website = data.get("website_url")
        if not website:
            identity = resolve_business_identity(data["business_name"], data["location"], data.get("gbp_link", ""))
            discovered = identity.get("selected_place", {}) if not identity.get("error") else identity
            website = normalize_url(str(discovered.get("website") or ""))
        pagespeed = (
            get_pagespeed_summary(website, data["pagespeed_strategy"])
            if website
            else {"error": "Website was not provided or discovered."}
        )
        quick_data = {**data, "website_url": website, "discovered_data": discovered}
        prompt = build_audit_prompt(quick_data, pagespeed)

    system_instruction = """
You are a senior marketing strategist for GrowingMonk.
GrowingMonk is a growth systems agency for local, service, and ecommerce businesses.

Be practical, specific, honest, and business-focused.
Do not invent facts.
Use careful language when data is incomplete.
Focus on local visibility, Instagram Reels, WhatsApp/contact flow, offers, tracking, and conversion.
Avoid hype, fake claims, unsupported numbers, and generic agency language.
""".strip()

    try:
        with st.spinner("Generating the mini growth audit..."):
            audit = generate_text(prompt, system_instruction=system_instruction)
    except Exception as exc:
        st.error(f"Gemini generation failed: {exc}")
        st.subheader("PageSpeed Summary")
        st.json(pagespeed)
        return

    st.success("Audit generated.")
    audit_record_id = save_generated_audit_record(
        mode=QUICK_MODE,
        data={**data, "website_url": quick_data.get("website_url", "")},
        quick_audit=audit,
        pagespeed=pagespeed,
    )
    st.session_state["last_quick_results"] = {
        "data": data,
        "pagespeed": pagespeed,
        "audit": audit,
        "audit_record_id": audit_record_id,
    }
    render_results(data, pagespeed, audit)


def _website_for_pagespeed(data: dict[str, Any], business: dict[str, Any]) -> str:
    return data.get("website_url") or normalize_url(str(business.get("website") or ""))


def _record_source(research_data: dict[str, Any], title: str, url: str, source_type: str, snippet: str = "") -> None:
    research_data.setdefault("sources", []).append(make_source(title, url, source_type, snippet))
    research_data["sources"] = dedupe_sources(research_data["sources"])


def run_deep_research(data: dict[str, Any], should_run_research: bool, client_options: dict[str, Any]) -> None:
    missing = validate_required_fields(data, require_website=False)
    if missing:
        st.error(f"Please complete required fields: {', '.join(missing)}.")
        return
    if not should_run_research:
        st.info(
            "Check 'Run Deep Research' to use Places, PageSpeed, contact discovery, "
            "competitor analysis, and Gemini report generation."
        )
        return

    research_data: dict[str, Any] = {
        "prospect": {key: value for key, value in data.items() if key != "submitted"},
        "discovered_data": {},
        "manual_overrides": build_manual_overrides(data),
        "final_data_used": {},
        "niche_detection": {},
        "business": {},
        "pagespeed": {},
        "competitors": [],
        "website_snapshot": {},
        "web_research": {},
        "contact_discovery": {},
        "competitor_analysis": {},
        "analytics_access": {
            "enabled": client_options.get("use_client_access", False),
            "ga4": {"available": False, "reason": "Client access data not enabled."},
            "search_console": {"available": False, "reason": "Client access data not enabled."},
        },
        "sources": [
            make_source("Manual prospect inputs", "", "manual_input", "Business details entered by GrowingMonk user.")
        ],
        "limitations": [],
    }

    with st.status("Running deep research...", expanded=True) as status:
        st.write("Searching business profile")
        identity = resolve_business_identity(data["business_name"], data["location"], data.get("gbp_link", ""))
        research_data["place_options"] = identity.get("place_options", [])
        if identity.get("error"):
            st.warning(identity["error"])
            research_data["business"] = identity
            research_data["limitations"].append(identity["error"])
        else:
            options = identity.get("place_options", [])
            selected_place = identity.get("selected_place", {})
            if len(options) > 1:
                labels = [
                    f"{option.get('name')} | {option.get('formatted_address')} | {option.get('rating', 'no rating')}"
                    for option in options
                ]
                selected_label = st.selectbox("Confirm matched business", labels)
                selected_index = labels.index(selected_label)
                selected_option = options[selected_index]
                selected_place = get_place_details(selected_option.get("place_id", ""))
                if selected_place.get("error"):
                    selected_place = selected_option
            research_data["business"] = selected_place
            _record_source(
                research_data,
                selected_place.get("name") or data["business_name"],
                selected_place.get("google_maps_url") or data.get("gbp_link", ""),
                "google_places",
                "Google Places business details.",
            )

        business = research_data["business"]
        detected_niche = infer_niche_from_place(business)
        selected_niche = data.get("niche") or ""
        effective_niche = detected_niche if detected_niche and detected_niche != "Other" else selected_niche or "Other"
        if selected_niche and detected_niche and detected_niche != "Other" and selected_niche != detected_niche:
            st.warning(
                f"Selected niche was {selected_niche}, but Google Places suggests {detected_niche}. "
                f"Competitor search will use {effective_niche}."
            )
        research_data["niche_detection"] = {
            "selected_niche": selected_niche,
            "detected_niche": detected_niche,
            "effective_niche": effective_niche,
            "place_types": business.get("types", []),
        }

        website = _website_for_pagespeed(data, business)
        st.write("Checking website")
        if website:
            research_data["pagespeed"] = get_pagespeed_summary(website, data["pagespeed_strategy"])
            _record_source(research_data, "Google PageSpeed Insights", website, "pagespeed", data["pagespeed_strategy"])
        else:
            research_data["pagespeed"] = {"error": "Website not found in manual input or Places data."}

        st.write("Fetching website snapshot")
        if website:
            research_data["website_snapshot"] = fetch_website_snapshot(website)
            if not research_data["website_snapshot"].get("error"):
                _record_source(
                    research_data,
                    research_data["website_snapshot"].get("page_title") or "Website homepage",
                    research_data["website_snapshot"].get("final_url") or website,
                    "website",
                    research_data["website_snapshot"].get("meta_description", ""),
                )
        else:
            research_data["website_snapshot"] = {"error": "Website snapshot skipped because no website URL was available."}

        st.write("Finding competitors")
        lat = business.get("latitude")
        lng = business.get("longitude")
        if lat is not None and lng is not None:
            competitors = find_nearby_competitors(
                lat=float(lat),
                lng=float(lng),
                niche=effective_niche,
                exclude_name=data["business_name"],
                exclude_place_id=business.get("place_id", ""),
            )
            research_data["competitors"] = competitors
        else:
            research_data["competitors"] = []
            research_data["limitations"].append("Competitors skipped because latitude/longitude were unavailable.")

        st.write("Preparing free public research checklist")
        research_data["web_research"] = research_business_public_presence(
            business_name=data["business_name"],
            city=data["location"],
            website=website,
            instagram=data.get("instagram_handle", ""),
            niche=effective_niche,
        )
        if not research_data["web_research"].get("available"):
            st.info(research_data["web_research"].get("error"))
        for result in research_data["web_research"].get("results", []):
            _record_source(
                research_data,
                result.get("title") or result.get("source_domain") or "Search result",
                result.get("link") or "",
                "search_result",
                result.get("snippet") or "",
            )
        if not website:
            discovered_website = infer_website_from_web_research(research_data["web_research"], data["business_name"])
            if discovered_website:
                website = discovered_website
                research_data["pagespeed"] = get_pagespeed_summary(website, data["pagespeed_strategy"])
                research_data["website_snapshot"] = fetch_website_snapshot(website)
                _record_source(research_data, "Discovered website from public search", website, "search_result", "Website inferred from optional public search result.")

        st.write("Discovering contact details")
        research_data["contact_discovery"] = merge_contact_sources(
            business,
            research_data["web_research"],
            research_data.get("website_snapshot", {}),
        )
        instagram_discovery = discover_instagram(data, research_data.get("website_snapshot", {}), research_data["web_research"])
        research_data["social_discovery"] = {"instagram": instagram_discovery}
        research_data["discovered_data"] = {
            "business": business,
            "website": website,
            "detected_niche": detected_niche,
            "instagram": instagram_discovery,
            "contact": research_data["contact_discovery"],
        }
        research_data["final_data_used"] = build_final_data_used(
            data=data,
            business=business,
            website=website,
            effective_niche=effective_niche,
            instagram=instagram_discovery,
            contact=research_data["contact_discovery"],
        )

        st.write("Analyzing reviews and competitors")
        research_data["competitor_analysis"] = analyze_competitors(
            business=business,
            competitors=research_data["competitors"],
            niche=effective_niche,
        )

        if client_options.get("use_client_access"):
            st.write("Pulling GA4 data if enabled")
            ga4 = get_ga4_summary(client_options.get("ga4_property_id", ""), client_options.get("days", 30))
            research_data["analytics_access"]["ga4"] = ga4
            if ga4.get("available"):
                _record_source(research_data, "Google Analytics 4", "", "ga4", f"{client_options.get('days', 30)} day summary")
            elif ga4.get("error") or ga4.get("reason"):
                message = ga4.get("error") or ga4.get("reason")
                st.warning(message)
                research_data["limitations"].append(message)

            st.write("Pulling Search Console data if enabled")
            sc = get_search_console_summary(client_options.get("search_console_site_url", ""), client_options.get("days", 30))
            research_data["analytics_access"]["search_console"] = sc
            if sc.get("available"):
                _record_source(research_data, "Google Search Console", client_options.get("search_console_site_url", ""), "search_console", f"{client_options.get('days', 30)} day summary")
            elif sc.get("error") or sc.get("reason"):
                message = sc.get("error") or sc.get("reason")
                st.warning(message)
                research_data["limitations"].append(message)

        report_system_instruction = """
You are a senior marketing strategist for GrowingMonk.
GrowingMonk is a growth systems agency for local, service, and ecommerce businesses.

Be practical, specific, honest, and business-focused.
Do not invent facts.
Use careful language when data is incomplete.
Focus on local visibility, Google reviews, Instagram Reels, WhatsApp/contact flow, offers, tracking, and conversion.
Avoid hype, fake claims, unsupported numbers, and generic agency language.
""".strip()

        try:
            st.write("Generating client due diligence report")
            client_report = generate_text(
                build_client_due_diligence_prompt(research_data),
                system_instruction=report_system_instruction,
            )
            client_report = clean_generated_report(client_report, client_safe=True)
            st.write("Generating internal sales diligence report")
            internal_report = generate_text(
                build_internal_sales_diligence_prompt(research_data),
                system_instruction=report_system_instruction,
            )
            internal_report = clean_generated_report(internal_report)
        except Exception as exc:
            status.update(label="Research completed, but Gemini generation failed.", state="error")
            st.error(f"Gemini generation failed: {exc}")
            render_deep_results(data, research_data, "", "")
            return

        st.write("Generating sales call brief")
        try:
            sales_brief = generate_text(
                build_sales_call_brief_prompt(research_data),
                system_instruction=report_system_instruction,
            )
            sales_brief = clean_generated_report(sales_brief)
        except Exception as exc:
            sales_brief = ""
            research_data["limitations"].append(f"Sales brief generation failed: {exc}")

        status.update(label="Deep research complete.", state="complete")

    st.success("Due diligence reports generated.")
    audit_record_id = save_generated_audit_record(
        mode=DEEP_MODE,
        data=data,
        research_data=research_data,
        client_report=client_report,
        internal_report=internal_report,
        sales_brief=sales_brief,
    )
    st.session_state["last_deep_results"] = {
        "data": data,
        "research_data": research_data,
        "client_report": client_report,
        "internal_report": internal_report,
        "sales_brief": sales_brief,
        "audit_record_id": audit_record_id,
    }
    render_deep_results(data, research_data, client_report, internal_report, sales_brief, audit_record_id)


def render_auto_discovered_summary(research_data: dict[str, Any]) -> None:
    final_data = research_data.get("final_data_used", {})
    business = research_data.get("business", {})
    contact = research_data.get("contact_discovery", {})
    competitors = research_data.get("competitors", [])
    instagram = research_data.get("social_discovery", {}).get("instagram", {})

    st.subheader("Auto-discovered data")
    col_1, col_2, col_3 = st.columns(3)
    with col_1:
        st.write(f"**Detected business:** {final_data.get('business_name') or 'Not found'}")
        st.write(f"**Business structure:** {final_data.get('business_structure') or 'Not found'}")
        st.write(f"**Detected niche/category:** {research_data.get('niche_detection', {}).get('effective_niche') or 'Not found'}")
        st.write(f"**Address:** {business.get('formatted_address') or 'Not found'}")
    with col_2:
        st.write(f"**Phone:** {business.get('international_phone_number') or business.get('phone_number') or 'Not found'}")
        st.write(f"**Website:** {final_data.get('website') or 'Not found'}")
        st.write(f"**Google rating:** {business.get('rating') or 'Not found'}")
    with col_3:
        st.write(f"**Review count:** {business.get('user_ratings_total') or 'Not found'}")
        st.write(f"**Google Maps:** {business.get('google_maps_url') or 'Not found'}")
        st.write(f"**Competitors found:** {len([c for c in competitors if not c.get('error')])}")

    st.write(f"**Instagram/public social links:** {', '.join(instagram.get('candidates', []) or []) or 'Not found'}")
    verified_wa = contact.get("verified_whatsapp_links", [])
    possible_wa = contact.get("possible_whatsapp_links_from_phone_numbers", [])
    possible_wa_labels = [
        item.get("link", "") if isinstance(item, dict) else str(item)
        for item in possible_wa
        if item
    ]
    st.write(f"**Verified WhatsApp links:** {', '.join(verified_wa) or 'Not found'}")
    st.write(f"**Possible WhatsApp links from phone numbers:** {', '.join(possible_wa_labels) or 'Not found'}")


def _render_markdown_downloads(
    markdown: str,
    business_name: str,
    report_type: str,
    markdown_label: str,
    markdown_file_label: str,
    pdf_label: str,
    pdf_file_label: str,
    research_data: dict[str, Any] | None = None,
    include_charts: bool = False,
    disabled: bool = False,
    disabled_help: str = "",
) -> None:
    col_md, col_pdf = st.columns(2)
    with col_md:
        add_download_button(
            markdown_label,
            data=markdown,
            file_name=report_file_name(business_name, markdown_file_label, "md"),
            mime="text/markdown",
            disabled=disabled,
            help=disabled_help or None,
        )
    with col_pdf:
        try:
            pdf_bytes = generate_audit_pdf(
                markdown,
                business_name,
                report_type,
                research_data=research_data,
                include_charts=include_charts,
            )
            add_download_button(
                pdf_label,
                data=pdf_bytes,
                file_name=report_file_name(business_name, pdf_file_label, "pdf"),
                mime="application/pdf",
                disabled=disabled,
                help=disabled_help or None,
            )
        except Exception as exc:
            st.warning(f"PDF generation failed. Markdown download is still available. {exc}")


def _report_pdf_or_note(
    markdown: str,
    business_name: str,
    report_type: str,
    research_data: dict[str, Any] | None = None,
    include_charts: bool = False,
) -> bytes | str:
    try:
        return generate_audit_pdf(
            markdown,
            business_name,
            report_type,
            research_data=research_data,
            include_charts=include_charts,
        )
    except Exception as exc:
        return f"PDF generation failed for {report_type}. Markdown is included. Error: {exc}\n"


def build_customer_share_pack(data: dict[str, Any], research_data: dict[str, Any], client_report: str) -> bytes:
    business_name = data["business_name"]
    return build_zip(
        {
            report_file_name(business_name, CLIENT_REPORT_FILE_LABEL, "pdf"): _report_pdf_or_note(
                client_report,
                business_name,
                "Growth Due Diligence Report",
                research_data=research_data,
                include_charts=True,
            ),
            report_file_name(business_name, CLIENT_REPORT_FILE_LABEL, "md"): client_report,
            "README.txt": (
                "Customer-share pack.\n"
                "Share only after GrowingMonk reviews the report for tone, factual accuracy, and unsupported claims.\n"
                "Do not include internal sales diligence, sales call brief, or raw research JSON in client-facing handoff.\n"
            ),
        }
    )


def build_sales_team_pack(
    data: dict[str, Any],
    research_data: dict[str, Any],
    client_report: str,
    internal_report: str,
    sales_brief: str,
) -> bytes:
    business_name = data["business_name"]
    research_json = build_research_payload(data, research_data, client_report, internal_report, sales_brief)
    return build_zip(
        {
            report_file_name(business_name, INTERNAL_REPORT_FILE_LABEL, "pdf"): _report_pdf_or_note(
                internal_report,
                business_name,
                "Internal Sales Diligence Report",
                research_data=research_data,
                include_charts=True,
            ),
            report_file_name(business_name, INTERNAL_REPORT_FILE_LABEL, "md"): internal_report,
            report_file_name(business_name, SALES_BRIEF_FILE_LABEL, "pdf"): _report_pdf_or_note(
                sales_brief,
                business_name,
                "Sales Call Brief",
                research_data=research_data,
                include_charts=False,
            ),
            report_file_name(business_name, SALES_BRIEF_FILE_LABEL, "md"): sales_brief,
            report_file_name(business_name, CLIENT_REPORT_FILE_LABEL, "pdf"): _report_pdf_or_note(
                client_report,
                business_name,
                "Growth Due Diligence Report",
                research_data=research_data,
                include_charts=True,
            ),
            report_file_name(business_name, CLIENT_REPORT_FILE_LABEL, "md"): client_report,
            report_file_name(business_name, RESEARCH_JSON_FILE_LABEL, "json"): research_json,
            "README.txt": (
                "GrowingMonk sales-team pack.\n"
                "Internal Sales Diligence and Sales Call Brief are internal-only.\n"
                "The Growth Due Diligence Report is the only prospect-shareable report in this pack.\n"
            ),
        }
    )


def build_delivery_artifacts(
    data: dict[str, Any],
    research_data: dict[str, Any],
    client_report: str,
    internal_report: str,
    sales_brief: str,
    customer_pack: bytes | None,
    sales_pack: bytes | None,
) -> dict[str, dict[str, Any]]:
    business_name = data["business_name"]
    artifacts: dict[str, dict[str, Any]] = {}

    if client_report:
        artifacts["Client PDF - safe for prospect"] = {
            "file_name": report_file_name(business_name, CLIENT_REPORT_FILE_LABEL, "pdf"),
            "payload": _report_pdf_or_note(
                client_report,
                business_name,
                "Growth Due Diligence Report",
                research_data=research_data,
                include_charts=True,
            ),
            "mime": "application/pdf",
            "client_safe": True,
        }
    if customer_pack:
        artifacts["Customer Share Pack ZIP - safe for prospect"] = {
            "file_name": report_file_name(business_name, CUSTOMER_PACK_FILE_LABEL, "zip"),
            "payload": customer_pack,
            "mime": "application/zip",
            "client_safe": True,
        }
    if internal_report:
        artifacts["Internal Sales Diligence PDF - internal only"] = {
            "file_name": report_file_name(business_name, INTERNAL_REPORT_FILE_LABEL, "pdf"),
            "payload": _report_pdf_or_note(
                internal_report,
                business_name,
                "Internal Sales Diligence Report",
                research_data=research_data,
                include_charts=True,
            ),
            "mime": "application/pdf",
            "client_safe": False,
        }
    if sales_brief:
        artifacts["Sales Call Brief PDF - internal only"] = {
            "file_name": report_file_name(business_name, SALES_BRIEF_FILE_LABEL, "pdf"),
            "payload": _report_pdf_or_note(
                sales_brief,
                business_name,
                "Sales Call Brief",
                research_data=research_data,
                include_charts=False,
            ),
            "mime": "application/pdf",
            "client_safe": False,
        }
    if sales_pack:
        artifacts["Sales Enablement Pack ZIP - internal only"] = {
            "file_name": report_file_name(business_name, SALES_PACK_FILE_LABEL, "zip"),
            "payload": sales_pack,
            "mime": "application/zip",
            "client_safe": False,
        }
    return artifacts


def artifact_bytes(payload: bytes | str) -> bytes:
    return payload if isinstance(payload, bytes) else payload.encode("utf-8")


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def render_research_numbers_and_graphs(research_data: dict[str, Any]) -> None:
    business = research_data.get("business", {})
    pagespeed = research_data.get("pagespeed", {})
    review_position = research_data.get("competitor_analysis", {}).get("review_position", {})
    competitors = research_data.get("competitor_analysis", {}).get("competitor_table_data", [])

    st.subheader("Numbers & Graphs")
    col_1, col_2, col_3, col_4 = st.columns(4)
    col_1.metric("Google rating", business.get("rating") or "Not found")
    col_2.metric("Google reviews", business.get("user_ratings_total") or 0)
    col_3.metric("Avg competitor reviews", review_position.get("avg_competitor_review_count") or "N/A")
    col_4.metric("Review gap vs top", review_position.get("review_volume_gap_vs_top") or "N/A")

    score_rows = [
        {"Metric": "Performance", "Score": pagespeed.get("performance_score")},
        {"Metric": "Accessibility", "Score": pagespeed.get("accessibility_score")},
        {"Metric": "Best practices", "Score": pagespeed.get("best_practices_score")},
        {"Metric": "SEO", "Score": pagespeed.get("seo_score")},
    ]
    score_rows = [row for row in score_rows if row["Score"] is not None]
    if score_rows:
        st.caption("PageSpeed score overview")
        st.bar_chart(score_rows, x="Metric", y="Score", horizontal=True)

    review_rows = [
        {
            "Business": business.get("name") or research_data.get("final_data_used", {}).get("business_name") or "Prospect",
            "Reviews": business.get("user_ratings_total") or 0,
        }
    ]
    for competitor in competitors:
        review_rows.append(
            {
                "Business": competitor.get("name") or "Competitor",
                "Reviews": competitor.get("review_count") or 0,
            }
        )
    if len(review_rows) > 1:
        st.caption("Visible Google review volume comparison")
        st.bar_chart(review_rows, x="Business", y="Reviews", horizontal=True)


def render_delivery_actions(
    data: dict[str, Any],
    research_data: dict[str, Any],
    client_report: str,
    internal_report: str,
    sales_brief: str,
    customer_pack: bytes | None,
    sales_pack: bytes | None,
    client_reviewed: bool = False,
) -> None:
    if not customer_pack and not sales_pack and not client_report:
        return

    business_name = data["business_name"]
    artifacts = build_delivery_artifacts(
        data,
        research_data,
        client_report,
        internal_report,
        sales_brief,
        customer_pack,
        sales_pack,
    )
    if not artifacts:
        return

    with st.expander("Share or Save Document Packs", expanded=False):
        st.caption("Internal tool only. Review the selected file before uploading or emailing.")
        with st.popover("Delivery setup help"):
            st.markdown("**Google Drive**")
            st.code(
                'gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.file"',
                language="bash",
            )
            st.markdown("Restart Streamlit after re-authenticating.")
            st.markdown("**Email SMTP**")
            st.code(
                '\n'.join(
                    [
                        'SMTP_HOST = "smtp.gmail.com"',
                        'SMTP_PORT = "587"',
                        'SMTP_SECURITY = "starttls"',
                        'SMTP_USER = "you@growingmonk.com"',
                        'SMTP_PASSWORD = "app-password"',
                        'SMTP_FROM = "you@growingmonk.com"',
                    ]
                ),
                language="toml",
            )
        drive_col, email_col = st.columns(2)

        with drive_col:
            st.markdown("#### Google Drive")
            drive_artifact_label = st.selectbox(
                "File to upload",
                list(artifacts.keys()),
                key="drive_artifact_choice",
            )
            if not artifacts[drive_artifact_label]["client_safe"]:
                st.warning("This file is internal-only. Do not share the Drive link with a prospect.")
            elif not client_reviewed:
                st.warning("Review and approve the client-facing report before uploading a prospect-shareable file.")
            default_folder_id = get_secret("GOOGLE_DRIVE_FOLDER_ID")
            folder_input = st.text_input(
                "Drive parent folder URL, ID, or exact name",
                value=default_folder_id,
                help="Use Sales-Reports, paste its full folder URL, or leave blank for My Drive.",
            )
            client_folder_name = build_drive_client_folder_name(business_name)
            st.caption(f"Upload destination: `{folder_input.strip() or 'My Drive'}` / `{client_folder_name}`")
            share_link = st.checkbox(
                "Make uploaded file accessible to anyone with the link",
                value=False,
                help="Use this only for the client-safe PDF or customer share pack after review.",
            )
            drive_disabled = artifacts[drive_artifact_label]["client_safe"] and not client_reviewed
            if st.button("Upload selected file to Google Drive", type="primary", disabled=drive_disabled):
                artifact = artifacts[drive_artifact_label]
                file_name = artifact["file_name"]
                payload = artifact_bytes(artifact["payload"])
                try:
                    with st.spinner("Uploading to Google Drive..."):
                        link = upload_file_to_drive(
                            file_name,
                            payload,
                            artifact["mime"],
                            folder_input.strip(),
                            share_anyone_with_link=share_link,
                            client_folder_name=client_folder_name,
                        )
                    st.success("Uploaded to Google Drive.")
                    st.link_button("Open uploaded file", link)
                except Exception as exc:
                    st.error(f"Google Drive upload failed: {exc}")
                    st.info(drive_error_help(exc))

        with email_col:
            st.markdown("#### Email")
            email_artifact_label = st.selectbox(
                "File to email",
                list(artifacts.keys()),
                key="email_artifact_choice",
            )
            selected_email_artifact = artifacts[email_artifact_label]
            if not selected_email_artifact["client_safe"]:
                st.warning("This file is internal-only. Do not send it to a prospect.")
            elif not client_reviewed:
                st.warning("Review and approve the client-facing report before emailing a prospect-shareable file.")
            with st.form("email_pack_form"):
                recipient = st.text_input("Recipient email")
                subject = st.text_input(
                    "Subject",
                    value=f"{business_name} - Growth Due Diligence Report",
                )
                body = st.text_area(
                    "Email body",
                    value=(
                        "Hi,\n\n"
                        "Sharing the Growth Due Diligence document prepared by GrowingMonk.\n\n"
                        "Regards,\nGrowingMonk"
                    ),
                    height=150,
                )
                email_disabled = selected_email_artifact["client_safe"] and not client_reviewed
                send_submitted = st.form_submit_button("Email selected pack", disabled=email_disabled)

            if send_submitted:
                if not smtp_configured():
                    missing = ", ".join(smtp_missing_settings())
                    st.error(f"SMTP is not configured. Missing: {missing}. Add SMTP settings in secrets before sending email.")
                    st.code(
                        '\n'.join(
                            [
                                'SMTP_HOST = "smtp.gmail.com"',
                                'SMTP_PORT = "587"',
                                'SMTP_SECURITY = "starttls"',
                                'SMTP_USER = "you@growingmonk.com"',
                                'SMTP_PASSWORD = "app-password"',
                                'SMTP_FROM = "you@growingmonk.com"',
                            ]
                        ),
                        language="toml",
                    )
                elif not recipient.strip():
                    st.error("Enter a recipient email.")
                else:
                    file_name = selected_email_artifact["file_name"]
                    payload = artifact_bytes(selected_email_artifact["payload"])
                    try:
                        with st.spinner("Sending email..."):
                            send_email_with_attachment(
                                recipient=recipient.strip(),
                                subject=subject.strip() or f"{business_name} - Growth Due Diligence Report",
                                body=body,
                                attachment_name=file_name,
                                attachment_bytes=payload,
                                attachment_mime=selected_email_artifact["mime"],
                            )
                        st.success("Email sent.")
                    except Exception as exc:
                        st.error(f"Email failed: {exc}")


def render_deep_results(
    data: dict[str, Any],
    research_data: dict[str, Any],
    client_report: str,
    internal_report: str = "",
    sales_brief: str = "",
    audit_record_id: str = "",
) -> None:
    render_auto_discovered_summary(research_data)
    render_research_numbers_and_graphs(research_data)
    if internal_report or sales_brief:
        render_sales_action_card(research_data, internal_report, sales_brief)

    client_reviewed = False
    if client_report:
        review_key = f"client_safe_reviewed_{audit_record_id or safe_folder_name(data['business_name'])}"
        client_reviewed = st.checkbox(
            CLIENT_SAFE_REVIEW_LABEL,
            value=bool(st.session_state.get(review_key, False)),
            key=review_key,
            help="Required before downloading, uploading, or emailing prospect-shareable files.",
        )
        if audit_record_id:
            update_audit_record(audit_record_id, client_reviewed=client_reviewed)
        if not client_reviewed:
            st.warning("Client-facing downloads and delivery are locked until review is confirmed.")

    customer_pack = build_customer_share_pack(data, research_data, client_report) if client_report else None
    sales_pack = (
        build_sales_team_pack(data, research_data, client_report, internal_report, sales_brief)
        if client_report and internal_report and sales_brief
        else None
    )

    if client_report or internal_report or sales_brief:
        st.subheader("File Packs")
        pack_col_1, pack_col_2 = st.columns(2)
        with pack_col_1:
            if sales_pack:
                add_download_button(
                    "Download Sales Team Pack",
                    data=sales_pack,
                    file_name=report_file_name(data["business_name"], SALES_PACK_FILE_LABEL, "zip"),
                    mime="application/zip",
                    help="Internal pack: sales diligence, sales call brief, client report copy, and verified research JSON.",
                    type="primary",
                )
            else:
                st.info("Sales Team Pack needs the internal report and sales call brief.")
        with pack_col_2:
            if customer_pack:
                add_download_button(
                    "Download Customer Share Pack",
                    data=customer_pack,
                    file_name=report_file_name(data["business_name"], CUSTOMER_PACK_FILE_LABEL, "zip"),
                    mime="application/zip",
                    help="Client-safe pack: Growth Due Diligence Report only.",
                    type="primary",
                    disabled=not client_reviewed,
                )
            else:
                st.info("Customer Share Pack needs the client due diligence report.")
        render_delivery_actions(
            data,
            research_data,
            client_report,
            internal_report,
            sales_brief,
            customer_pack,
            sales_pack,
            client_reviewed=client_reviewed,
        )

    (
        tab_client,
        tab_internal,
        tab_sales,
        tab_verified,
        tab_competitors,
        tab_contact,
        tab_website,
        tab_raw,
    ) = st.tabs(
        [
            "Client Due Diligence Report",
            "Internal Sales Diligence",
            "Sales Call Brief",
            "Verified Data",
            "Competitors",
            "Contact Discovery",
            "Website Snapshot",
            "Raw JSON",
        ]
    )

    with tab_client:
        if client_report:
            _render_markdown_downloads(
                markdown=client_report,
                business_name=data["business_name"],
                report_type="Growth Due Diligence Report",
                markdown_label="Download Client Due Diligence as Markdown",
                markdown_file_label=CLIENT_REPORT_FILE_LABEL,
                pdf_label="Download Client Due Diligence as PDF",
                pdf_file_label=CLIENT_REPORT_FILE_LABEL,
                research_data=research_data,
                include_charts=True,
                disabled=not client_reviewed,
                disabled_help="Review and approve the client-facing report before downloading.",
            )
            st.markdown(client_report)
        else:
            st.info("Client due diligence report was not generated, but research data is available in the other tabs.")

    with tab_internal:
        if internal_report:
            st.warning("Internal-only. Do not send this report to the client.")
            _render_markdown_downloads(
                markdown=internal_report,
                business_name=data["business_name"],
                report_type="Internal Sales Diligence Report",
                markdown_label="Download Internal Sales Diligence as Markdown",
                markdown_file_label=INTERNAL_REPORT_FILE_LABEL,
                pdf_label="Download Internal Sales Diligence as PDF",
                pdf_file_label=INTERNAL_REPORT_FILE_LABEL,
                research_data=research_data,
                include_charts=True,
            )
            st.markdown(internal_report)
        else:
            st.info("Internal sales diligence report was not generated, but research data is available in the other tabs.")

    with tab_sales:
        if sales_brief:
            _render_markdown_downloads(
                markdown=sales_brief,
                business_name=data["business_name"],
                report_type="Sales Call Brief",
                markdown_label="Download Sales Call Brief as Markdown",
                markdown_file_label=SALES_BRIEF_FILE_LABEL,
                pdf_label="Download Sales Call Brief as PDF",
                pdf_file_label=SALES_BRIEF_FILE_LABEL,
                research_data=research_data,
                include_charts=False,
            )
            st.markdown(sales_brief)
        else:
            st.info("Sales call brief was not generated.")

    with tab_verified:
        st.json(
            {
                "business": research_data.get("business"),
                "niche_detection": research_data.get("niche_detection"),
                "final_data_used": research_data.get("final_data_used"),
                "pagespeed": research_data.get("pagespeed"),
                "analytics_access": research_data.get("analytics_access"),
                "sources": research_data.get("sources"),
                "limitations": research_data.get("limitations"),
                "manual_search_queries": research_data.get("web_research", {}).get("suggested_manual_search_queries", []),
            }
        )

    with tab_competitors:
        table = research_data.get("competitor_analysis", {}).get("competitor_table_data", [])
        if table:
            st.dataframe(table, use_container_width=True)
        st.json(research_data.get("competitor_analysis", {}))

    with tab_contact:
        st.json(research_data.get("contact_discovery", {}))

    with tab_website:
        st.json(research_data.get("website_snapshot", {}))

    with tab_raw:
        st.json(research_data)

    add_download_button(
        "Download Verified Research Data as JSON",
        data=build_research_payload(data, research_data, client_report, internal_report, sales_brief),
        file_name=report_file_name(data["business_name"], RESEARCH_JSON_FILE_LABEL, "json"),
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="MonkAudit | GrowingMonk", layout="wide")
    require_login()
    render_sidebar()

    st.title("MonkAudit | GrowingMonk")
    st.caption("Internal prospect audit assistant")

    mode = st.radio("Audit mode", [QUICK_MODE, DEEP_MODE], horizontal=True)
    should_run_research = False
    client_options: dict[str, Any] = {
        "use_client_access": False,
        "ga4_property_id": get_secret("GA4_PROPERTY_ID"),
        "search_console_site_url": get_secret("SEARCH_CONSOLE_SITE_URL"),
        "days": 30,
    }
    if mode == DEEP_MODE:
        should_run_research = st.checkbox("Run Deep Research - may use paid APIs", value=False)
        use_client_access = st.checkbox(
            "Use Client Access Data",
            value=False,
            help="Only enable this if the prospect/client has given Google Analytics or Search Console access.",
        )
        client_options["use_client_access"] = use_client_access
        if use_client_access:
            with st.expander("Client Access Research", expanded=True):
                client_options["ga4_property_id"] = st.text_input(
                    "GA4 Property ID",
                    value=client_options["ga4_property_id"],
                )
                client_options["search_console_site_url"] = st.text_input(
                    "Search Console Site URL",
                    value=client_options["search_console_site_url"],
                )
                client_options["days"] = st.selectbox("Days range", [7, 30, 90], index=1)

    data = collect_form_data(mode)
    if not data["submitted"]:
        if mode == QUICK_MODE and st.session_state.get("last_quick_results"):
            previous = st.session_state["last_quick_results"]
            st.info("Showing the last generated mini audit from this session.")
            render_results(previous["data"], previous["pagespeed"], previous["audit"])
        elif mode == DEEP_MODE and st.session_state.get("last_deep_results"):
            previous = st.session_state["last_deep_results"]
            st.info("Showing the last generated deep research reports from this session.")
            render_deep_results(
                previous["data"],
                previous["research_data"],
                previous["client_report"],
                previous["internal_report"],
                previous["sales_brief"],
                previous.get("audit_record_id", ""),
            )
        return

    if mode == QUICK_MODE:
        run_quick_audit(data)
    else:
        run_deep_research(data, should_run_research, client_options)


if __name__ == "__main__":
    main()
