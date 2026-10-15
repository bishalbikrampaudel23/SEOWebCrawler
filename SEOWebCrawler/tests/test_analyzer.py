import unittest

from seowebcrawler.analyzer import analyze_page


class AnalyzePageTests(unittest.TestCase):
    def test_extracts_seo_signals_and_matches_broken_links(self):
        html = """<!doctype html><html><head><title>Search engines and running</title>
        <meta name="description" content="A useful description for search engines">
        <meta name="keywords" content="search, crawling"></head><body>
        <h1>Search engines</h1><p>Running runners search search engines.</p>
        <a href="/guide">Guide</a><a href="https://outside.example/bad">Outside</a>
        <img src="a.png"><img src="b.png" alt="A chart"></body></html>"""
        analysis = analyze_page(
            "https://example.com/",
            200,
            html,
            {"https://example.com/guide": 200, "https://outside.example/bad": 404},
        )

        self.assertEqual(analysis.title, "Search engines and running")
        self.assertEqual(analysis.meta_keywords, ["search", "crawling"])
        self.assertIn("run", analysis.keyword_frequencies)
        self.assertGreater(analysis.keyword_density["search"], 0)
        self.assertEqual(analysis.images_missing_alt, 1)
        self.assertEqual(analysis.internal_links, ["https://example.com/guide"])
        self.assertEqual(analysis.external_links, ["https://outside.example/bad"])
        self.assertEqual(analysis.broken_links[0]["status_code"], 404)

    def test_invalid_html_returns_empty_content_signals(self):
        analysis = analyze_page("https://example.com/", 500, "<broken")
        self.assertEqual(analysis.seo_score, 0)
        self.assertEqual(analysis.word_count, 1)
        self.assertEqual(analysis.title, "")
        self.assertTrue(analysis.keyword_density)


if __name__ == "__main__":
    unittest.main()