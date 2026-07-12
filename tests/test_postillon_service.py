import unittest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from services.postillon.models import FeedResponse
from services.postillon.service import PostillonService, create_postillon_embed


class FakeDatabase:
    def __init__(self):
        self.state = None
        self.deliveries = []
        self.attempt_error = None

    def try_acquire_postillon_lease(self, feed_key, owner, lease_seconds):
        return True

    def release_postillon_lease(self, feed_key, owner):
        return True

    def get_postillon_feed_state(self, feed_key):
        return self.state

    def record_postillon_attempt(self, feed_key, error=None):
        self.attempt_error = error

    def record_postillon_not_modified(self, feed_key, etag, last_modified):
        return True

    def import_postillon_posts(self, *args):
        return {"inserted": 2, "updated": 0, "queued": 0}

    def claim_postillon_deliveries(self, channel_id, stale_after, limit):
        return self.deliveries

    def mark_postillon_delivery_sent(self, delivery_id, message_id):
        return True

    def mark_postillon_delivery_pending(self, delivery_id, error):
        return True


class PostillonServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = FakeDatabase()
        self.bot = Mock()
        self.bot.get_channel.return_value = None
        self.bot.fetch_channel = AsyncMock(return_value=None)
        self.client = Mock()
        self.service = PostillonService(
            bot=self.bot,
            db_manager=self.db,
            feed_client=self.client,
            channel_id=123,
            announce_first_sync=False,
            delivery_delay_seconds=0,
            lease_seconds=300,
        )

    async def test_successful_initial_import_does_not_queue_old_posts(self):
        self.client.fetch = AsyncMock(
            return_value=FeedResponse(200, b"feed", "etag", "modified")
        )
        with patch("services.postillon.service.parse_feed", return_value=[1, 2]):
            result = await self.service.run_import()

        self.assertEqual("success", result.status)
        self.assertEqual(2, result.inserted)
        self.assertEqual(0, result.queued)

    async def test_304_is_successful_and_processes_pending_delivery(self):
        self.client.fetch = AsyncMock(
            return_value=FeedResponse(304, None, "etag", "modified")
        )

        result = await self.service.run_import()

        self.assertEqual("not_modified", result.status)
        self.assertEqual(0, result.failed)

    async def test_parallel_local_import_returns_busy(self):
        self.service._lock = Mock()
        self.service._lock.locked.return_value = True

        result = await self.service.run_import()

        self.assertEqual("busy", result.status)

    def test_embed_sanitizes_discord_limits(self):
        embed = create_postillon_embed(
            {
                "title": "x" * 300,
                "url": "https://example.com",
                "summary_text": "y" * 900,
                "published_at": datetime(2026, 7, 12, 8, 0),
                "categories_json": '["Politik", "Zeitlos"]',
            }
        )

        self.assertEqual(256, len(embed.title))
        self.assertEqual(800, len(embed.description))
        self.assertIsNotNone(embed.timestamp.tzinfo)


if __name__ == "__main__":
    unittest.main()
