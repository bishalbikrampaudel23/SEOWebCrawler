"""JSON and CSV report serialization."""

from __future__ import annotations

import csv
import io
import json

from .models import SiteReport


def _safe_csv_cell(value: object) -> object:
    """Prefix formula-leading text so spreadsheet applications treat it as text."""
    if isinstance(value, str) and value.lstrip()[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def to_json(report: SiteReport) -> str:
    """Serialize a site report as readable JSON."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def to_csv(report: SiteReport) -> str:
    """Serialize one page per CSV row, with structured cells encoded as JSON."""
    output = io.StringIO(newline="")
    fields = [
        "url", "status_code", "seo_score", "title", "meta_description",
        "meta_keywords", "word_count", "keyword_frequencies", "keyword_density",
        "internal_links", "external_links", "broken_links", "images_total",
        "images_missing_alt", "error",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for page in report.pages:
        row = page.__dict__.copy()
        for key in (
            "meta_keywords", "keyword_frequencies", "keyword_density", "internal_links",
            "external_links", "broken_links", "headings",
        ):
            row[key] = json.dumps(row[key], ensure_ascii=False)
        writer.writerow(
            {key: _safe_csv_cell(row.get(key, "")) for key in fields}
        )
    return output.getvalue()