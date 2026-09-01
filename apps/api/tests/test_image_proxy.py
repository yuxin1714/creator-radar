import unittest
from app.providers.base import ProviderError
from app.services.image_proxy import fetch_remote_image

class ImageProxyTests(unittest.TestCase):
    def test_rejects_non_https_and_credentials_before_network(self):
        for url in ("http://example.com/image.jpg", "https://user@example.com/image.jpg", "https://example.com:444/image.jpg"):
            with self.subTest(url=url), self.assertRaises(ProviderError) as result:
                fetch_remote_image(url)
            self.assertEqual(result.exception.code, "unsafe_image_url")

if __name__ == "__main__": unittest.main()
