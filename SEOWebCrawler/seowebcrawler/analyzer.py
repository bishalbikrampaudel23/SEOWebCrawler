"""Extract on-page SEO signals from crawler results."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup
from nltk.stem.snowball import SnowballStemmer

from .models import CrawlResult, PageAnalysis, SiteReport

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{1,}")
_STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can", "could", "did", "do", "does", "for", "from", "had", "has", "have", "he", "her", "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "may", "me", "might", "more", "most", "my", "no", "nor", "not", "of", "on", "once", "only", "or", "other", "our", "ours", "out", "over", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "us", "very", "was", "we", "were", "what", "when", "where", "which", "who", "why", "will", "with", "would", "you", "your", "yours"]
)
_STEMMER = SnowballStemmer("english")


def _normalized_words(text: str) -> tuple[list[str], list[str]]:
    """Normalize text and return all words plus stopword-filtered stemmed keywords."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    tokens = _TOKEN_RE.findall(normalized)
    all_words = [_STEMMER.stem(token) for token in tokens]
    keywords = [_STEMMER.stem(token) for token in tokens if token not in _STOPWORDS]
    return all_words, keywords


def _seo_score(
    title: str,
    description: str,
    headings: list[str],
    word_count: int,
    image_count: int,
    missing_alt: int,
    internal_link_count: int,
    url: str,
) -> int:
    """Calculate the documented weighted on-page SEO heuristic."""
    score = 0
    score += 20 if 10 <= len(title) <= 60 else 10 if title else 0
    score += 20 if 70 <= len(description) <= 160 else 10 if description else 0
    h1_count = sum(1 for heading in headings if heading.startswith("h1:"))
    score += 15 if h1_count == 1 else 5 if h1_count > 1 else 0
    score += 20 if word_count >= 300 else 10 if word_count >= 100 else 0
    score += 10 if image_count == 0 or missing_alt == 0 else 5 if missing_alt < image_count else 0
    score += 10 if internal_link_count > 0 else 0
    score += 5 if urlsplit(url).scheme == "https" else 0
    return score


def analyze_page(
    url: str,
    status_code: int | None,
    html: str,
    link_statuses: dict[str, int | None] | None = None,
    error: str | None = None,
) -> PageAnalysis:
    """Analyze a page's metadata, keyword density, links, headings, and images."""
    link_statuses = link_statuses or {}
    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    descriptions = soup.find_all("meta", attrs={"name": re.compile("^description$", re.IGNORECASE)})
    description = str(descriptions[0].get("content", "")).strip() if descriptions else ""
    keyword_tags = soup.find_all("meta", attrs={"name": re.compile("^keywords$", re.IGNORECASE)})
    meta_keywords = [
        keyword.strip()
        for tag in keyword_tags
        for keyword in str(tag.get("content", "")).split(",")
        if keyword.strip()
    ]

    headings = [
        f"{heading.name}:{heading.get_text(' ', strip=True)}"
        for heading in soup.find_all(re.compile(r"^h[1-6]$"))
    ]
    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()
    all_words, keywords = _normalized_words(soup.get_text(" ", strip=True))
    frequencies = Counter(keywords)
    word_count = len(all_words)
    density = {
        keyword: round(count * 100 / word_count, 2)
        for keyword, count in frequencies.most_common()
    } if word_count else {}

    page_origin = (urlsplit(url).scheme, urlsplit(url).netloc.lower())
    internal_links: list[str] = []
    external_links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        target = urldefrag(urljoin(url, str(anchor["href"])))[0]
        target_parts = urlsplit(target)
        if target_parts.scheme not in {"http", "https"}:
            continue
        if (target_parts.scheme, target_parts.netloc.lower()) != page_origin:
            if target not in external_links:
                external_links.append(target)
        else:
            if target not in internal_links:
                internal_links.append(target)

    broken_links = [
        {"url": target, "status_code": status}
        for target, status in link_statuses.items()
        if status is not None and status >= 400
        and (target in internal_links or target in external_links)
    ]
    images = soup.find_all("img")
    missing_alt = sum(1 for image in images if not str(image.get("alt", "")).strip())
    score = _seo_score(
        title,
        description,
        headings,
        word_count,
        len(images),
        missing_alt,
        len(internal_links),
        url,
    ) if status_code == 200 else 0

    return PageAnalysis(
        url=url,
        status_code=status_code,
        title=title,
        meta_description=description,
        meta_keywords=meta_keywords,
        headings=headings,
        word_count=word_count,
        keyword_frequencies=dict(frequencies.most_common(50)),
        keyword_density={key: density[key] for key, _ in frequencies.most_common(50)},
        internal_links=internal_links,
        external_links=external_links,
        broken_links=broken_links,
        images_total=len(images),
        images_missing_alt=missing_alt,
        seo_score=score,
        error=error,
    )


def analyze_crawl(result: CrawlResult) -> SiteReport:
    """Convert all fetched pages into a serializable site report."""
    analyses = [
        analyze_page(page.url, page.status_code, page.html, result.link_statuses, page.error)
        for page in result.pages
    ]
    return SiteReport(result.start_url, analyses, result.link_statuses)