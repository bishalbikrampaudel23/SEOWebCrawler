# SEO Web Crawler

A bounded, robots-aware SEO analyzer for authorized HTTPS websites. It reports page metadata, stemmed keyword frequencies and density, internal/external links, checked broken links, image alt coverage, and a heuristic SEO score. It includes a CLI, JSON/CSV exports, an optional Flask dashboard, and Python API.

## Requirements

- Python 3.11 or newer
- Network access to the authorized target site
- Docker is optional

## Local installation

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## CLI usage

```powershell
seo-analyze https://example.com --config config.example.yaml --format json --output report.json
seo-analyze https://example.com --format csv --output report.csv
python -m seowebcrawler https://example.com --verbose
```

Without `--output`, the report is written to stdout. `--format` accepts `json` or `csv`. A target must use HTTPS and resolve only to public IP addresses. Only same-origin pages are crawled.

## Dashboard

For local use, run:

```powershell
python -c "from seowebcrawler.web import create_app; create_app().run(host='127.0.0.1', port=5000, debug=False)"
```

Open `http://127.0.0.1:5000`. Scan jobs are asynchronous, limited to two concurrent jobs per process, retained in process memory, and can be exported as CSV. For a server process, install `requirements-server.txt`, then run:

```powershell
gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 4 --timeout 180 "seowebcrawler.web:create_app()"
```

Put an authenticated reverse proxy and TLS termination in front of any remotely reachable dashboard. The built-in dashboard has no user authentication and its job queue is in-memory; it is intended for trusted/local deployments, not direct public exposure or multi-worker scaling.

## Configuration

Copy `config.example.yaml` and tune crawl depth, page count, timeout/retries, per-host delay, worker count, response-size limit, redirects, and external-link check cap. JSON configuration is also supported. Unknown keys and out-of-range values fail closed. Use a descriptive user-agent and publish a contact/policy page for the crawler.

## Python API

```python
from seowebcrawler.analyzer import analyze_crawl
from seowebcrawler.config import CrawlerConfig
from seowebcrawler.crawler import Crawler
from seowebcrawler.reporting import to_json

config = CrawlerConfig(max_depth=1, max_pages=25)
result = Crawler(config).crawl("https://example.com/")
report = analyze_crawl(result)
print(to_json(report))
```

See `examples/analyze_site.py` and the Sphinx API docs in `docs/`.

## Tests and docs

```powershell
python -m pytest -q
python -m sphinx -b html docs docs/_build/html
```

Tests mock HTTP responses and do not crawl public websites. The docs include the architecture/implementation plan, module boundaries, score explanation, scaling recommendations, and screenshot capture guidance.

## Docker

```powershell
docker build -t seo-web-crawler .
docker run --rm -p 127.0.0.1:8000:8000 seo-web-crawler
```

The image runs as a non-root user. Access the dashboard at `http://127.0.0.1:8000`. Keep it bound to loopback unless protected by an authenticated reverse proxy. Container networking should deny private, loopback, link-local, and metadata-service egress; application DNS checks are not a substitute for an egress firewall.

## Security notes

- HTTPS-only URLs, certificate verification, no embedded credentials, standard ports only, hostname/IP checks, redirect revalidation, and disabled ambient proxy settings.
- Rejects private/reserved IP literals and hostnames resolving to any non-public address. Network egress should also be restricted at the host/container firewall to mitigate DNS rebinding and deployment-specific routing.
- Robots.txt is cached per origin for one crawl; an unavailable/forbidden robots file blocks crawling. Link checks are capped, paced, and robots-aware.
- Timeouts, retries, depth/page limits, response-byte limits, redirect limits, and worker caps limit resource use. These limits do not protect against every hostile origin or parser-level denial of service; run in a resource-limited container.
- The dashboard does not execute shell commands, evaluate input, or write crawl-derived paths. Its HTTP API is unauthenticated and should only be exposed locally or behind authentication.
- CSV exports prefix spreadsheet-formula-leading text with an apostrophe to prevent crawled content from being evaluated as a formula.
- Use only on sites you own or have permission to analyze. Comply with site terms, applicable law, and robots policy.

## Heuristic score

Each successful page receives up to 100 points: title length (20), description length (20), exactly one H1 (15), at least 300 normalized words (20), image alt coverage (10), at least one internal link (10), and HTTPS (5). The site score is the mean of successful page scores. It is an audit aid, not a search-ranking guarantee.