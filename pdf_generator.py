from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF


ACCENT = (232, 119, 34)
DARK = (17, 24, 39)
TEXT = (35, 35, 35)
MUTED = (101, 111, 109)
ASSET_DIR = Path(__file__).resolve().parent / "assets"
LOGO_CANDIDATES = (
    ASSET_DIR / "growingmonk_logo.png",
    ASSET_DIR / "growingmonk_logo.jpg",
    ASSET_DIR / "growingmonk_logo.jpeg",
)
MAX_LINE_CHARS = 700
MAX_BLANK_LINES = 1
MAX_TOKEN_CHARS = 90


def sanitize_text(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2192": "->",
        "\u2022": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def normalize_markdown_for_pdf(markdown: str) -> list[str]:
    lines: list[str] = []
    in_code_block = False
    blank_count = 0

    for raw_line in markdown.splitlines():
        line = sanitize_text(raw_line).strip()

        if line.startswith("```") or line.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if not line:
            blank_count += 1
            if blank_count <= MAX_BLANK_LINES:
                lines.append("")
            continue
        blank_count = 0

        if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line):
            continue

        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        line = _soft_break_long_tokens(line)

        if len(line) > MAX_LINE_CHARS:
            line = f"{line[:MAX_LINE_CHARS].rstrip()}..."

        lines.append(line)

    return lines


def _soft_break_long_tokens(text: str) -> str:
    parts = []
    for token in text.split(" "):
        if len(token) <= MAX_TOKEN_CHARS:
            parts.append(token)
            continue
        chunks = [token[i : i + MAX_TOKEN_CHARS] for i in range(0, len(token), MAX_TOKEN_CHARS)]
        parts.append(" ".join(chunks))
    return " ".join(parts)


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return cleaned or "MonkAudit"


class AuditPDF(FPDF):
    def __init__(self, business_name: str, report_type: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.business_name = sanitize_text(business_name)
        self.report_type = sanitize_text(report_type)
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(15, 16, 15)

    def header(self) -> None:
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 25, "F")
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.35)
        self.line(15, 24.5, 195, 24.5)
        self._draw_brand_header()
        self.set_xy(128, 9)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(230, 230, 230)
        self.cell(67, 5, self.report_type, align="R")
        self.ln(23)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        footer_label = "Internal Sales Intelligence" if "Internal" in self.report_type or "Sales Call" in self.report_type else "Growth Due Diligence"
        self.cell(0, 6, f"GrowingMonk | {footer_label} | Page {self.page_no()}", align="C")

    def _draw_brand_header(self) -> None:
        logo_path = _logo_path()
        if logo_path:
            try:
                self.image(str(logo_path), x=14, y=4.5, w=68)
                return
            except Exception:
                pass

        self.set_xy(15, 5)
        self.set_fill_color(*ACCENT)
        self.ellipse(15, 6.2, 6, 6, "F")
        self.set_draw_color(*ACCENT)
        self.set_line_width(1.2)
        self.line(16, 15, 31, 7)
        self.line(31, 7, 29, 7)
        self.set_xy(25, 5.2)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 255, 255)
        self.cell(42, 6, "GrowingMonk", ln=1)
        self.set_x(25)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(200, 200, 200)
        self.cell(60, 4, "Digital Marketing & Growth Agency", ln=0)


def _logo_path() -> Path | None:
    for candidate in LOGO_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _write_wrapped(pdf: AuditPDF, text: str, font_size: int = 10, style: str = "", indent: int = 0, line_height: float = 5.2) -> None:
    pdf.set_font("Helvetica", style, font_size)
    pdf.set_text_color(*TEXT)
    if indent:
        pdf.set_x(pdf.l_margin + indent)
    width = pdf.w - pdf.l_margin - pdf.r_margin - indent
    text = sanitize_text(text)
    if len(text) > MAX_LINE_CHARS:
        text = f"{text[:MAX_LINE_CHARS].rstrip()}..."
    pdf.multi_cell(width, line_height, text, new_x="LMARGIN", new_y="NEXT")


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_label(value: Any, fallback: str = "N/A") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return sanitize_text(str(value))


def _truncate(text: Any, limit: int = 28) -> str:
    value = sanitize_text(str(text or "N/A"))
    return value if len(value) <= limit else f"{value[: limit - 3].rstrip()}..."


