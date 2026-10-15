import unittest
from concurrent.futures import Executor, Future
from unittest.mock import patch

from seowebcrawler.models import CrawledPage, CrawlResult
from seowebcrawler.web import create_app


class DeferredExecutor(Executor):
    def submit(self, fn, /, *args, **kwargs):
        self.submitted = (fn, args, kwargs)
        return Future()


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.executor = DeferredExecutor()
        self.app = create_app(executor=self.executor)
        self.client = self.app.test_client()

    def test_dashboard_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SEO FIELDNOTES", response.data)
        self.assertIn(b"keywords-body", response.data)
        self.assertIn(b"external-body", response.data)

    def test_health_endpoint_reports_ready(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_scan_rejects_private_target(self):
        response = self.client.post("/api/scans", json={"url": "https://127.0.0.1/"})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Private or reserved", response.data)

    def test_valid_scan_is_queued_and_status_is_readable(self):
        response = self.client.post("/api/scans", json={"url": "https://93.184.216.34/"})
        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["id"]
        task, args, kwargs = self.executor.submitted
        crawl_result = CrawlResult(
            start_url="https://93.184.216.34/",
            pages=[CrawledPage("https://93.184.216.34/", 0, 200, "<title>Example</title>")],
            link_statuses={},
        )
        with patch("seowebcrawler.web.Crawler") as crawler_class:
            crawler_class.return_value.crawl.return_value = crawl_result
            task(*args, **kwargs)
        status = self.client.get(f"/api/scans/{job_id}")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["status"], "complete")
        csv_response = self.client.get(f"/api/scans/{job_id}/report.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(b"Example", csv_response.data)


if __name__ == "__main__":
    unittest.main()