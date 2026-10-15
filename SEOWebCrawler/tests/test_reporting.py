import csv
import io
import json
import unittest

from seowebcrawler.analyzer import analyze_page
from seowebcrawler.models import SiteReport
from seowebcrawler.reporting import to_csv, to_json


class ReportingTests(unittest.TestCase):
    def make_report(self):
        page = analyze_page(
            "https://example.com/",
            200,
            '<title>A, quoted "title"</title><h1>SEO report</h1><a href="/guide">Guide</a>',
        )
        return SiteReport("https://example.com/", [page], {})

    def test_json_contains_site_and_page_scores(self):
        document = json.loads(to_json(self.make_report()))
        self.assertEqual(document["start_url"], "https://example.com/")
        self.assertEqual(document["seo_score"], document["pages"][0]["seo_score"])
        self.assertIn("keyword_density", document["pages"][0])

    def test_csv_escapes_page_fields_and_has_one_page_per_row(self):
        rows = list(csv.DictReader(io.StringIO(to_csv(self.make_report()))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], 'A, quoted "title"')


if __name__ == "__main__":
    unittest.main()