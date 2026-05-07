from __future__ import annotations

import json
from typing import Any


NICHE_GUIDANCE: dict[str, str] = {
    "Salon / Beauty": """
- Local visibility: check whether nearby people can quickly understand services, location, pricing signals, and booking options.
- Instagram Reels: look for proof of outcomes, transformations, stylist expertise, client experience, and consistency.
- Google Business Profile: review service categories, photos, review quality, booking/call actions, and location relevance.
- Reviews: look for recent, specific reviews around results, hygiene, experience, staff, and repeat visits.
- Offer clarity: highlight packages, first-visit offers, bridal/event services, membership or maintenance plans where relevant.
- Website conversion: check whether services, prices/ranges, location, trust signals, gallery, and booking CTA are easy to find.
- WhatsApp/contact flow: check if appointment questions, availability, and consultation booking can happen quickly.
- Tracking: recommend tracking call clicks, WhatsApp clicks, booking form starts, GBP actions, and confirmed bookings if shared.
""",
    "Restaurant / Cafe": """
- Local visibility: check search intent around cuisine, location, opening hours, menu, ambience, delivery, and reservations.
- Instagram Reels: look for food visuals, chef/process content, atmosphere, offers, events, and customer moments.
- Google Business Profile: review menu links, photos, hours, reservation/order links, review response quality, and map visibility.
- Reviews: look for recent feedback on food quality, service, ambience, wait times, delivery, and repeat visits.
- Offer clarity: highlight lunch specials, combos, events, delivery offers, catering, or reservation-led experiences where relevant.
- Website conversion: check menu access, location, ordering/reservation CTA, hours, phone, maps, and mobile speed.
- WhatsApp/contact flow: check if table bookings, catering inquiries, and party reservations can be handled without friction.
- Tracking: recommend tracking call clicks, directions, menu clicks, order/reservation clicks, WhatsApp clicks, and GBP actions.
""",
    "Local Service": """
- Local visibility: check service-area clarity, city pages, emergency/urgent intent, trust markers, and proof of completed work.
- Instagram Reels: look for before/after work, technician/process clips, customer education, and local credibility.
- Google Business Profile: review service categories, service area, photos, Q&A, review quality, and call/direction actions.
- Reviews: look for recent, specific reviews around punctuality, quality, pricing transparency, and problem resolution.
- Offer clarity: highlight inspection, quote, repair, maintenance plan, or urgent-service offers where relevant.
- Website conversion: check service pages, location/service area, proof, licensing if relevant, and prominent call/WhatsApp CTA.
- WhatsApp/contact flow: check whether quote requests can include photos, location, urgency, and preferred visit times.
- Tracking: recommend tracking call clicks, quote forms, WhatsApp clicks, service page visits, GBP actions, and booked jobs if shared.
""",
    "Clinic / Wellness": """
- Local visibility: check treatment/service clarity, practitioner trust, location, appointment flow, and patient intent.
- Instagram Reels: look for educational content, treatment explanations, patient-safe proof, practitioner credibility, and FAQs.
- Google Business Profile: review medical/wellness categories, appointment links, photos, reviews, Q&A, and location accuracy.
- Reviews: look for recent feedback on care quality, professionalism, comfort, wait times, and outcomes without overstating claims.
- Offer clarity: highlight consultation, assessment, packages, follow-up care, and suitability criteria where relevant.
- Website conversion: check service pages, practitioner bios, trust signals, FAQs, compliance-sensitive claims, and booking CTA.
- WhatsApp/contact flow: check if appointment requests, eligibility questions, and follow-up steps are easy and respectful.
- Tracking: recommend tracking call clicks, WhatsApp clicks, appointment form starts, GBP actions, and confirmed bookings if shared.
""",
    "Ecommerce / D2C": """
- Local visibility: if location matters, check local search and GBP; otherwise focus on product discovery and branded search.
- Instagram Reels: look for product demos, use cases, founder/process content, UGC, objections, comparisons, and social proof.
- Google Business Profile: only emphasize this if the brand has a store, pickup point, showroom, or local service presence.
- Reviews: look for product reviews, shipping feedback, quality proof, repeat purchase signals, and customer objections.
- Offer clarity: highlight bestsellers, bundles, starter kits, guarantees/policies, shipping thresholds, and category positioning.
- Website conversion: check product pages, mobile speed, CTA clarity, trust badges, reviews, FAQs, cart friction, and checkout signals.
- WhatsApp/contact flow: check whether product questions, size/fit help, bulk orders, or support can convert through chat.
- Tracking: recommend tracking product views, add-to-cart, checkout starts, purchases, WhatsApp clicks, and campaign source quality.
""",
}


