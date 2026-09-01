import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from app.providers.base import ProviderError, WorkMetadataResult

ENDPOINTS = {
    "douyin": ("/api/v1/douyin/web/fetch_one_video", "aweme_id"),
    "tiktok": ("/api/v1/tiktok/web/fetch_post_detail", "itemId"),
    "youtube": ("/api/v1/youtube/web_v2/get_video_info_v2", "video_id"),
}

def _first_url(value):
    if isinstance(value, str): return value
    if isinstance(value, list):
        for item in value:
            found = _first_url(item)
            if found: return found
    if isinstance(value, dict):
        for key in ("url_list", "urlList", "urls", "url"):
            found = _first_url(value.get(key))
            if found: return found
    return None

def _pick(root, *paths):
    for path in paths:
        value = root
        for key in path.split("."):
            if not isinstance(value, dict): value = None; break
            value = value.get(key)
        if value not in (None, "", [], {}): return value
    return None

def _timestamp(value):
    if isinstance(value, str) and "-" in value:
        try: return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=timezone.utc) if "T" not in value else datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError: return None
    try: return datetime.fromtimestamp(int(value), timezone.utc) if value else None
    except (TypeError, ValueError, OSError): return None

def normalize_payload(platform: str, payload: dict) -> WorkMetadataResult:
    data = payload.get("data")
    if not isinstance(data, dict): raise ProviderError("empty_result", "数据服务未返回作品信息。")
    if platform == "douyin":
        item = _pick(data, "aweme_detail", "aweme_list") or data
        if isinstance(item, list): item = item[0] if item else {}
        author = item.get("author") or {}
        video = item.get("video") or {}
        stats = item.get("statistics") or {}
        duration = video.get("duration")
    elif platform == "tiktok":
        item = _pick(data, "itemInfo.itemStruct", "itemStruct") or data
        author = item.get("author") or {}
        video = item.get("video") or {}
        stats = item.get("stats") or item.get("statistics") or {}
        duration = video.get("duration")
    else:
        item = _pick(data, "playerResponse.videoDetails", "videoDetails", "formatted") or data
        author = item.get("author") if isinstance(item.get("author"), dict) else item.get("channel") or {}
        video = item
        stats = {"view_count": _pick(item, "viewCount", "view_count")}
        duration = _pick(item, "lengthSeconds", "length_seconds", "duration")
    title = _pick(item, "desc", "title")
    author_name = _pick(author, "nickname", "uniqueId", "name") or (item.get("author") if isinstance(item.get("author"), str) else None)
    author_id = _pick(author, "uid", "id", "uniqueId", "unique_id", "channelId") or _pick(item, "channelId", "author_id")
    cover = _first_url(_pick(video, "cover", "origin_cover", "dynamicCover", "thumbnail", "thumbnails"))
    try: duration_seconds = round(float(duration) / 1000) if duration and float(duration) > 10000 else int(duration) if duration else None
    except (TypeError, ValueError): duration_seconds = None
    clean_metrics = {str(k): v for k, v in stats.items() if isinstance(v, (int, float, str)) and v not in (None, "")}
    if not any((title, author_name, cover)): raise ProviderError("invalid_payload", "数据服务响应缺少可用的作品元数据。")
    return WorkMetadataResult(title=title, author_id=str(author_id) if author_id else None,
        author_name=author_name, cover_url=cover, duration_seconds=duration_seconds,
        published_at=_timestamp(_pick(item, "create_time", "createTime", "publishDate", "publish_date")), metrics=clean_metrics or None)

class TikHubProvider:
    name = "tikhub"
    def __init__(self, api_key: str, base_url: str = "https://api.tikhub.io"):
        self.api_key, self.base_url = api_key.strip(), base_url.rstrip("/")
    @property
    def configured(self): return bool(self.api_key)
    def _fetch_payload(self, platform: str, external_id: str) -> dict:
        if not self.configured: raise ProviderError("provider_not_configured", "尚未配置 TikHub API Key。")
        if platform not in ENDPOINTS: raise ProviderError("unsupported_platform", "当前数据服务不支持该平台。")
        path, parameter = ENDPOINTS[platform]
        query = {parameter: external_id}
        if platform == "douyin": query["need_anchor_info"] = "false"
        if platform == "tiktok": query["region"] = "US"
        if platform == "youtube": query["need_format"] = "true"
        request = Request(self.base_url + path + "?" + urlencode(query), headers={"Authorization": "Bearer " + self.api_key, "Accept": "application/json", "User-Agent": "CreatorRadar/0.4"})
        try:
            with urlopen(request, timeout=30) as response: payload = json.load(response)
        except HTTPError as error:
            if error.code in (401, 403): raise ProviderError("provider_auth_failed", "TikHub 凭证无效或没有接口权限。") from error
            if error.code == 429: raise ProviderError("provider_rate_limited", "TikHub 请求受限，请稍后重试。", True) from error
            raise ProviderError("provider_http_error", f"TikHub 返回 HTTP {error.code}。", error.code >= 500) from error
        except (URLError, TimeoutError) as error: raise ProviderError("provider_unreachable", "暂时无法连接 TikHub。", True) from error
        except (json.JSONDecodeError, ValueError) as error: raise ProviderError("invalid_payload", "TikHub 返回了无法解析的数据。") from error
        if payload.get("code") not in (0, 200): raise ProviderError("provider_rejected", payload.get("message_zh") or payload.get("message") or "TikHub 未接受请求。")
        return payload

    def fetch_work(self, platform: str, external_id: str) -> WorkMetadataResult:
        return normalize_payload(platform, self._fetch_payload(platform, external_id))

    def fetch_media_url(self, platform: str, external_id: str) -> str:
        if platform not in ("douyin", "tiktok"):
            raise ProviderError("media_not_supported", "当前仅支持抖音和 TikTok 的本地转写。")
        payload = self._fetch_payload(platform, external_id)
        data = payload.get("data") or {}
        item = _pick(data, "aweme_detail", "itemInfo.itemStruct", "itemStruct") or data
        if isinstance(item, list): item = item[0] if item else {}
        video = item.get("video") if isinstance(item, dict) else None
        if not isinstance(video, dict):
            raise ProviderError("media_not_found", "数据服务未返回可用媒体信息。")
        for key in ("play_addr_h264", "play_addr", "playAddr", "download_addr", "downloadAddr", "bit_rate", "bitrateInfo"):
            url = _first_url(video.get(key))
            if url and url.startswith("https://"):
                return url
        raise ProviderError("media_not_found", "数据服务未返回可用于转写的媒体地址。")
