import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from seowebcrawler.config import CrawlerConfig
from seowebcrawler.models import CrawledPage, CrawlResult
from seowebcrawler.security import UnsafeTargetError


class CliTests(unittest.TestCase):
    def crawl_result(self):
        return CrawlResult(
            start_url="https://example.com/",
            pages=[
                CrawledPage(
                    url="https://example.com/",
                    depth=0,
                    status_code=200,
                    html="<title>Example</title><h1>Home</h1>",
                )
            ],
        )

    def test_json_report_is_written_to_stdout_by_default(self):
        stdout = io.StringIO()
        with (
            patch("seowebcrawler.cli.Crawler") as crawler_class,
            contextlib.redirect_stdout(stdout),
        ):
            crawler_class.return_value.crawl.return_value = self.crawl_result()

            from seowebcrawler.cli import main

            exit_code = main(["https://example.com/"])

        document = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(document["start_url"], "https://example.com/")
        self.assertEqual(document["pages"][0]["title"], "Example")
        crawler_class.assert_called_once_with(CrawlerConfig())

    def test_csv_report_is_written_to_requested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "report.csv"
            with (
                patch("seowebcrawler.cli.Crawler") as crawler_class,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                crawler_class.return_value.crawl.return_value = self.crawl_result()

                from seowebcrawler.cli import main

                exit_code = main(
                    [
                        "https://example.com/",
                        "--format",
                        "csv",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("Example", output_path.read_text(encoding="utf-8"))

    def test_configuration_is_loaded_and_passed_to_crawler(self):
        config = CrawlerConfig(max_pages=7)
        with (
            patch("seowebcrawler.cli.load_config", return_value=config),
            patch("seowebcrawler.cli.Crawler") as crawler_class,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            crawler_class.return_value.crawl.return_value = self.crawl_result()

            from seowebcrawler.cli import main

            exit_code = main(
                ["https://example.com/", "--config", "settings.yaml", "--format", "json"]
            )

        self.assertEqual(exit_code, 0)
        crawler_class.assert_called_once_with(config)

    def test_invalid_target_returns_error_exit_code(self):
        with (
            patch("seowebcrawler.cli.Crawler") as crawler_class,
            patch("seowebcrawler.cli.LOGGER.error") as log_error,
        ):
            crawler_class.return_value.crawl.side_effect = UnsafeTargetError(
                "Only absolute HTTPS URLs are allowed"
            )

            from seowebcrawler.cli import main

            exit_code = main(["http://example.com/"])

        self.assertEqual(exit_code, 2)
        log_error.assert_called_once()

    def test_output_write_error_returns_error_exit_code(self):
        with (
            patch("seowebcrawler.cli.Crawler") as crawler_class,
            patch("pathlib.Path.write_text", side_effect=OSError("read-only filesystem")),
            patch("seowebcrawler.cli.LOGGER.error") as log_error,
        ):
            crawler_class.return_value.crawl.return_value = self.crawl_result()

            from seowebcrawler.cli import main

            exit_code = main(
                ["https://example.com/", "--output", "report.json"]
            )

        self.assertEqual(exit_code, 2)
        log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