def _niche_guidance(niche: str) -> str:
    return NICHE_GUIDANCE.get(
        niche,
        """
- Local visibility: check whether the business can be found for the obvious buyer/search intent in its market.
- Instagram Reels: look for proof, education, personality, useful objections, and content that makes the offer easier to understand.
- Google Business Profile: review categories, photos, reviews, actions, location/service area, and completeness where relevant.
- Reviews: look for recency, specificity, owner responses, and buyer confidence.
- Offer clarity: check whether the next step and reason to act now are clear without sounding pushy.
- Website conversion: check mobile clarity, CTA placement, proof, speed, and friction.
- WhatsApp/contact flow: check whether a prospect can ask, qualify, book, or buy with minimal back-and-forth.
- Tracking: recommend the first practical events to track before asking for advanced reporting.
""",
    ).strip()


def _business_structure_guidance(structure: str) -> str:
    normalized = (structure or "Single location/store").strip()
    guidance = {
        "Single location/store": """
- Audit as one local revenue unit. Prioritize local search visibility, Google Business Profile quality, review volume, contact/booking friction, offer clarity, nearby competitor comparison, and the first 30-day lead-flow improvements.
- Do not assume centralized brand budgets, franchise support, multi-location reporting, or expansion plans unless the data says so.
""",
        "Local brand with multiple locations": """
- Audit as a multi-location brand. Separate brand-level issues from location-level issues.
- Look for consistency across website, Google profiles, location pages, reviews, offers, tracking, and content.
- Recommend systems that can scale across locations: location page template, GBP standards, review collection process, campaign structure, reporting, and local content operations.
- Avoid judging one location as the whole brand unless only one location has data.
""",
        "Regional master franchise": """
- Audit as a regional growth and partner-acquisition system, not only as one outlet.
- Consider franchisee lead generation, location expansion, territory credibility, unit economics proof needed, regional brand visibility, sales enablement, local store marketing standards, and reporting across franchise locations.
- Separate three layers: regional master brand, individual franchise locations, and franchisee/investor acquisition.
- Do not claim franchise performance, profitability, or territory demand unless client-confirmed data exists.
""",
        "Franchise location": """
- Audit as one operator within a broader franchise system. Separate what the local operator can control from what the parent brand controls.
- Focus on local GBP execution, reviews, local content, contact flow, local offers permitted by brand guidelines, tracking access, and local campaign opportunities.
- Avoid recommending changes that may violate franchise brand guidelines unless framed as items to confirm with the franchisor.
""",
        "Online-first brand": """
- Audit as a brand/distribution system rather than a map-first local business.
- Prioritize product/category discovery, website conversion, tracking, content proof, paid/social funnel clarity, email/WhatsApp capture, retention signals, and offer architecture.
- Use Google Business Profile and local competitor data only if there is a showroom, store, pickup point, or local service angle.
""",
        "Other / unsure": """
- State that business structure needs confirmation. Avoid overfitting the recommendations.
- Give the safest first-pass audit, then list the questions needed to determine whether this is a single location, multi-location brand, franchise unit, master franchise, or online-first brand.
""",
    }
    return guidance.get(normalized, guidance["Other / unsure"]).strip()


