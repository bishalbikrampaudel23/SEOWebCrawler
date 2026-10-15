import unittest
from unittest.mock import patch

from seowebcrawler.security import UnsafeTargetError, validate_target_url


class ValidateTargetUrlTests(unittest.TestCase):
    def test_normalizes_public_url_and_drops_fragment(self):
        with patch("seowebcrawler.security.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("93.184.216.34", 443))
        ]):
            result = validate_target_url("https://Example.com:443/path?q=1#section")
        self.assertEqual(result, "https://example.com/path?q=1")

    def test_rejects_non_http_scheme_and_credentials(self):
        for url in ("file:///etc/passwd", "https://user:pass@example.com/"):
            with self.subTest(url=url), self.assertRaises(UnsafeTargetError):
                validate_target_url(url)

    def test_rejects_private_literal_and_nonstandard_port(self):
        for url in ("http://127.0.0.1/", "https://example.com:8443/"):
            with self.subTest(url=url), self.assertRaises(UnsafeTargetError):
                validate_target_url(url)

    def test_rejects_host_resolving_to_private_address(self):
        with patch("seowebcrawler.security.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("10.0.0.8", 443))
        ]), self.assertRaises(UnsafeTargetError):
            validate_target_url("https://example.com/")


if __name__ == "__main__":
    unittest.main()