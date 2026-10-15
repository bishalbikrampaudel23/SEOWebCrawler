"""Example Python API usage; no command-line arguments are evaluated."""

from seowebcrawler.analyzer import analyze_crawl
from seowebcrawler.config import CrawlerConfig
from seowebcrawler.crawler import Crawler
from seowebcrawler.reporting import to_json


def main() -> None:
    config = CrawlerConfig(max_depth=1, max_pages=25, rate_limit_seconds=1.0)
    result = Crawler(config).crawl("https://example.com/")
    report = analyze_crawl(result)
    print(to_json(report))


if __name__ == "__main__":
    main()