def build_audit_prompt(data: dict[str, Any], pagespeed: dict[str, Any]) -> str:
    prospect_json = json.dumps(data, indent=2, ensure_ascii=False)
    pagespeed_json = json.dumps(pagespeed, indent=2, ensure_ascii=False)
    niche = str(data.get("niche", "")).strip()
    business_structure = str(data.get("business_structure", "Single location/store")).strip()
    niche_guidance = _niche_guidance(niche)
    structure_guidance = _business_structure_guidance(business_structure)

    return f"""
You are a senior growth systems strategist for GrowingMonk.

GrowingMonk helps local, service, and ecommerce businesses improve visibility, lead flow, contact flow, content, ads, tracking, and AI-supported workflows. Your job is to create a useful internal mini-audit that helps a strategist prepare a thoughtful outreach message and a sharper sales call.

Think like a premium growth systems agency, not a generic digital marketing agency. Focus on the business system:
- how the right prospect discovers the business
- what proof and offer clarity they see
- how easily they can contact, book, order, or ask a question
- what can be tracked now
- what should be reviewed once the client gives access

Rules:
- Use only the available information below.
- Do not invent facts, metrics, reviews, rankings, ad spend, revenue, or conversion rates.
- Do not guarantee results.
- Do not make fake claims.
- Do not say GrowingMonk has already found issues unless the data supports it.
- If PageSpeed failed, use it only as a note and continue from the manual inputs.
- When data is incomplete, use careful language such as "appears", "may be", "should be reviewed", "likely opportunity", and "based on available information".
- Be specific enough for a founder or strategist to use on a sales call.
- Keep recommendations practical for a first 30-day sprint.

Niche-specific lens for {niche or "this business"}:
{niche_guidance}

Business structure lens for {business_structure or "Single location/store"}:
{structure_guidance}

Business/prospect data:
```json
{prospect_json}
```

PageSpeed summary:
```json
{pagespeed_json}
```

The output must be Markdown with this exact structure:

# [Business Name] — Mini Growth Audit

## 1. Quick Business Snapshot
Write 2-3 lines. Explain what the business appears to sell, who it likely serves, and what the growth system may need next. Be honest if information is limited.

## 2. What Looks Strong
Give 2-3 bullets. Mention only strengths supported by the inputs. If information is limited, say what appears promising or worth validating.

## 3. Where Leads May Be Leaking
Give 5 practical gaps. Each gap should include:
- what may be happening
- why it matters commercially
- what should be checked or improved first

Prioritize the most relevant of:
- Google Business Profile / local visibility
- Instagram Reels / content clarity
- reviews and trust signals
- website or landing page conversion
- WhatsApp / call / contact flow
- offer clarity
- tracking gaps
- audience targeting where relevant

## 4. First 30-Day Growth Sprint Recommendation
Give 5 realistic action steps GrowingMonk could do in 30 days. Make them concrete, sequenced, and measurable where possible. Do not overpromise.

## 5. Suggested Outreach Message
Write a short personalized message to the business owner. Make it warm, specific, and not spammy. Mention one or two likely opportunities, not a long audit dump.

## 6. Sales Call Talking Points
Give 5 talking points for the founder or strategist. Each point should help diagnose the business, create trust, or identify whether GrowingMonk can help.

## 7. Tracking Notes
Explain what can be tracked immediately and what needs client access.
Mention:
- WhatsApp clicks
- call button clicks
- forms
- Google Business Profile actions
- confirmed bookings/orders only if client shares them

Tone:
- premium
- direct
- practical
- clear
- commercially useful
- no fake claims
- no "guaranteed growth"
- no "skyrocket"
- no generic agency language
""".strip()


def _research_context(data: dict[str, Any]) -> tuple[str, str]:
    research_json = json.dumps(data, indent=2, ensure_ascii=False)
    business_name = data.get("prospect", {}).get("business_name") or data.get("business", {}).get("name") or "Business"
    return research_json, business_name


def _research_structure_context(data: dict[str, Any]) -> str:
    structure = (
        data.get("final_data_used", {}).get("business_structure")
        or data.get("manual_overrides", {}).get("business_structure")
        or data.get("prospect", {}).get("business_structure")
        or "Single location/store"
    )
    return f"""
Business structure selected by GrowingMonk: {structure}

Use this structure to frame the audit:
{_business_structure_guidance(str(structure))}
""".strip()


