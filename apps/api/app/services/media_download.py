import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from app.providers.base import ProviderError

def download_media(url: str, directory: str, max_bytes: int) -> Path:
    if not url.startswith("https://"):
        raise ProviderError("unsafe_media_url", "媒体地址不是安全的 HTTPS 地址。")
    target_dir = Path(directory); target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4()}.mp4"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 CreatorRadar/0.6", "Referer": "https://www.douyin.com/"})
    try:
        with urlopen(request, timeout=60) as response, target.open("wb") as output:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes: raise ProviderError("media_too_large", "媒体文件超过本地转写大小上限。")
            copied = 0
            while chunk := response.read(1024 * 1024):
                copied += len(chunk)
                if copied > max_bytes: raise ProviderError("media_too_large", "媒体文件超过本地转写大小上限。")
                output.write(chunk)
        return target
    except ProviderError:
        target.unlink(missing_ok=True); raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        target.unlink(missing_ok=True)
        raise ProviderError("media_download_failed", "暂时无法下载用于转写的媒体。", True) from error
