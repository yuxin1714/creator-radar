import unittest
from app.services.link_validation import LinkError, validate_link


class LinkValidationTests(unittest.TestCase):
    def test_youtube_formats_normalize_to_same_work(self):
        urls = [
            "https://youtu.be/jNQXAC9IVRw?si=tracking",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw&feature=share",
            "https://www.youtube.com/shorts/jNQXAC9IVRw",
        ]
        for url in urls:
            with self.subTest(url=url):
                result = validate_link(url)
                self.assertEqual(result["normalized_url"], "https://www.youtube.com/watch?v=jNQXAC9IVRw")
                self.assertFalse(result["availability_checked"])
                self.assertFalse(result["imported"])

    def test_share_text_and_numeric_ids(self):
        self.assertEqual(validate_link("https://www.iesdouyin.com/share/video/7123456789012345678/")["normalized_url"], "https://www.douyin.com/video/7123456789012345678")
        result = validate_link("分享一个作品 https://www.douyin.com/video/7123456789012345678。 复制打开")
        self.assertEqual(result["external_id"], "7123456789012345678")
        self.assertEqual(validate_link("https://www.tiktok.com/@scout2015/video/6718335390845095173")["platform"], "tiktok")

    def test_short_links_are_not_claimed_as_work(self):
        for url in ["https://v.douyin.com/AbCd123/", "https://vm.tiktok.com/Z123abc/", "https://www.tiktok.com/t/Z123abc/"]:
            with self.subTest(url=url):
                result = validate_link(url)
                self.assertEqual(result["status"], "needs_resolution")
                self.assertEqual(result["content_type"], "unknown")
                self.assertIsNone(result["normalized_url"])

    def test_reject_unsafe_and_ambiguous_inputs(self):
        urls = [
            "http://127.0.0.1:8000/health", "http://169.254.169.254/latest/meta-data",
            "https://www.youtube.com.evil.test/watch?v=jNQXAC9IVRw",
            "https://youtube.com@evil.test/watch?v=jNQXAC9IVRw",
            "https://evil@youtube.com/watch?v=jNQXAC9IVRw",
            "https://youtube.com:444/watch?v=jNQXAC9IVRw",
            "javascript:alert(1)", "https://youtube.com/playlist?list=abc",
            "https://youtube.com/watch?v=jNQXAC9IVRw&v=other",
            "https://youtu.be/jNQXAC9IVRw https://youtu.be/jNQXAC9IVRw",
            "https://youtube.com/shorts/invalid", "https://v.douyin.com/",
            "https://youtube.com\\@evil.test/watch?v=jNQXAC9IVRw",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(LinkError):
                validate_link(url)

    def test_creator_has_actionable_error(self):
        for url in ["https://www.douyin.com/user/abc", "https://www.youtube.com/@creator"]:
            with self.assertRaises(LinkError) as result:
                validate_link(url)
            self.assertEqual(result.exception.code, "creator_link")


if __name__ == "__main__":
    unittest.main()