def build_internal_sales_diligence_prompt(data: dict[str, Any]) -> str:
    research_json, business_name = _research_context(data)
    structure_context = _research_structure_context(data)

    return f"""
You are a senior sales strategist for GrowingMonk.

Use only the provided data. Do not invent facts. Use `final_data_used` as the main business identity. Mention manual overrides separately when relevant. Separate auto-discovered public data, manual overrides, missing data, and client-access analytics data. Cite source names or source types when making important claims. Never pretend GA4, Search Console, private Instagram, bookings, revenue, or ad account data exists unless it is present in the JSON.

This report is for GrowingMonk internal use only. It should help a salesperson prepare a specific pitch. It may include direct competitor gaps, pitch angles, outreach messages, call questions, likely objections, internal warnings, proof needed before claims, where to push the conversation, and what access to request from the prospect.

{structure_context}

Research data:
```json
{research_json}
```

Generate a Markdown report with this exact structure:

# {business_name} — Internal Sales Diligence Report

**Internal-only: Do not send this report to the client.**

## 1. Internal Executive Summary
Give a direct, specific 4-5 line internal summary of the business's current digital position and the likely sales opportunity.

## 2. Verified Public Data
Summarize only the most important verified public data. Avoid repeating full Google Places fields already visible in the JSON. Include Google Places, website snapshot, PageSpeed, public contact signals, and public search results only where useful.

Include a compact Markdown table for verified numbers when available:
- Google rating
- Google review count
- Average competitor rating
- Average competitor review count
- Review gap vs average
- Review gap vs top competitor
- PageSpeed performance, accessibility, best practices, and SEO scores

If a field is missing, place it under "Needs Client Confirmation" instead of calling it "Missing Data."

## 3. Inferred Opportunities
Clearly separate opportunities inferred from public data from verified facts. Use "appears", "may", and "should be checked" where appropriate.

## 4. Needs Client Confirmation
List data requiring client access / confirmation, such as GBP access, analytics, Search Console, ad accounts, booking/contact records, Instagram insights, and revenue/bookings data. Use the heading wording "Data Requiring Client Access / Confirmation" when referring to this bucket.

## 5. Category / Niche Detection
Explain selected niche, detected niche, business structure, place types, and what the category implies for local visibility, content, offer clarity, contact flow, and scale/franchise needs where relevant.

## 6. Google Review & Local Trust Gap
Compare review count/rating carefully against nearby competitors. State what is verified and what is inferred. Do not claim exact lead loss or revenue impact.

## 7. Competitor Comparison
For each competitor, include name, rating/reviews, visible strength, possible weakness, and how the salesperson can use the comparison carefully.
Use a Markdown table where available. Include review counts and ratings as numbers, not vague claims.

## 8. Contact / WhatsApp / Booking Flow
Use discovered phone/WhatsApp/contact data. Do not call a phone number WhatsApp unless a public WhatsApp link/source was found. Possible generated links must be labeled "possible WhatsApp link - needs manual verification." Explain contact friction and what access or confirmation to request.

## 9. Website & Content Observations
Use PageSpeed, website snapshot, public search results, and Search Console only if available. Explain content clarity, trust signals, offer clarity, local pages, technical checks, and conversion implications. If something is not found in the lightweight snapshot, use: "Our lightweight website snapshot did not detect... This should be verified with a deeper website review."

## 10. Main Sales Pitch Angle
Write one very specific pitch angle for this business. Reference only supported review, competitor, contact, website, content, tracking, or offer opportunities.

## 11. Outreach Messages
Write:
- Instagram DM
- WhatsApp message
- Email
- Follow-up 1
- Follow-up 2

Messages should be short, specific, and not spammy.

## 12. Sales Call Questions
Give 8-10 smart questions that diagnose access, tracking, booking/contact flow, offers, content, local visibility, and current constraints.

## 13. Likely Objections & Responses
Give likely objections and concise responses a salesperson can use without overstating claims.

## 14. Recommended Offer
Recommend the most appropriate GrowingMonk offer and why. Use one of: Free Growth Audit, 30-Day Growth Sprint, Monthly Growth System, Tracking Setup First.

## 15. Proof Needed Before Claims
State clearly: Do not claim revenue, bookings, or exact lead loss without client-confirmed data.
List what must be confirmed before making stronger claims: GBP access, Instagram insights, call/WhatsApp data, appointment records, ad account access, booking software or manual sheet.

## 16. Internal Notes & Cautions
Include internal warnings, what not to claim, where to push the conversation, and what access to request from the client.

Rules:
- Do not invent data.
- Use "verified" only for API/public-source data.
- Use "appears" for inferences.
- Do not guarantee results.
- Do not say revenue or bookings unless provided.
- Do not claim a phone number is WhatsApp unless a public WhatsApp link was found. If only a phone number is available, say it may be tested as a possible WhatsApp number.
- Never invent analytics.
- Never claim private Instagram inspection.
- Never claim WhatsApp is active unless a WhatsApp link/source is found.
- Never claim revenue impact unless provided.
- Mark this as internal-only in the report.
- Include numbers and simple Markdown tables where the JSON supports them.
- Make it direct, strategic, specific, and sales-useful.
- Keep "Internal-only: Do not send this report to the client." visible on page 1.
""".strip()


