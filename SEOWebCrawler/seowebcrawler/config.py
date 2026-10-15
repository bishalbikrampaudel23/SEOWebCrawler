"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CrawlerConfig:
    max_depth: int = 2
    max_pages: int = 100
    timeout_seconds: float = 10.0
    retries: int = 2
    backoff_factor: float = 0.4
    rate_limit_seconds: float = 1.0
    max_workers: int = 4
    max_response_bytes: int = 2_000_000
    max_redirects: int = 5
    max_external_links: int = 30
    check_external_links: bool = True
    user_agent: str = "SEOWebCrawler/0.1 (+https://localhost/about)"

    def __post_init__(self) -> None:
        """Reject settings outside resource-safe supported ranges."""
        if not 0 <= self.max_depth <= 10:
            raise ValueError("max_depth must be between 0 and 10")
        if not 1 <= self.max_pages <= 10_000:
            raise ValueError("max_pages must be between 1 and 10000")
        if not 0.1 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 0.1 and 120")
        if not 0 <= self.retries <= 5:
            raise ValueError("retries must be between 0 and 5")
        if not 0 <= self.backoff_factor <= 10:
            raise ValueError("backoff_factor must be between 0 and 10")
        if not 0 <= self.rate_limit_seconds <= 60:
            raise ValueError("rate_limit_seconds must be between 0 and 60")
        if not 1 <= self.max_workers <= 32:
            raise ValueError("max_workers must be between 1 and 32")
        if not 1024 <= self.max_response_bytes <= 50_000_000:
            raise ValueError("max_response_bytes must be between 1024 and 50000000")
        if not 0 <= self.max_redirects <= 10:
            raise ValueError("max_redirects must be between 0 and 10")
        if not 0 <= self.max_external_links <= 500:
            raise ValueError("max_external_links must be between 0 and 500")
        if not self.user_agent.strip() or len(self.user_agent) > 200:
            raise ValueError("user_agent must contain 1 to 200 characters")


def load_config(path: str | Path) -> CrawlerConfig:
    """Load YAML or JSON settings, rejecting unknown keys and invalid values."""
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    suffix = config_path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ValueError("Configuration file must use .yaml, .yml, or .json")
    try:
        values: Any = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError("Configuration contains invalid YAML") from exc
    if not isinstance(values, dict):
        raise TypeError("Configuration must be a mapping of setting names to values")
    known_keys = set(asdict(CrawlerConfig()))
    unknown_keys = set(values) - known_keys
    if unknown_keys:
        raise ValueError(f"Unknown configuration settings: {', '.join(sorted(unknown_keys))}")
    return CrawlerConfig(**values)