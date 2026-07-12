from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PostillonPost:
    external_id: str | None
    title: str
    url: str
    author: str | None
    summary_text: str
    image_url: str | None
    categories: tuple[str, ...]
    published_at: datetime | None
    updated_at: datetime | None
    identity_hash: str
    url_hash: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class FeedResponse:
    status: int
    content: bytes | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True, slots=True)
class ImportResult:
    status: str
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    queued: int = 0
    delivered: int = 0
    failed: int = 0
    message: str | None = None