def build_client_due_diligence_prompt(data: dict[str, Any]) -> str:
    research_json, business_name = _research_context(data)
    structure_context = _research_structure_context(data)

    return f"""
You are a senior growth strategist for GrowingMonk preparing a client-shareable due diligence report for a business owner or prospect.

Use only the provided data. Do not invent facts. Use `final_data_used` as the main business identity. Clearly separate verified public data from inferred opportunities. Never pretend GA4, Search Console, private Instagram, bookings, revenue, or ad account data exists unless it is present in the JSON.

This report should build trust and show GrowingMonk did real research before pitching. It is for a lead/prospect who has not yet signed. It must be helpful, premium, practical, careful, and not aggressive. Give enough insight to prove expertise, but do not give away a full implementation playbook.

{structure_context}

Research data:
```json
{research_json}
```

Generate a Markdown report with this exact structure:

# {business_name} — Growth Due Diligence Report

## 1. Executive Summary
Give a concise 3-4 line executive summary using careful, prospect-safe language. Do not start with charts or raw data.

## 2. What We Reviewed
Explain that the report is based on publicly available information and limited technical checks. Mention source categories used, such as Google Places, PageSpeed, website snapshot, public search results, contact discovery, competitor comparison, and optional client-access data only if present.

## 3. Verified Number Snapshot
Include a small "Verified Number Snapshot" table when numbers are available. Use only verified public or permitted client-access numbers.

## 4. What Looks Strong
Give 3-5 positive observations supported by the available data. If evidence is limited, phrase the point as something that appears promising or worth building on.

## 5. Key Growth Opportunities
Give 5-7 practical improvement opportunities. Keep them specific to the business structure and separate verified observations from inferred opportunities. Explain what should be improved and why it matters, but avoid step-by-step execution detail, exact ad/content calendars, scripts, or internal strategy mechanics.

## 6. Local Visibility and Trust
Use review/rating/competitor comparison carefully and professionally.
Include a simple comparison table when competitor review/rating data is available. Keep the language professional and directional.
Use safe language such as:
- "Some nearby businesses appear to have stronger review volume."
- "This can influence customer trust during quick comparisons."
- "There is an opportunity to strengthen local visibility."
Avoid harsh language such as:
- "Your competitors are beating you."
- "You are weak."
- "You are losing customers."
- "You are behind."

## 7. Website and Contact Flow
Explain website/contact findings in practical language. Do not call a phone number WhatsApp unless a WhatsApp link/source was found. If something is not found in the lightweight snapshot, use: "Our lightweight website snapshot did not detect... This should be verified with a deeper website review."

## 8. Content and Offer Opportunities
Give niche-specific direction for content, proof, offers, local visibility, and buyer education. Keep this at the level of strategic themes and examples. Do not provide a complete content calendar, campaign structure, ad copy bank, or implementation checklist.

## 9. Suggested 30-Day Growth Sprint Roadmap
Frame this as a high-level 30-day Growth Sprint direction, not a free implementation plan.
Use this structure:
Week 1: Visibility, tracking, profile cleanup.
Week 2: Offer clarity, content direction, contact flow.
Week 3: Launch content/campaign experiments.
Week 4: Review signals and plan improvements.
For each week, give 1-2 outcome-focused bullets only. Avoid detailed how-to steps, exact scripts, exact campaign setup, or reusable internal processes.

## 10. Tracking and Measurement Notes
Explain what can be tracked and what needs access. Mention Google Business Profile, website analytics, call/WhatsApp clicks, forms, ad accounts, and booking/contact data only as applicable.

## 11. Recommended Next Step
Recommend either:
- "Book a Growth Sprint discussion with GrowingMonk"
- "Start with a 30-Day Growth Sprint."

## 12. Limitations
Include this exact sentence:
"This due diligence report is based on publicly available information and limited technical checks. Full performance analysis requires access to Google Business Profile, website analytics, ad accounts, and booking/contact data."

Rules:
- Do not invent facts.
- Separate verified public data from inferred opportunities.
- Do not claim revenue, bookings, or exact lead loss unless provided.
- Do not call a phone number WhatsApp unless WhatsApp link/source is found.
- Do not claim private analytics unless GA4/Search Console access is provided.
- Include numbers and simple Markdown tables where the JSON supports them.
- Remember this is for a lead/prospect, not an onboarded client.
- Include: verified snapshot, positives, visible opportunities, business impact, high-level roadmap, access needed, next step.
- Avoid: internal warnings, sales objections, outreach scripts, detailed implementation playbook, pricing strategy, exact ad setup, full content calendar, aggressive competitor language, or anything that sounds like a diagnosis from private analytics.
- Avoid these phrases: "You are behind", "You are losing customers", "Your competitors are beating you", "significantly boost", "guaranteed", and "capture a larger share" unless heavily qualified and careful.
- Prefer: "There is an opportunity", "may influence customer trust", "can help improve clarity", "should be verified", and "based on public data".
- Make the report specific to the business.
- Keep the tone helpful, premium, practical, careful, and not aggressive.
""".strip()


