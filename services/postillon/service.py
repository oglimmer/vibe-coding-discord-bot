import asyncio
import json
import logging
import uuid
from datetime import UTC

import discord

from services.postillon.feed_client import PostillonFeedClient
from services.postillon.feed_parser import parse_feed
from services.postillon.models import ImportResult

logger = logging.getLogger(__name__)

FEED_KEY = "postillon-default"


def create_postillon_embed(post: dict) -> discord.Embed:
    published_at = post.get("published_at")
    if published_at and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    embed = discord.Embed(
        title=str(post.get("title") or "Der Postillon")[:256],
        url=post.get("url"),
        description=str(post.get("summary_text") or "")[:800] or None,
        color=0xD71920,
        timestamp=published_at,
    )
    image_url = post.get("image_url")
    if image_url:
        embed.set_image(url=image_url)
    categories = post.get("categories_json") or []
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except (TypeError, json.JSONDecodeError):
            categories = []
    footer = " · ".join(str(value) for value in categories[:3])
    embed.set_footer(text=footer or "Der Postillon")
    return embed


class PostillonService:
    def __init__(
        self,
        bot,
        db_manager,
        feed_client: PostillonFeedClient,
        channel_id: int,
        announce_first_sync: bool,
        delivery_delay_seconds: float,
        lease_seconds: int,
    ):
        self.bot = bot
        self.db_manager = db_manager
        self.feed_client = feed_client
        self.channel_id = channel_id
        self.announce_first_sync = announce_first_sync
        self.delivery_delay_seconds = delivery_delay_seconds
        self.lease_seconds = lease_seconds
        self._lock = asyncio.Lock()

    async def run_import(self) -> ImportResult:
        if self._lock.locked():
            return ImportResult(status="busy", message="Ein Import läuft bereits.")

        async with self._lock:
            owner = f"{uuid.uuid4()}"
            acquired = False
            try:
                acquired = await asyncio.to_thread(
                    self.db_manager.try_acquire_postillon_lease,
                    FEED_KEY,
                    owner,
                    self.lease_seconds,
                )
                if not acquired:
                    return ImportResult(
                        status="busy",
                        message="Ein anderer Bot-Prozess importiert bereits.",
                    )
                return await self._run_import(owner)
            except Exception as exc:
                logger.exception("Postillon import failed")
                try:
                    await asyncio.to_thread(
                        self.db_manager.record_postillon_attempt,
                        FEED_KEY,
                        str(exc),
                    )
                except Exception:
                    logger.exception("Could not persist Postillon import error")
                return ImportResult(status="error", message=str(exc))
            finally:
                if acquired:
                    try:
                        await asyncio.to_thread(
                            self.db_manager.release_postillon_lease, FEED_KEY, owner
                        )
                    except Exception:
                        logger.exception("Could not release Postillon import lease")

    async def _run_import(self, owner: str) -> ImportResult:
        state = await asyncio.to_thread(
            self.db_manager.get_postillon_feed_state, FEED_KEY
        )
        response = await self.feed_client.fetch(
            etag=state.get("etag") if state else None,
            last_modified=state.get("last_modified") if state else None,
        )
        if response.status == 304:
            await asyncio.to_thread(
                self.db_manager.record_postillon_not_modified,
                FEED_KEY,
                response.etag,
                response.last_modified,
            )
            delivered, failed = await self._deliver_pending(owner)
            return ImportResult(
                status="not_modified", delivered=delivered, failed=failed
            )

        posts = parse_feed(response.content or b"")
        imported = await asyncio.to_thread(
            self.db_manager.import_postillon_posts,
            FEED_KEY,
            posts,
            self.channel_id,
            self.announce_first_sync,
            response.etag,
            response.last_modified,
        )
        delivered, failed = await self._deliver_pending(owner)
        return ImportResult(
            status="success",
            fetched=len(posts),
            inserted=imported["inserted"],
            updated=imported["updated"],
            queued=imported["queued"],
            delivered=delivered,
            failed=failed,
        )

    async def _resolve_channel(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel is not None:
            return channel
        try:
            return await self.bot.fetch_channel(self.channel_id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            logger.exception(
                "Configured Postillon channel %s is unavailable", self.channel_id
            )
            return None

    async def _deliver_pending(self, owner: str) -> tuple[int, int]:
        channel = await self._resolve_channel()
        if channel is None:
            return 0, 0
        delivered = 0
        failed = 0
        for _ in range(50):
            renewed = await asyncio.to_thread(
                self.db_manager.try_acquire_postillon_lease,
                FEED_KEY,
                owner,
                self.lease_seconds,
            )
            if not renewed:
                logger.warning("Lost Postillon import lease during delivery")
                break
            deliveries = await asyncio.to_thread(
                self.db_manager.claim_postillon_deliveries,
                self.channel_id,
                self.lease_seconds,
                1,
            )
            if not deliveries:
                break
            delivery = deliveries[0]
            try:
                message = await channel.send(
                    embed=create_postillon_embed(delivery),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                await asyncio.to_thread(
                    self.db_manager.mark_postillon_delivery_sent,
                    delivery["delivery_id"],
                    message.id,
                )
                delivered += 1
                if self.delivery_delay_seconds > 0:
                    await asyncio.sleep(self.delivery_delay_seconds)
            except Exception as exc:
                logger.error(
                    "Could not deliver Postillon post %s: %s",
                    delivery["post_id"],
                    exc,
                )
                try:
                    await asyncio.to_thread(
                        self.db_manager.mark_postillon_delivery_pending,
                        delivery["delivery_id"],
                        str(exc),
                    )
                except Exception:
                    logger.exception("Could not reset failed Postillon delivery")
                failed += 1
                break
        return delivered, failed
