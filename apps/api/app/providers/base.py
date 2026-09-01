from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class WorkMetadataResult:
    title: str | None = None
    author_id: str | None = None
    author_name: str | None = None
    cover_url: str | None = None
    duration_seconds: int | None = None
    published_at: datetime | None = None
    metrics: dict | None = None

class ProviderError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
