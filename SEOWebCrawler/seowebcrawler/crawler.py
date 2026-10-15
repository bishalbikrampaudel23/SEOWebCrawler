"""Robots-aware, bounded website crawler with SSRF defenses."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .config import CrawlerConfig
from .models import CrawledPage, CrawlResult
from .security import UnsafeTargetError, validate_target_url

LOGGER = logging.getLogger(__name__)


class _HostRateLimiter:
    def __init__(self, delay: float) -> None:
        """Initialize a synchronized per-host request interval."""
        self.delay = delay
        self._lock = threading.Lock()
        self._next_request: dict[str, float] = {}

    def wait(self, url: str) -> None:
        """Wait until this host's next scheduled request time."""
        host = urlsplit(url).netloc.lower()
        with self._lock:
            now = time.monotonic()
            scheduled = max(now, self._next_request.get(host, now))
            self._next_request[host] = scheduled + self.delay
        wait_seconds = scheduled - time.monotonic()
        if wait_seconds > 0:
            time.sleep(wait_seconds)


class Crawler:
    """Fetch a bounded set of pages while respecting robots.txt and host pacing."""

    def __init__(self, config: CrawlerConfig | None = None) -> None:
        """Create isolated crawler state and thread-local HTTP sessions."""
        self.config = config or CrawlerConfig()
        self._rate_limiter = _HostRateLimiter(self.config.rate_limit_seconds)
        self._thread_local = threading.local()
        self._robots_lock = threading.Lock()
        self._robots: dict[str, RobotFileParser] = {}

    def _session(self) -> requests.Session:
        """Return the current thread's proxy-independent HTTP session."""
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.trust_env = False
            session.headers.update({"User-Agent": self.config.user_agent})
            self._thread_local.session = session
        return session

    def _request(
        self, method: str, url: str, *, check_robots: bool = True
    ) -> requests.Response | None:
        """Issue a bounded request with validated redirects and retry policy."""
        current_url = validate_target_url(url)
        for redirect_count in range(self.config.max_redirects + 1):
            if check_robots and not self._allowed_by_robots(current_url):
                return None
            response: requests.Response | None = None
            for attempt in range(self.config.retries + 1):
                self._rate_limiter.wait(current_url)
                try:
                    response = self._session().request(
                        method,
                        current_url,
                        allow_redirects=False,
                        stream=True,
                        timeout=(min(5.0, self.config.timeout_seconds), self.config.timeout_seconds),
                        verify=True,
                    )
                except requests.exceptions.SSLError:
                    LOGGER.warning("TLS verification failed for %s", current_url)
                    return None
                except requests.RequestException as exc:
                    LOGGER.info("Request failed for %s: %s", current_url, exc)
                    if attempt < self.config.retries:
                        time.sleep(self.config.backoff_factor * (2**attempt))
                        continue
                    return None

                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                if attempt >= self.config.retries:
                    break
                retry_after = response.headers.get("Retry-After", "")
                response.close()
                try:
                    delay = min(float(retry_after), 30.0)
                except ValueError:
                    delay = self.config.backoff_factor * (2**attempt)
                time.sleep(max(delay, 0))

            if response is None:
                return None
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location or redirect_count >= self.config.max_redirects:
                    return None
                try:
                    current_url = validate_target_url(urljoin(current_url, location))
                except UnsafeTargetError as exc:
                    LOGGER.warning("Rejected redirect from %s: %s", url, exc)
                    return None
                continue
            return response
        return None

    def _allowed_by_robots(self, url: str) -> bool:
        """Check the cached origin policy, failing closed when robots cannot be read."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._robots_lock:
            parser = self._robots.get(origin)
            if parser is None:
                parser = RobotFileParser()
                robots_url = f"{origin}/robots.txt"
                response = self._request("GET", robots_url, check_robots=False)
                if response is None:
                    parser.disallow_all = True
                else:
                    try:
                        if response.status_code in {401, 403} or response.status_code >= 500:
                            parser.disallow_all = True
                        elif response.status_code >= 400:
                            parser.allow_all = True
                        else:
                            try:
                                body = self._read_body(response)
                                parser.parse(body.decode("utf-8", errors="replace").splitlines())
                            except ValueError as exc:
                                LOGGER.warning(
                                    "Could not safely parse robots.txt at %s: %s",
                                    robots_url,
                                    exc,
                                )
                                parser.disallow_all = True
                    finally:
                        response.close()
                self._robots[origin] = parser
        try:
            return parser.can_fetch(self.config.user_agent, url)
        except (ValueError, UnicodeError):
            return False

    def _read_body(self, response: requests.Response) -> bytes:
        """Read a streamed response while enforcing the configured byte limit."""
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.config.max_response_bytes:
                    raise ValueError("Response exceeds configured size limit")
            except ValueError as exc:
                if str(exc) == "Response exceeds configured size limit":
                    raise
        body = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            body.extend(chunk)
            if len(body) > self.config.max_response_bytes:
                raise ValueError("Response exceeds configured size limit")
        return bytes(body)

    def _fetch_page(self, url: str, depth: int) -> CrawledPage:
        """Fetch and decode one HTML page, converting failures into page records."""
        try:
            response = self._request("GET", url)
            if response is None:
                return CrawledPage(url, depth, None, error="Request blocked or failed")
            try:
                status = response.status_code
                if status != 200:
                    return CrawledPage(url, depth, status, error=f"HTTP {status}")
                content_type = response.headers.get("Content-Type", "").lower()
                if content_type and "html" not in content_type:
                    return CrawledPage(url, depth, status, error="Response is not HTML")
                body = self._read_body(response)
                return CrawledPage(
                    response.url or url,
                    depth,
                    status,
                    body.decode(response.encoding or "utf-8", errors="replace"),
                )
            finally:
                response.close()
        except (UnsafeTargetError, ValueError, requests.RequestException) as exc:
            LOGGER.info("Could not crawl %s: %s", url, exc)
            return CrawledPage(url, depth, None, error=str(exc))

    @staticmethod
    def _links(page: CrawledPage) -> list[str]:
        """Extract unique, validated HTTP(S) links from a page."""
        soup = BeautifulSoup(page.html, "html.parser")
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            candidate = urljoin(page.url, str(anchor["href"]))
            try:
                normalized = validate_target_url(candidate)
            except UnsafeTargetError:
                continue
            if normalized not in links:
                links.append(normalized)
        return links

    def _check_link(self, url: str) -> int | None:
        """Check a link status without following unsafe or disallowed targets."""
        try:
            normalized = validate_target_url(url)
            if not self._allowed_by_robots(normalized):
                return None
            response = self._request("HEAD", normalized)
            if response is None:
                return None
            try:
                if response.status_code in {405, 501}:
                    response.close()
                    response = self._request("GET", normalized)
                    if response is None:
                        return None
                return response.status_code
            finally:
                response.close()
        except (UnsafeTargetError, ValueError, requests.RequestException):
            return None

    def crawl(self, start_url: str) -> CrawlResult:
        """Crawl same-origin HTML pages up to configured depth/page limits."""
        normalized_start = validate_target_url(start_url)
        root = urlsplit(normalized_start)
        root_origin = (root.scheme, root.netloc.lower())
        result = CrawlResult(start_url=normalized_start)
        visited = {normalized_start}
        frontier = [(normalized_start, 0)]
        discovered_links: set[str] = set()

        while frontier and len(result.pages) < self.config.max_pages:
            remaining = self.config.max_pages - len(result.pages)
            batch = frontier[:remaining]
            frontier = frontier[remaining:]
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {
                    executor.submit(self._fetch_page, url, depth): (url, depth)
                    for url, depth in batch
                }
                for future in as_completed(futures):
                    page = future.result()
                    result.pages.append(page)
                    if page.status_code != 200:
                        continue
                    for link in self._links(page):
                        discovered_links.add(link)
                        parts = urlsplit(link)
                        if (parts.scheme, parts.netloc.lower()) != root_origin:
                            continue
                        if page.depth < self.config.max_depth and link not in visited:
                            visited.add(link)
                            frontier.append((link, page.depth + 1))

        for page in result.pages:
            if page.status_code is not None:
                result.link_statuses[page.url] = page.status_code

        if self.config.check_external_links and self.config.max_external_links:
            external = []
            for link in sorted(discovered_links):
                parts = urlsplit(link)
                if (parts.scheme, parts.netloc.lower()) != root_origin:
                    external.append(link)
            external = external[: self.config.max_external_links]
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {executor.submit(self._check_link, url): url for url in external}
                for future in as_completed(futures):
                    result.link_statuses[futures[future]] = future.result()

        result.pages.sort(key=lambda page: (page.depth, page.url))
        return result