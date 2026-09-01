"""Resolve allowlisted platform redirects with bounded requests and SSRF checks."""
import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from app.services.link_validation import LinkError, PLATFORMS, validate_link

ALLOWED_HOSTS = set(PLATFORMS)
MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CreatorRadar/0.1"

def _check_target(url: str) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_HOSTS or parts.username or parts.password or parts.port not in (None, 443):
        raise LinkError("unsafe_redirect", "平台返回了不受信任的跳转地址，已停止访问。")
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise LinkError("platform_unreachable", "无法解析平台地址，请检查网络后重试。") from None
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise LinkError("unsafe_redirect", "平台地址解析到了非公网网络，已停止访问。")

class SafeRedirect(HTTPRedirectHandler):
    count = 0
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > MAX_REDIRECTS:
            raise LinkError("too_many_redirects", "短链接跳转次数过多，已停止访问。")
        target = urljoin(req.full_url, newurl)
        _check_target(target)
        return super().redirect_request(req, fp, code, msg, headers, target)

def resolve_and_check(parsed: dict) -> dict:
    source = parsed.get("input_url") or parsed.get("normalized_url")
    if not source:
        return parsed
    _check_target(source)
    redirect = SafeRedirect()
    request = Request(source, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        response = build_opener(redirect).open(request, timeout=8)
        final_url, status = response.geturl(), response.status
        response.close()
    except HTTPError as error:
        final_url, status = error.geturl(), error.code
        if status >= 500:
            raise LinkError("platform_unreachable", f"平台暂时返回 {status}，请稍后重试。") from None
    except (URLError, TimeoutError, OSError):
        raise LinkError("platform_unreachable", "暂时无法连接平台，请检查网络后重试。") from None
    _check_target(final_url)
    final = validate_link(final_url)
    if final["status"] != "recognized":
        raise LinkError("unresolved_short_link", "平台响应后仍未得到完整作品地址，请稍后重试或粘贴完整地址。")
    return {**final, "availability_checked": True, "availability_status": "platform_responded",
            "resolved_from_short_link": parsed["status"] == "needs_resolution",
            "message": "平台页面已响应，作品地址与标识已确认。此检查不包含标题、作者、媒体或可长期访问性。"}
