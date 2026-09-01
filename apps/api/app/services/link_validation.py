"""Pure URL parsing: never resolves DNS, follows redirects or fetches media."""

import re

from urllib.parse import urlsplit, parse_qs



PLATFORMS = {

    "douyin.com": "douyin", "www.douyin.com": "douyin", "v.douyin.com": "douyin", "www.iesdouyin.com": "douyin",

    "tiktok.com": "tiktok", "www.tiktok.com": "tiktok",

    "m.tiktok.com": "tiktok", "vm.tiktok.com": "tiktok", "vt.tiktok.com": "tiktok",

    "youtube.com": "youtube", "www.youtube.com": "youtube",

    "m.youtube.com": "youtube", "youtu.be": "youtube",

}

SHORT_HOSTS = {"v.douyin.com", "vm.tiktok.com", "vt.tiktok.com"}





class LinkError(ValueError):

    def __init__(self, code: str, message: str):

        super().__init__(message)

        self.code = code





def validate_link(value: str) -> dict:

    value = value.strip()

    if not value or len(value) > 4000:

        raise LinkError("invalid_input", "请粘贴一条作品链接或分享文字，最多 4000 字符。")

    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):

        raise LinkError("invalid_input", "输入包含无效控制字符，请重新复制链接。")

    urls = re.findall(r"https?://[^\s<>\"“”]+", value, flags=re.I)

    if len(urls) != 1:

        raise LinkError("single_link_required", "每次只验证一条完整的 http:// 或 https:// 链接。")

    url = urls[0].rstrip(".,，。!！?？;；)）]】")

    if "\\" in url:

        raise LinkError("invalid_url", "链接格式不正确，请重新复制平台原始链接。")

    try:

        parts = urlsplit(url)

        host = (parts.hostname or "").lower()

        port = parts.port

    except ValueError:

        raise LinkError("invalid_url", "链接格式不正确。") from None

    if parts.username is not None or parts.password is not None or port not in (None, 80, 443):

        raise LinkError("invalid_url", "不支持含账号信息或自定义端口的链接。")

    platform = PLATFORMS.get(host)

    if not platform:

        raise LinkError("unsupported_platform", "仅支持抖音、TikTok 和 YouTube 的官方链接。")

    path = parts.path.rstrip("/")

    result = {"platform": platform, "content_type": "work", "external_id": None,
              "input_url": url,

              "normalized_url": None, "status": "recognized",

              "availability_checked": False, "imported": False}

    if host in SHORT_HOSTS or (platform == "tiktok" and path.startswith("/t/")):

        if not re.fullmatch(r"/(?:t/)?[A-Za-z0-9_-]+", path):

            raise LinkError("invalid_url", "短链接格式不完整。")

        return {**result, "content_type": "unknown", "status": "needs_resolution",

                "message": "识别到平台短链接，尚不能确定是作品还是创作者。请在浏览器打开后复制完整作品地址；本轮不会自动访问或展开短链接。"}

    external_id = None

    canonical = None

    if platform == "youtube":

        if host == "youtu.be":

            external_id = path.removeprefix("/")

        elif path == "/watch":

            ids = parse_qs(parts.query).get("v", [])

            if len(ids) == 1:

                external_id = ids[0]

        elif re.fullmatch(r"/(?:shorts|embed|live)/[A-Za-z0-9_-]+", path):

            external_id = path.rsplit("/", 1)[1]

        elif path.startswith(("/@", "/channel/", "/c/", "/user/")):

            raise LinkError("creator_link", "这是创作者主页，请粘贴具体作品链接。创作者导入将在后续接入。")

        if external_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", external_id):

            canonical = f"https://www.youtube.com/watch?v={external_id}"

    elif platform == "douyin":

        match = re.fullmatch(r"/(?:video|share/video)/([0-9]{10,25})", path)

        if match:

            external_id = match[1]

            canonical = f"https://www.douyin.com/video/{external_id}"

        elif path.startswith("/user/"):

            raise LinkError("creator_link", "这是创作者主页，请粘贴具体作品链接。")

    else:

        match = re.fullmatch(r"/@([A-Za-z0-9_.-]+)/video/([0-9]{10,25})", path)

        if match:

            external_id = match[2]

            canonical = f"https://www.tiktok.com/@{match[1]}/video/{external_id}"

        elif path.startswith("/@"):

            raise LinkError("creator_link", "请复制具体视频的链接，而不是创作者主页。")

    if not canonical:

        raise LinkError("unsupported_url", "暂不识别这种链接格式。请使用作品详情页地址；不支持图集、播放列表或搜索页。")

    return {**result, "external_id": external_id, "normalized_url": canonical,

            "message": "链接格式验证通过，已提取作品标识。尚未检查作品是否存在或可访问，也未导入、下载或分析。"}



