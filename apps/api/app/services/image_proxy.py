import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from app.providers.base import ProviderError

MAX_IMAGE_BYTES = 8 * 1024 * 1024

def fetch_remote_image(url: str) -> tuple[bytes, str]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ProviderError("unsafe_image_url", "封面地址不符合安全要求。")
    try: addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error: raise ProviderError("image_unreachable", "封面域名无法解析。", True) from error
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ProviderError("unsafe_image_url", "封面地址未解析到公网。")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 CreatorRadar/0.4", "Referer": "https://www.douyin.com/", "Accept": "image/avif,image/webp,image/*"})
    try:
        with urlopen(request, timeout=20) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"): raise ProviderError("invalid_image", "封面响应不是图片。")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_IMAGE_BYTES: raise ProviderError("image_too_large", "封面超过大小限制。")
            data = response.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise ProviderError("image_unreachable", "暂时无法读取封面。", True) from error
    if len(data) > MAX_IMAGE_BYTES: raise ProviderError("image_too_large", "封面超过大小限制。")
    return data, content_type
