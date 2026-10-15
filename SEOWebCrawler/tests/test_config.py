import tempfile
import unittest
from pathlib import Path

from seowebcrawler.config import CrawlerConfig, load_config


class ConfigTests(unittest.TestCase):
    def test_yaml_settings_load_and_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.yaml"
            path.write_text("max_depth: 3\nmax_pages: 20\n", encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config.max_depth, 3)
        self.assertEqual(config.max_pages, 20)

    def test_unknown_or_malformed_settings_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.yaml"
            path.write_text("unknown_option: true\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown configuration"):
                load_config(path)
            path.write_text("max_depth: [\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid YAML"):
                load_config(path)

    def test_out_of_range_runtime_config_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_depth"):
            CrawlerConfig(max_depth=11)


if __name__ == "__main__":
    unittest.main()