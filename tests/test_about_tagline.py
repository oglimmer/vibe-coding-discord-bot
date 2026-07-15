import unittest
from unittest.mock import MagicMock

from commands.about_command import AboutCommand


class TestAboutTagline(unittest.TestCase):
    def test_purpose_describes_vibe_coding_and_backend(self):
        """The about embed must describe vibe coding and mention Claude Code + DeepSeek."""
        # Minimal mock bot to support _create_about_embed
        bot = MagicMock()
        bot.latency = 0.123
        mock_guild1 = MagicMock()
        mock_guild1.member_count = 15
        mock_guild2 = MagicMock()
        mock_guild2.member_count = 5
        bot.guilds = [mock_guild1, mock_guild2]
        mock_commands = [MagicMock() for _ in range(3)]
        bot.tree.get_commands.return_value = mock_commands

        about = AboutCommand(bot)
        embed = about._create_about_embed()

        purpose_value = None
        for field in embed.fields:
            if field.name == "Purpose":
                purpose_value = field.value
                break

        self.assertIsNotNone(purpose_value, "Embed must contain a Purpose field")
        self.assertIn(
            "Vibe Coding",
            purpose_value,
            "Purpose field should mention 'Vibe Coding'",
        )
        self.assertIn(
            "Claude Code",
            purpose_value,
            "Purpose field should mention 'Claude Code' framework",
        )
        self.assertIn(
            "DeepSeek",
            purpose_value,
            "Purpose field should mention 'DeepSeek' as the backend model",
        )
