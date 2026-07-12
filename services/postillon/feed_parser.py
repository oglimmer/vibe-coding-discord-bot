import hashlib
import html
import json
import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

import feedparser

from services.postillon.models import PostillonPost

logger = logging.getLogger(__name__)


class FeedParseError(ValueError):
    pass


class _ContentExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.image_url: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img" and self.image_url is None:
            attributes = dict(attrs)
            self.image_url = attributes.get("src")

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.text_parts.append(value)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, "")
    )


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _extract_content(raw_html: str) -> tuple[str, str | None]:
    parser = _ContentExtractor()
    parser.feed(raw_html or "")
    text = html.unescape(" ".join(parser.text_parts))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*mehr\.\.\.\s*$", "", text, flags=re.IGNORECASE).strip()
    return text, _normalize_url(parser.image_url or "") or None


def _entry_image(entry, html_image: str | None) -> str | None:
    if html_image:
        return html_image
    thumbnails = entry.get("media_thumbnail") or []
    if thumbnails:
        return _normalize_url(thumbnails[0].get("url", "")) or None
    return None


def _build_post(entry) -> PostillonPost:
    title = html.unescape(str(entry.get("title", ""))).strip()
    url = _normalize_url(str(entry.get("link", "")))
    if not title or not url:
        raise FeedParseError("Feed entry has no valid title or URL")
    if len(url) > 2048:
        raise FeedParseError("Feed entry URL is too long")

    external_id_value = str(entry.get("id") or entry.get("guid") or "").strip()
    external_id = external_id_value[:512] or None
    summary_text, html_image = _extract_content(
        str(entry.get("summary") or entry.get("description") or "")
    )
    published_at = _parse_datetime(entry.get("published"))
    updated_at = _parse_datetime(entry.get("updated"))
    categories = tuple(
        dict.fromkeys(
            str(tag.get("term", "")).strip()
            for tag in entry.get("tags", [])
            if str(tag.get("term", "")).strip()
        )
    )
    identity_source = external_id_value or url or f"{url}\n{title}"
    content_source = json.dumps(
        {
            "title": title,
            "url": url,
            "summary": summary_text,
            "published_at": published_at.isoformat() if published_at else None,
            "updated_at": updated_at.isoformat() if updated_at else None,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return PostillonPost(
        external_id=external_id,
        title=title,
        url=url,
        author=str(entry.get("author", "")).strip()[:255] or None,
        summary_text=summary_text,
        image_url=(lambda value: value if value and len(value) <= 2048 else None)(
            _entry_image(entry, html_image)
        ),
        categories=categories,
        published_at=published_at,
        updated_at=updated_at,
        identity_hash=_sha256(identity_source),
        url_hash=_sha256(url),
        content_hash=_sha256(content_source),
    )


def parse_feed(content: bytes) -> list[PostillonPost]:
    if not content:
        raise FeedParseError("Feed response is empty")
    try:
        ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise FeedParseError(f"Feed is not valid XML: {exc}") from exc

    parsed = feedparser.parse(content)
    if not parsed.entries:
        raise FeedParseError("Feed contains no entries")
    posts = []
    for entry in parsed.entries:
        try:
            posts.append(_build_post(entry))
        except FeedParseError as exc:
            logger.warning("Skipping invalid Postillon feed entry: %s", exc)
        except Exception:
            logger.exception("Skipping unexpected invalid Postillon feed entry")
    if not posts:
        raise FeedParseError("Feed contains no valid entries")
    return posts
