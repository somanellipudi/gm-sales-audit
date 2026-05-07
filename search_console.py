from __future__ import annotations

from datetime import date, timedelta


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _query(service, site_url: str, start_date: str, end_date: str, dimensions: list[str], row_limit: int = 10):
    body = {"startDate": start_date, "endDate": end_date, "dimensions": dimensions, "rowLimit": row_limit}
    return service.searchanalytics().query(siteUrl=site_url, body=body).execute()


def get_search_console_summary(site_url: str, days: int = 30) -> dict:
    if not site_url:
        return {"available": False, "reason": "No Search Console site URL provided."}

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    try:
        import google.auth
        from googleapiclient.discovery import build

        credentials, _ = google.auth.default(scopes=SCOPES)
        service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)

        query_data = _query(service, site_url, start_date.isoformat(), end_date.isoformat(), ["query"], 10)
        page_data = _query(service, site_url, start_date.isoformat(), end_date.isoformat(), ["page"], 10)
        device_data = _query(service, site_url, start_date.isoformat(), end_date.isoformat(), ["device"], 10)
        total_data = _query(service, site_url, start_date.isoformat(), end_date.isoformat(), [], 1)

        totals = total_data.get("rows", [{}])[0]
        return {
            "available": True,
            "site_url": site_url,
            "days": days,
            "total_clicks": totals.get("clicks", 0),
            "total_impressions": totals.get("impressions", 0),
            "avg_ctr": totals.get("ctr", 0),
            "avg_position": totals.get("position", 0),
            "top_queries": [
                {
                    "query": row.get("keys", [""])[0],
                    "clicks": row.get("clicks"),
                    "impressions": row.get("impressions"),
                    "ctr": row.get("ctr"),
                    "position": row.get("position"),
                }
                for row in query_data.get("rows", [])
            ],
            "top_pages": [
                {
                    "page": row.get("keys", [""])[0],
                    "clicks": row.get("clicks"),
                    "impressions": row.get("impressions"),
                    "ctr": row.get("ctr"),
                    "position": row.get("position"),
                }
                for row in page_data.get("rows", [])
            ],
            "device_summary": [
                {
                    "device": row.get("keys", [""])[0],
                    "clicks": row.get("clicks"),
                    "impressions": row.get("impressions"),
                }
                for row in device_data.get("rows", [])
            ],
            "error": None,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": "Search Console access failed. Confirm the authenticated account/service account has access to this Search Console property.",
            "details": str(exc),
        }
