import unittest

from commands.postillon_command import PostillonView


class PostillonCommandTest(unittest.TestCase):
    def test_postillon_view_has_public_navigation(self):
        view = PostillonView(
            [
                {
                    "title": "Test",
                    "url": "https://example.com",
                    "summary_text": "Summary",
                }
            ]
        )

        self.assertFalse(hasattr(view, "owner_id"))
        self.assertTrue(view.previous.disabled)
        self.assertTrue(view.next.disabled)


if __name__ == "__main__":
    unittest.main()
