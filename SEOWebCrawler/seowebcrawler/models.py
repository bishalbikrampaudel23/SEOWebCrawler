"""Typed data structures shared by the crawler and reporting layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class CrawledPage:
    url: str
    depth: int
    status_code: int | None
    html: str = ""
    error: str | None = None


@dataclass
class CrawlResult:
    start_url: str
    pages: list[CrawledPage] = field(default_factory=list)
    link_statuses: dict[str, int | None] = field(default_factory=dict)


@dataclass
class PageAnalysis:
    url: str
    status_code: int | None
    title: str
    meta_description: str
    meta_keywords: list[str]
    headings: list[str]
    word_count: int
    keyword_frequencies: dict[str, int]
    keyword_density: dict[str, float]
    internal_links: list[str]
    external_links: list[str]
    broken_links: list[dict[str, Any]]
    images_total: int
    images_missing_alt: int
    seo_score: int
    error: str | None = None


@dataclass
class SiteReport:
    start_url: str
    pages: list[PageAnalysis]
    link_statuses: dict[str, int | None]
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    @property
    def seo_score(self) -> int:
        """Return the mean SEO score for successful pages."""
        scored_pages = [page.seo_score for page in self.pages if page.status_code == 200]
        return round(sum(scored_pages) / len(scored_pages)) if scored_pages else 0

    @property
    def keyword_totals(self) -> dict[str, int]:
        """Aggregate page keyword counts and sort by descending frequency."""
        totals: dict[str, int] = {}
        for page in self.pages:
            for keyword, count in page.keyword_frequencies.items():
                totals[keyword] = totals.get(keyword, 0) + count
        return dict(sorted(totals.items(), key=lambda item: (-item[1], item[0])))

    def to_dict(self) -> dict[str, Any]:
        """Return the report and its aggregate values as JSON-compatible data."""
        result = asdict(self)
        result["seo_score"] = self.seo_score
        result["keyword_totals"] = self.keyword_totals
        return result