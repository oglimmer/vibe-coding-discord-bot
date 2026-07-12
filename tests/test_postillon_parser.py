import unittest
from pathlib import Path

from services.postillon.feed_parser import FeedParseError, parse_feed


FIXTURE = Path(__file__).parent / "fixtures" / "postillon_feed.xml"


class PostillonParserTest(unittest.TestCase):
    def test_parses_entries_and_skips_invalid_entry(self):
        posts = parse_feed(FIXTURE.read_bytes())

        self.assertEqual(2, len(posts))
        self.assertEqual("post-1", posts[0].external_id)
        self.assertEqual("Erster & bester Artikel", posts[0].title)
        self.assertEqual("Ein kurzer Text & weitere Details.", posts[0].summary_text)
        self.assertEqual("https://images.example/first.jpg", posts[0].image_url)
        self.assertEqual(("Politik", "Zeitlos"), posts[0].categories)
        self.assertIsNotNone(posts[0].published_at)

    def test_uses_url_when_guid_is_missing(self):
        post = parse_feed(FIXTURE.read_bytes())[1]

        self.assertIsNone(post.external_id)
        self.assertIsNone(post.published_at)
        self.assertEqual(64, len(post.identity_hash))
        self.assertEqual(post.identity_hash, post.url_hash)

    def test_rejects_invalid_xml(self):
        with self.assertRaises(FeedParseError):
            parse_feed(b"<rss><broken>")


if __name__ == "__main__":
    unittest.main()
