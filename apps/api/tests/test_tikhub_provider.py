import unittest
from app.providers.base import ProviderError
from app.providers.tikhub import TikHubProvider, normalize_payload

class TikHubProviderTests(unittest.TestCase):
    def test_duration_units_come_from_platform_not_value_size(self):
        for platform,value,expected in [('douyin',7000,7),('douyin',0,0),('tiktok',12000,12000)]:
            result=normalize_payload(platform,{'data':{'desc':'Example','video':{'duration':value}}})
            self.assertEqual(result.duration_seconds,expected)
    def test_requires_key_before_network(self):
        with self.assertRaises(ProviderError) as result:
            TikHubProvider("").fetch_work("douyin", "123")
        self.assertEqual(result.exception.code, "provider_not_configured")

    def test_normalizes_douyin_without_leaking_provider_shape(self):
        result = normalize_payload("douyin", {"data": {"aweme_detail": {
            "desc": "测试作品", "create_time": 1700000000,
            "author": {"uid": "u1", "nickname": "作者"},
            "video": {"duration": 12500, "cover": {"url_list": ["https://img.example/cover.jpg"]}},
            "statistics": {"digg_count": 8, "comment_count": 2},
        }}})
        self.assertEqual(result.title, "测试作品")
        self.assertEqual(result.author_name, "作者")
        self.assertEqual(result.duration_seconds, 12)
        self.assertEqual(result.metrics["digg_count"], 8)

    def test_rejects_empty_payload(self):
        with self.assertRaises(ProviderError) as result:
            normalize_payload("youtube", {"data": {}})
        self.assertEqual(result.exception.code, "invalid_payload")

if __name__ == "__main__": unittest.main()