def _draw_section_title(pdf: AuditPDF, title: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*ACCENT)
    pdf.multi_cell(0, 7, sanitize_text(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _draw_metric_box(pdf: AuditPDF, x: float, y: float, w: float, label: str, value: Any) -> None:
    pdf.set_fill_color(248, 248, 248)
    pdf.set_draw_color(220, 220, 220)
    pdf.rect(x, y, w, 20, "DF")
    pdf.set_xy(x + 3, y + 3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(95, 95, 95)
    pdf.cell(w - 6, 4, sanitize_text(label), ln=1)
    pdf.set_x(x + 3)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK)
    pdf.cell(w - 6, 8, _metric_label(value), ln=0)


def _draw_bar_chart(pdf: AuditPDF, title: str, rows: list[tuple[str, float]], max_value: float | None = None) -> None:
    if not rows:
        return
    if pdf.get_y() > 225:
        pdf.add_page()

    _draw_section_title(pdf, title)
    chart_x = pdf.l_margin
    label_w = 50
    bar_x = chart_x + label_w
    bar_w = pdf.w - pdf.l_margin - pdf.r_margin - label_w - 14
    row_h = 8
    max_value = max_value or max(value for _, value in rows) or 1

    for label, value in rows:
        if pdf.get_y() > 260:
            pdf.add_page()
            _draw_section_title(pdf, title)
        y = pdf.get_y()
        pdf.set_xy(chart_x, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*TEXT)
        pdf.cell(label_w - 2, row_h, _truncate(label), ln=0)
        pdf.set_fill_color(235, 235, 235)
        pdf.rect(bar_x, y + 1.8, bar_w, 4, "F")
        pdf.set_fill_color(*ACCENT)
        filled = 0 if max_value <= 0 else max(0, min(bar_w, bar_w * (value / max_value)))
        pdf.rect(bar_x, y + 1.8, filled, 4, "F")
        pdf.set_xy(bar_x + bar_w + 2, y)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*DARK)
        pdf.cell(12, row_h, _metric_label(value), ln=1)
    pdf.ln(2)


def _draw_simple_table(pdf: AuditPDF, title: str, headers: list[str], rows: list[list[Any]]) -> None:
    if not rows:
        return
    if pdf.get_y() > 220 or (len(rows) > 4 and pdf.get_y() > 180):
        pdf.add_page()

    if title:
        _draw_section_title(pdf, title)
    width = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = width / len(headers)
    row_h = 7

    pdf.set_fill_color(*DARK)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for header in headers:
        pdf.cell(col_w, row_h, _truncate(header, 18), border=1, align="C", fill=True)
    pdf.ln(row_h)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*TEXT)
    for row in rows[:8]:
        if pdf.get_y() > 260:
            pdf.add_page()
        for cell in row:
            pdf.cell(col_w, row_h, _truncate(cell, 22), border=1)
        pdf.ln(row_h)
    pdf.ln(2)


def _is_table_row(line: str) -> bool:
    return "|" in line and line.count("|") >= 2 and not re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line)


def _parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip("|").split("|")]


def _draw_markdown_table(pdf: AuditPDF, table_lines: list[str]) -> None:
    rows = [_parse_table_row(line) for line in table_lines if _is_table_row(line)]
    if not rows:
        return
    headers = rows[0]
    body = rows[1:] or [["" for _ in headers]]
    _draw_simple_table(pdf, "", headers, body)


def _draw_cover_intro(pdf: AuditPDF, business_name: str, report_type: str) -> None:
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(0, 9, sanitize_text(report_type), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*ACCENT)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 7, sanitize_text(business_name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.7)
    y = pdf.get_y() + 1
    pdf.line(pdf.l_margin, y, pdf.l_margin + 52, y)
    pdf.set_y(y + 4)
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1)
    pdf.ln(3)


def _visual_summary_available(research_data: dict[str, Any] | None) -> bool:
    if not research_data:
        return False
    pagespeed = research_data.get("pagespeed", {})
    business = research_data.get("business", {})
    competitors = research_data.get("competitor_analysis", {}).get("competitor_table_data", [])
    return bool(
        business.get("rating")
        or business.get("user_ratings_total")
        or competitors
        or any(pagespeed.get(key) is not None for key in ("performance_score", "accessibility_score", "best_practices_score", "seo_score"))
    )


