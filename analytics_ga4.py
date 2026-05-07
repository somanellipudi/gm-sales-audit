from __future__ import annotations

from datetime import date, timedelta


def get_ga4_summary(property_id: str, days: int = 30) -> dict:
    if not property_id:
        return {"available": False, "reason": "No GA4 property ID provided."}

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    except ImportError as exc:
        return {"available": False, "error": f"GA4 library is not installed: {exc}"}

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    try:
        client = BetaAnalyticsDataClient()
        summary_request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="newUsers"),
                Metric(name="eventCount"),
            ],
        )
        summary = client.run_report(summary_request)
        values = summary.rows[0].metric_values if summary.rows else []
        key_events = None
        try:
            key_event_request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
                metrics=[Metric(name="keyEvents")],
            )
            key_event_response = client.run_report(key_event_request)
            key_events = key_event_response.rows[0].metric_values[0].value if key_event_response.rows else None
        except Exception:
            key_events = None

        pages_request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews")],
            limit=10,
        )
        pages = client.run_report(pages_request)

        channels_request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            limit=10,
        )
        channels = client.run_report(channels_request)

        return {
            "available": True,
            "property_id": property_id,
            "days": days,
            "active_users": values[0].value if len(values) > 0 else None,
            "sessions": values[1].value if len(values) > 1 else None,
            "new_users": values[2].value if len(values) > 2 else None,
            "event_count": values[3].value if len(values) > 3 else None,
            "key_events": key_events,
            "top_pages": [
                {"page": row.dimension_values[0].value, "views": row.metric_values[0].value}
                for row in pages.rows
            ],
            "traffic_channels": [
                {"channel": row.dimension_values[0].value, "sessions": row.metric_values[0].value}
                for row in channels.rows
            ],
            "error": None,
        }
    except Exception as exc:
        return {
            "available": False,
            "error": "GA4 access failed. Confirm the authenticated account/service account has access to this GA4 property.",
            "details": str(exc),
        }
