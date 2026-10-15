import unittest
from unittest.mock import Mock, patch
from urllib.robotparser import RobotFileParser

import requests

from seowebcrawler.config import CrawlerConfig
from seowebcrawler.crawler import Crawler
from seowebcrawler.models import CrawledPage


class CrawlerTests(unittest.TestCase):
    def test_crawl_respects_depth_limit_and_deduplicates_urls(self):
        config = CrawlerConfig(max_depth=1, max_pages=5, rate_limit_seconds=0, check_external_links=False)
        crawler = Crawler(config)

        def fetch(url, depth):
            return CrawledPage(url=url, depth=depth, status_code=200, html="<html></html>")

        def links(page):
            if page.url.endswith("/a"):
                return ["https://example.com/", "https://example.com/a"]
            return ["https://example.com/a", "https://example.com/a"]

        address = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch("seowebcrawler.security.socket.getaddrinfo", return_value=address), \
                patch.object(crawler, "_allowed_by_robots", return_value=True), \
                patch.object(crawler, "_fetch_page", side_effect=fetch), \
                patch.object(crawler, "_links", side_effect=links):
            result = crawler.crawl("https://example.com/")

        self.assertEqual({page.url for page in result.pages}, {"https://example.com/", "https://example.com/a"})
        self.assertEqual(len(result.pages), 2)

    def test_private_redirect_is_rejected_before_a_second_request(self):
        crawler = Crawler(CrawlerConfig(retries=0, rate_limit_seconds=0))
        redirect = requests.Response()
        redirect.status_code = 302
        redirect.headers["Location"] = "https://127.0.0.1/admin"
        redirect.close = Mock()
        session = Mock()
        session.request.return_value = redirect
        address = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch("seowebcrawler.security.socket.getaddrinfo", return_value=address), \
                patch.object(crawler, "_allowed_by_robots", return_value=True), \
                patch.object(crawler, "_session", return_value=session):
            response = crawler._request("GET", "https://example.com/")

        self.assertIsNone(response)
        session.request.assert_called_once()
        redirect.close.assert_called_once()

    def test_robots_disallow_rule_is_respected(self):
        crawler = Crawler()
        parser = RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /private"])
        crawler._robots["https://example.com"] = parser
        self.assertFalse(crawler._allowed_by_robots("https://example.com/private/data"))
        self.assertTrue(crawler._allowed_by_robots("https://example.com/public"))

    def test_response_body_limit_is_enforced(self):
        crawler = Crawler(CrawlerConfig(max_response_bytes=1024))
        response = Mock()
        response.headers = {}
        response.iter_content.return_value = [b"x" * 1025]
        with self.assertRaisesRegex(ValueError, "size limit"):
            crawler._read_body(response)

    def test_oversized_robots_file_fails_closed(self):
        crawler = Crawler()
        response = Mock()
        response.status_code = 200
        response.close = Mock()
        with patch.object(crawler, "_request", return_value=response), \
                patch.object(crawler, "_read_body", side_effect=ValueError("size limit")):
            self.assertFalse(crawler._allowed_by_robots("https://example.com/page"))
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()