def build_sales_call_brief_prompt(data: dict[str, Any]) -> str:
    research_json, business_name = _research_context(data)
    structure_context = _research_structure_context(data)

    return f"""
You are preparing a concise internal sales call brief for GrowingMonk.

Use only the provided data. Be specific, practical, and honest. Do not invent private analytics, bookings, revenue, or WhatsApp activity.

{structure_context}

Research data:
```json
{research_json}
```

Generate a Markdown brief with this exact structure:

# {business_name} — Sales Call Brief

## Main Pitch Angle

## Why This Business Is Worth Contacting

## 5 Specific Talking Points
Include exact verified numbers where they help the salesperson, such as review count, competitor average, review gap, PageSpeed scores, contact findings, or structure-specific expansion/location/franchise questions.

## 5 Smart Questions to Ask the Owner

## Likely Objections & Responses
Give exactly 3 likely objections and concise responses.

## Recommended Offer
Recommend one:
- Free Growth Audit
- 30-Day Growth Sprint
- Monthly Growth System
- Tracking Setup First

## What Not To Claim Yet

Rules:
- Do not invent data.
- Use "verified" only for API/public-source data.
- Use "appears" for inferences.
- Do not guarantee results.
- Do not say revenue or bookings unless provided.
- Do not claim a phone number is WhatsApp unless a public WhatsApp link was found. If only a phone number is available, say it may be tested as a possible WhatsApp number.
- Never invent analytics.
- Never claim private Instagram inspection.
- Never claim WhatsApp is active unless a WhatsApp link/source is found.
- Never claim revenue impact unless provided.
- Include numbers and simple Markdown tables where the JSON supports them.
- Keep it concise, internal, sales-ready, specific, and practical.
- Target 1-2 pages. Do not include charts, competitor tables, outreach scripts, or long research summaries in this brief.
""".strip()


def build_deep_pitch_prompt(data: dict[str, Any]) -> str:
    return build_internal_sales_diligence_prompt(data)


def build_sales_brief_prompt(data: dict[str, Any]) -> str:
    return build_sales_call_brief_prompt(data)
