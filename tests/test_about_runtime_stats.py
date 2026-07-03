import asyncio
import datetime
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import discord

from commands.about_command import AboutCommand


class TestAboutRuntimeStats(unittest.TestCase):
    def test_about_includes_runtime_stats(self):
        async def async_test():
            bot = MagicMock()
            bot.latency = 0.2  # seconds
            guild1 = MagicMock()
            guild1.member_count = 15
            guild2 = MagicMock()
            guild2.member_count = 5
            bot.guilds = [guild1, guild2]
            dummy_cmds = [MagicMock() for _ in range(8)]
            bot.tree.get_commands.return_value = dummy_cmds

            cog = AboutCommand(bot)
            # Override start_time to a fixed past so we can assert uptime presence
            cog.start_time = datetime.datetime(
                2025, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc
            )

            interaction = MagicMock()
            interaction.response.send_message = AsyncMock()

            with patch.object(
                AboutCommand,
                "_get_build_info",
                return_value={
                    "build_time": "2025-01-01",
                    "git_branch": "dev",
                    "git_revision": "abc123",
                },
            ):
                # call the underlying slash command callback
                await cog.about.callback(cog, interaction)

            send_msg_mock = interaction.response.send_message
            send_msg_mock.assert_called_once()

            # retrieve the embed passed to send_message
            _, kwargs = send_msg_mock.call_args
            embed = kwargs.get("embed")
            self.assertIsNotNone(embed, "Embed not passed to send_message")

            # locate the Runtime Statistics field
            runtime_field = None
            for field in embed.fields:
                if "Runtime Statistics" in field.name:
                    runtime_field = field
                    break
            self.assertIsNotNone(runtime_field, "Runtime Statistics field missing")

            field_text = runtime_field.value
            # Check that all expected labels and values appear
            self.assertIn("**Uptime:**", field_text)
            self.assertIn("**Latency:** 200 ms", field_text)
            self.assertIn("**Servers:** 2", field_text)
            self.assertIn("**Members:** 20", field_text)
            self.assertIn("**Commands:** 8", field_text)

        asyncio.run(async_test())


if __name__ == "__main__":
    unittest.main()
