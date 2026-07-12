import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from datetime import timedelta

from commands.tldr_command import TldrCommand


class TestTldrCommand(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MagicMock()
        self.db = MagicMock()
        self.openai_key = "fake-key"
        # patching during each test is clearer; reset per test.
        self.mock_ai_client = AsyncMock()
        self.cog_patch = patch(
            "commands.tldr_command.openai.AsyncOpenAI",
            return_value=self.mock_ai_client,
        )
        self.config_patch = patch(
            "commands.tldr_command.Config.OPENAI_API_KEY", self.openai_key
        )
        self.mock_ai_class = self.cog_patch.start()
        self.config_patch.start()
        self.addCleanup(self.cog_patch.stop)
        self.addCleanup(self.config_patch.stop)
        self.cog = TldrCommand(self.bot, self.db)

    async def test_tldr_no_api_key_sends_error(self):
        # re-create cog with missing key
        with patch(
            "commands.tldr_command.Config.OPENAI_API_KEY", None
        ), patch(
            "commands.tldr_command.openai.AsyncOpenAI"
        ) as mock_ai:
            mock_ai.return_value = AsyncMock()
            cog = TldrCommand(self.bot, self.db)

        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)
        await cog.tldr.callback(cog, interaction, anzahl=50, zeit=None)
        interaction.followup.send.assert_called_once_with(
            "❌ OpenAI API-Schlüssel fehlt. TL;DR kann nicht genutzt werden.",
            ephemeral=True,
        )

    async def test_tldr_non_text_channel_returns_error(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.DMChannel)
        await self.cog.tldr.callback(self.cog, interaction, anzahl=50, zeit=None)
        interaction.followup.send.assert_called_once_with(
            "❌ Dieser Befehl funktioniert nur in Textkanälen.",
            ephemeral=True,
        )

    async def test_tldr_summarizes_messages(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        fake_user = MagicMock()
        fake_user.bot = False
        fake_user.display_name = "Hans"
        fake_msg1 = MagicMock()
        fake_msg1.author = fake_user
        fake_msg1.content = "Hallo Welt"
        fake_msg2 = MagicMock()
        fake_msg2.author = fake_user
        fake_msg2.content = "Wie geht's?"

        async def mock_history(limit=100, after=None):
            yield fake_msg1
            yield fake_msg2

        interaction.channel.history = mock_history

        self.mock_ai_client.chat.completions.create = AsyncMock()
        self.mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(message=MagicMock(content="- Jemand hat Hallo Welt gesagt"))
            ]
        )

        await self.cog.tldr.callback(self.cog, interaction, anzahl=10, zeit=None)

        interaction.response.defer.assert_called_once_with(ephemeral=False)
        embed_kwargs = interaction.followup.send.call_args[1]
        embed = embed_kwargs["embed"]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "📝 TL;DR Zusammenfassung")
        self.assertIn(
            "- Jemand hat Hallo Welt gesagt", embed.description
        )
        self.assertIn("Basierend auf 2 Nachrichten", embed.footer.text)

    async def test_tldr_respects_anzahl_and_zeit_filter(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        fake_user = MagicMock()
        fake_user.bot = False
        fake_user.display_name = "Testi"

        # only one message in the future window (we fake time)
        fresh_msg = MagicMock()
        fresh_msg.author = fake_user
        fresh_msg.content = "neue Nachricht"

        stale_msg = MagicMock()
        stale_msg.author = fake_user
        stale_msg.content = "alte Nachricht"

        # Override history to filter by after
        call_after = None

        async def mock_history(limit=100, after=None):
            nonlocal call_after
            call_after = after
            if after is None:
                yield stale_msg
            yield fresh_msg

        interaction.channel.history = mock_history

        self.mock_ai_client.chat.completions.create = AsyncMock()
        self.mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(message=MagicMock(content="- jemand hat etwas geschrieben"))
            ]
        )

        await self.cog.tldr.callback(
            self.cog, interaction, anzahl=30, zeit="1h"
        )

        interaction.response.defer.assert_called_once_with(ephemeral=False)
        # The stub raises after for 1h
        self.assertIsNotNone(call_after)
        embed = interaction.followup.send.call_args[1]["embed"]
        self.assertIn("Basierend auf 1 Nachrichten", embed.footer.text)

    async def test_tldr_no_messages(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        async def empty_history(limit=100, after=None):
            if False:
                yield  # no messages

        interaction.channel.history = empty_history

        await self.cog.tldr.callback(self.cog, interaction, anzahl=5, zeit=None)
        interaction.followup.send.assert_called_once_with(
            "Keine Nachrichten gefunden, die zusammengefasst werden können.",
            ephemeral=True,
        )
