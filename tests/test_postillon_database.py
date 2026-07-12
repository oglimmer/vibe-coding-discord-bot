import os
import unittest
import uuid
from datetime import datetime

from database import DatabaseManager
from services.postillon.models import PostillonPost


@unittest.skipUnless(
    os.getenv("POSTILLON_DB_TEST") == "1", "requires a disposable MariaDB database"
)
class PostillonDatabaseIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager()
        unique = uuid.uuid4().hex
        self.feed_key = f"postillon-test-{unique}"
        self.channel_id = 123456789
        self.posts = [self._post(unique, 1), self._post(unique, 2)]
        self.assertTrue(self.db.try_acquire_postillon_lease(self.feed_key, "test", 300))
        self.assertTrue(self.db.try_acquire_postillon_lease(self.feed_key, "test", 300))

    def tearDown(self):
        connection = self.db._get_connection()
        try:
            cursor = connection.cursor()
            hashes = [post.identity_hash for post in self.posts]
            placeholders = ",".join("?" for _ in hashes)
            cursor.execute(
                f"DELETE FROM postillon_posts WHERE identity_hash IN ({placeholders})",
                tuple(hashes),
            )
            cursor.execute(
                "DELETE FROM postillon_feed_state WHERE feed_key = ?", (self.feed_key,)
            )
            connection.commit()
        finally:
            connection.close()

    def _post(self, unique, number):
        identity = (unique + str(number)).ljust(64, "0")[:64]
        url_hash = (str(number) + unique).ljust(64, "1")[:64]
        return PostillonPost(
            external_id=f"post-{unique}-{number}",
            title=f"Test post {number}",
            url=f"https://example.com/{unique}/{number}",
            author="Test",
            summary_text="Summary",
            image_url=None,
            categories=("Test",),
            published_at=datetime(2026, 7, 12, 8, number),
            updated_at=None,
            identity_hash=identity,
            url_hash=url_hash,
            content_hash=identity,
        )

    def test_initial_sync_is_silent_and_later_post_is_queued_once(self):
        initial = self.db.import_postillon_posts(
            self.feed_key,
            self.posts[:1],
            self.channel_id,
            False,
            "etag-1",
            None,
        )
        second = self.db.import_postillon_posts(
            self.feed_key,
            self.posts,
            self.channel_id,
            False,
            "etag-2",
            None,
        )
        repeated = self.db.import_postillon_posts(
            self.feed_key,
            self.posts,
            self.channel_id,
            False,
            "etag-2",
            None,
        )

        self.assertEqual({"inserted": 1, "updated": 0, "queued": 0}, initial)
        self.assertEqual({"inserted": 1, "updated": 0, "queued": 1}, second)
        self.assertEqual({"inserted": 0, "updated": 0, "queued": 0}, repeated)
        deliveries = self.db.claim_postillon_deliveries(self.channel_id, 300)
        self.assertEqual(1, len(deliveries))


if __name__ == "__main__":
    unittest.main()
