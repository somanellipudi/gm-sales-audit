from __future__ import annotations

from datetime import datetime, timezone


def make_source(title: str, url: str, source_type: str, snippet: str = "") -> dict:
    return {
        "title": title,
        "url": url,
        "source_type": source_type,
        "snippet": snippet,
        "found_at": datetime.now(timezone.utc).isoformat(),
    }


def dedupe_sources(sources: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for source in sources:
        key = (source.get("url", ""), source.get("source_type", ""), source.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def format_sources_markdown(sources: list[dict]) -> str:
    if not sources:
        return "No sources recorded."

    lines = []
    for source in dedupe_sources(sources):
        title = source.get("title") or "Source"
        url = source.get("url") or ""
        source_type = source.get("source_type") or "source"
        snippet = source.get("snippet") or ""
        if url:
            lines.append(f"- [{title}]({url}) ({source_type})")
        else:
            lines.append(f"- {title} ({source_type})")
        if snippet:
            lines.append(f"  - {snippet}")
    return "\n".join(lines)
