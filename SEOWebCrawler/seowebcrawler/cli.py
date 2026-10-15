"""Command-line entry point for crawling and exporting SEO reports."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .analyzer import analyze_crawl
from .config import CrawlerConfig, load_config
from .crawler import Crawler
from .reporting import to_csv, to_json
from .security import UnsafeTargetError

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Crawl a website and report SEO signals.")
    parser.add_argument("url", help="HTTPS website URL to analyze")
    parser.add_argument("--config", help="YAML or JSON crawler configuration")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", help="Output path; defaults to standard output")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a crawl and write a JSON or CSV report."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = load_config(args.config) if args.config else CrawlerConfig()
        report = analyze_crawl(Crawler(config).crawl(args.url))
        rendered = to_json(report) if args.format == "json" else to_csv(report)
        if args.output:
            Path(args.output).expanduser().write_text(rendered + ("\n" if args.format == "json" else ""), encoding="utf-8")
        else:
            sys.stdout.write(rendered)
            if args.format == "json":
                sys.stdout.write("\n")
        return 0
    except (UnsafeTargetError, ValueError, OSError) as exc:
        LOGGER.error("Could not create report: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())