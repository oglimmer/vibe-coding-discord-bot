import asyncio
import logging

import aiohttp

from services.postillon.models import FeedResponse

logger = logging.getLogger(__name__)

MAX_FEED_BYTES = 5 * 1024 * 1024
USER_AGENT = "vibe-coding-discord-bot/1.0 (+Postillon RSS reader)"


class FeedClientError(RuntimeError):
    pass


class PostillonFeedClient:
    def __init__(self, url: str, timeout_seconds: int, retries: int = 2):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    async def fetch(
        self,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FeedResponse:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.url, headers=headers) as response:
                        if response.status == 304:
                            return FeedResponse(
                                status=304,
                                content=None,
                                etag=response.headers.get("ETag") or etag,
                                last_modified=response.headers.get("Last-Modified")
                                or last_modified,
                            )
                        if response.status != 200:
                            if response.status >= 500 and attempt < self.retries:
                                await asyncio.sleep(0.5 * (attempt + 1))
                                continue
                            raise FeedClientError(
                                f"Feed request returned HTTP {response.status}"
                            )

                        content_length = response.content_length
                        if content_length and content_length > MAX_FEED_BYTES:
                            raise FeedClientError("Feed response is too large")
                        content = await response.read()
                        if len(content) > MAX_FEED_BYTES:
                            raise FeedClientError("Feed response is too large")
                        return FeedResponse(
                            status=200,
                            content=content,
                            etag=response.headers.get("ETag"),
                            last_modified=response.headers.get("Last-Modified"),
                        )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    logger.warning(
                        "Postillon feed request failed (attempt %s/%s): %s",
                        attempt + 1,
                        self.retries + 1,
                        exc,
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                break

        raise FeedClientError(f"Could not fetch Postillon feed: {last_error}")
