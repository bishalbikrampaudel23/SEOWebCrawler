Architecture and Implementation Plan
====================================

Step-by-step plan
-----------------

1. Define report types and validated runtime settings so modules share a stable contract.
2. Add URL safety checks, robots policy, bounded redirects, retries, response limits, pacing, and crawl-local deduplication.
3. Parse successful HTML into metadata, stopword-filtered/stemmed keyword counts and density, link inventories, and image-alt findings.
4. Add JSON/CSV serializers and the CLI around the reusable crawl/analyze pipeline.
5. Add the optional asynchronous Flask dashboard and a bounded, mockable job interface.
6. Verify security boundaries and outputs with deterministic mocked unit/integration tests.
7. Package the tool, document local/Docker deployment, and scale out via durable jobs, shared caching, and network egress controls when needed.

Request flow
------------

1. Validate and normalize an HTTPS target, resolving every hostname and rejecting private or reserved addresses.
2. Fetch robots.txt once per origin. A robots fetch failure is treated as disallow-all; 4xx other than 401/403 means no published rules.
3. Run a breadth-first crawl with page/depth caps, per-host pacing, timeout/retry limits, response byte limits, and manually revalidated redirects.
4. Parse HTML and calculate metadata, stemmed keyword frequencies/density, links, image-alt coverage, and a heuristic score.
5. Serialize the report as JSON or CSV, or expose it through the optional local Flask dashboard.

Module boundaries
-----------------

* ``security.py``: URL validation and network-target restrictions.
* ``config.py``: strict YAML/JSON parsing and settings bounds.
* ``crawler.py``: HTTP, robots policy, crawl queue, retry/pacing and link checks.
* ``analyzer.py``: HTML parsing and scoring; no network access.
* ``models.py`` / ``reporting.py``: report schema and output encoding.
* ``cli.py`` / ``web.py``: user interfaces; both reuse the same core pipeline.

Scaling path
------------

The current thread pool is intentionally capped and the visited set is crawl-local. For larger jobs, use a durable queue (for example Celery with Redis), persist jobs and reports in a database/object store, add a shared rate-limit coordinator by origin, and use a distributed cache with explicit TTL and robots-policy invalidation. Keep per-origin concurrency low and enforce outbound network policy at the container/firewall layer. Add a conditional-request cache (``ETag``/``Last-Modified``) only after defining freshness and privacy requirements. Competitor comparison can be added as a separate report operation over two ``SiteReport`` values.

Limits and score
----------------

The SEO score is a transparent heuristic, not a search-engine ranking prediction. It rewards title/description lengths, one H1, content length, image alt coverage, internal links, and HTTPS. Link checks are capped and do not run against robots-disallowed targets; status ``null`` means the target could not safely or reliably be checked. Only same-origin HTML pages are crawled.

Screenshot capture
------------------

Run the dashboard locally and capture the audit-entry or synthetic report view with your browser's screenshot command. Do not commit screenshots containing private URLs or page content without permission.