def _draw_visual_summary(pdf: AuditPDF, research_data: dict[str, Any] | None) -> None:
    if not _visual_summary_available(research_data):
        return

    research_data = research_data or {}
    business = research_data.get("business", {})
    pagespeed = research_data.get("pagespeed", {})
    review_position = research_data.get("competitor_analysis", {}).get("review_position", {})
    competitors = research_data.get("competitor_analysis", {}).get("competitor_table_data", [])

    _draw_section_title(pdf, "Numbers & Graphs")
    x = pdf.l_margin
    y = pdf.get_y()
    gap = 4
    box_w = (pdf.w - pdf.l_margin - pdf.r_margin - (gap * 3)) / 4
    _draw_metric_box(pdf, x, y, box_w, "Google rating", business.get("rating"))
    _draw_metric_box(pdf, x + box_w + gap, y, box_w, "Google reviews", business.get("user_ratings_total") or 0)
    _draw_metric_box(pdf, x + (box_w + gap) * 2, y, box_w, "Avg competitor reviews", review_position.get("avg_competitor_review_count"))
    _draw_metric_box(pdf, x + (box_w + gap) * 3, y, box_w, "Review gap vs top", review_position.get("review_volume_gap_vs_top"))
    pdf.set_y(y + 24)

    score_rows: list[tuple[str, float]] = []
    for label, key in (
        ("Performance", "performance_score"),
        ("Accessibility", "accessibility_score"),
        ("Best practices", "best_practices_score"),
        ("SEO", "seo_score"),
    ):
        value = _number(pagespeed.get(key))
        if value is not None:
            score_rows.append((label, value))
    _draw_bar_chart(pdf, "PageSpeed Score Overview", score_rows, max_value=100)

    review_rows: list[tuple[str, float]] = []
    prospect_name = business.get("name") or research_data.get("final_data_used", {}).get("business_name") or "Prospect"
    prospect_reviews = _number(business.get("user_ratings_total"))
    if prospect_reviews is not None:
        review_rows.append((prospect_name, prospect_reviews))
    for competitor in competitors[:8]:
        reviews = _number(competitor.get("review_count"))
        if reviews is not None:
            review_rows.append((competitor.get("name") or "Competitor", reviews))
    _draw_bar_chart(pdf, "Visible Google Review Volume Comparison", review_rows)

    table_rows = [
        [
            prospect_name,
            business.get("rating") or "N/A",
            business.get("user_ratings_total") or 0,
        ]
    ]
    for competitor in competitors[:6]:
        table_rows.append(
            [
                competitor.get("name") or "Competitor",
                competitor.get("rating") or "N/A",
                competitor.get("review_count") or 0,
            ]
        )
    _draw_simple_table(pdf, "Review Comparison Table", ["Business", "Rating", "Reviews"], table_rows)

    _write_wrapped(
        pdf,
        "Note: Charts use available public or permitted client-access data only. Missing values are not estimated.",
        font_size=8,
        style="I",
        line_height=4.4,
    )
    pdf.ln(2)


def markdown_to_pdf(
    report_markdown: str,
    business_name: str,
    report_type: str,
    research_data: dict[str, Any] | None = None,
    include_charts: bool = False,
) -> bytes:
    pdf = AuditPDF(business_name=business_name, report_type=report_type)
    pdf.add_page()
    _draw_cover_intro(pdf, business_name, report_type)

    lines = normalize_markdown_for_pdf(report_markdown)
    charts_drawn = False
    h2_count = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        if _is_table_row(line):
            table_lines = []
            while index < len(lines) and (_is_table_row(lines[index]) or re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", lines[index])):
                if _is_table_row(lines[index]):
                    table_lines.append(lines[index])
                index += 1
            _draw_markdown_table(pdf, table_lines)
            continue

        if not line:
            pdf.ln(1.2)
            index += 1
            continue
        if line.startswith("# "):
            index += 1
            continue
        elif line.startswith("## "):
            h2_count += 1
            if include_charts and not charts_drawn and h2_count == 2:
                _draw_visual_summary(pdf, research_data)
                charts_drawn = True
            if pdf.get_y() > 246:
                pdf.add_page()
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(*ACCENT)
            pdf.multi_cell(0, 7, line[3:].strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.8)
        elif line.startswith("### "):
            pdf.ln(1.5)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 6, line[4:].strip(), new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("- "):
            _write_wrapped(pdf, f"- {line[2:].strip()}", font_size=10, indent=4, line_height=5)
        else:
            _write_wrapped(pdf, line, font_size=10, line_height=5.8)
        index += 1

    if include_charts and not charts_drawn:
        _draw_visual_summary(pdf, research_data)

    output = pdf.output(dest="S")
    if isinstance(output, bytearray):
        return bytes(output)
    if isinstance(output, str):
        return output.encode("latin-1")
    return bytes(output)


def generate_audit_pdf(
    report_markdown: str,
    business_name: str,
    report_type: str = "MonkAudit Report",
    research_data: dict[str, Any] | None = None,
    include_charts: bool = False,
) -> bytes:
    return markdown_to_pdf(report_markdown, business_name, report_type, research_data, include_charts)
