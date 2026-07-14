import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from commands.tldr_command import TldrCommand


class TestTldrCommand(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MagicMock()
        self.db = MagicMock()
        # /tldr is opt-in only. Tests that expect messages to be summarized
        # set their authors' ids here explicitly.
        self.db.get_tldr_opted_in_users.return_value = set()
        self.deepseek_key = "fake-key"
        # patching during each test is clearer; reset per test.
        self.mock_ai_client = AsyncMock()
        self.cog_patch = patch(
            "commands.tldr_command.openai.AsyncOpenAI",
            return_value=self.mock_ai_client,
        )
        self.config_patch = patch(
            "commands.tldr_command.Config.DEEPSEEK_API_KEY", self.deepseek_key
        )
        self.mock_ai_class = self.cog_patch.start()
        self.config_patch.start()
        self.addCleanup(self.cog_patch.stop)
        self.addCleanup(self.config_patch.stop)
        self.cog = TldrCommand(self.bot, self.db)

    async def test_tldr_no_api_key_sends_error(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        # The command checks Config.DEEPSEEK_API_KEY before deferring, so the
        # error is a private (ephemeral) initial response, not a follow-up.
        with (
            patch("commands.tldr_command.Config.DEEPSEEK_API_KEY", None),
            patch("commands.tldr_command.openai.AsyncOpenAI", return_value=AsyncMock()),
        ):
            await self.cog.tldr.callback(self.cog, interaction, anzahl=50, zeit=None)

        interaction.response.send_message.assert_called_once_with(
            "❌ DeepSeek API-Schlüssel fehlt. TL;DR kann nicht genutzt werden.",
            ephemeral=True,
        )
        interaction.response.defer.assert_not_called()

    async def test_tldr_non_text_channel_returns_error(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.channel = MagicMock(spec=discord.DMChannel)
        await self.cog.tldr.callback(self.cog, interaction, anzahl=50, zeit=None)
        interaction.response.send_message.assert_called_once_with(
            "❌ Dieser Befehl funktioniert nur in Textkanälen.",
            ephemeral=True,
        )
        interaction.response.defer.assert_not_called()

    async def test_tldr_thread_channel_is_allowed(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.Thread)

        user = MagicMock()
        user.bot = False
        user.id = 55
        user.display_name = "Threadi"
        msg = MagicMock()
        msg.author = user
        msg.content = "im Thread"

        async def mock_history(limit=100, after=None, oldest_first=False):
            yield msg

        interaction.channel.history = mock_history
        self.db.get_tldr_opted_in_users.return_value = {55}

        self.mock_ai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="- eine Zusammenfassung"))]
            )
        )

        await self.cog.tldr.callback(self.cog, interaction, anzahl=10, zeit=None)

        interaction.response.defer.assert_called_once_with(ephemeral=False)
        embed = interaction.followup.send.call_args[1]["embed"]
        self.assertIn("- eine Zusammenfassung", embed.description)

    async def test_tldr_summarizes_messages(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        fake_user = MagicMock()
        fake_user.bot = False
        fake_user.id = 111
        fake_user.display_name = "Hans"
        fake_msg1 = MagicMock()
        fake_msg1.author = fake_user
        fake_msg1.content = "Hallo Welt"
        fake_msg2 = MagicMock()
        fake_msg2.author = fake_user
        fake_msg2.content = "Wie geht's?"

        async def mock_history(limit=100, after=None, oldest_first=False):
            yield fake_msg1
            yield fake_msg2

        interaction.channel.history = mock_history
        self.db.get_tldr_opted_in_users.return_value = {111}

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
        self.assertIn("- Jemand hat Hallo Welt gesagt", embed.description)
        self.assertIn("Basierend auf 2 Nachrichten", embed.footer.text)

    async def test_tldr_respects_anzahl_and_zeit_filter(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        fake_user = MagicMock()
        fake_user.bot = False
        fake_user.id = 222
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

        async def mock_history(limit=100, after=None, oldest_first=False):
            nonlocal call_after
            call_after = after
            if after is None:
                yield stale_msg
            yield fresh_msg

        interaction.channel.history = mock_history
        self.db.get_tldr_opted_in_users.return_value = {222}

        self.mock_ai_client.chat.completions.create = AsyncMock()
        self.mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(message=MagicMock(content="- jemand hat etwas geschrieben"))
            ]
        )

        await self.cog.tldr.callback(self.cog, interaction, anzahl=30, zeit="1h")

        interaction.response.defer.assert_called_once_with(ephemeral=False)
        # The stub raises after for 1h
        self.assertIsNotNone(call_after)
        embed = interaction.followup.send.call_args[1]["embed"]
        self.assertIn("Basierend auf 1 Nachrichten", embed.footer.text)

    async def test_tldr_includes_only_opted_in_users(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        included_user = MagicMock()
        included_user.bot = False
        included_user.id = 1
        included_user.display_name = "Bleibt"

        not_opted_in_user = MagicMock()
        not_opted_in_user.bot = False
        not_opted_in_user.id = 2
        not_opted_in_user.display_name = "Raus"

        included_msg = MagicMock()
        included_msg.author = included_user
        included_msg.content = "sichtbar"

        excluded_msg = MagicMock()
        excluded_msg.author = not_opted_in_user
        excluded_msg.content = "geheim"

        async def mock_history(limit=100, after=None, oldest_first=False):
            yield included_msg
            yield excluded_msg

        interaction.channel.history = mock_history
        # Only user 1 has opted in; user 2 must be excluded by default.
        self.db.get_tldr_opted_in_users.return_value = {1}

        self.mock_ai_client.chat.completions.create = AsyncMock()
        self.mock_ai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="- zusammenfassung"))]
        )

        await self.cog.tldr.callback(self.cog, interaction, anzahl=10, zeit=None)

        # Only the opted-in user's message should reach the AI.
        sent_context = self.mock_ai_client.chat.completions.create.call_args[1][
            "messages"
        ][1]["content"]
        self.assertIn("sichtbar", sent_context)
        self.assertNotIn("geheim", sent_context)

        embed = interaction.followup.send.call_args[1]["embed"]
        self.assertIn("Basierend auf 1 Nachrichten", embed.footer.text)
        self.assertIn("1 ausgeschlossen", embed.footer.text)

    async def test_tldr_optin_persists_preference(self):
        interaction = MagicMock()
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        self.db.set_tldr_optin.return_value = True

        await self.cog.tldr_optin.callback(self.cog, interaction)

        self.db.set_tldr_optin.assert_called_once_with(42, True)
        interaction.response.send_message.assert_called_once()
        self.assertTrue(interaction.response.send_message.call_args[1]["ephemeral"])

    async def test_tldr_optout_persists_preference(self):
        interaction = MagicMock()
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        self.db.set_tldr_optin.return_value = True

        await self.cog.tldr_optout.callback(self.cog, interaction)

        self.db.set_tldr_optin.assert_called_once_with(42, False)
        interaction.response.send_message.assert_called_once()

    async def test_tldr_no_messages(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        async def empty_history(limit=100, after=None, oldest_first=False):
            if False:
                yield  # no messages

        interaction.channel.history = empty_history

        await self.cog.tldr.callback(self.cog, interaction, anzahl=5, zeit=None)
        interaction.followup.send.assert_called_once_with(
            "Keine Nachrichten gefunden, die zusammengefasst werden können.",
            ephemeral=True,
        )

    async def test_tldr_all_skipped_prompts_optin(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        user = MagicMock()
        user.bot = False
        user.id = 99
        user.display_name = "Nope"
        msg = MagicMock()
        msg.author = user
        msg.content = "hallo"

        async def mock_history(limit=100, after=None, oldest_first=False):
            yield msg

        interaction.channel.history = mock_history
        # Nobody opted in, so every message is filtered out.
        self.db.get_tldr_opted_in_users.return_value = set()

        await self.cog.tldr.callback(self.cog, interaction, anzahl=10, zeit=None)

        sent_text = interaction.followup.send.call_args[0][0]
        self.assertIn("/tldr_optin", sent_text)
        self.assertTrue(interaction.followup.send.call_args[1]["ephemeral"])

    async def test_tldr_empty_ai_response_reports_error(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock(spec=discord.TextChannel)

        user = MagicMock()
        user.bot = False
        user.id = 7
        user.display_name = "Redner"
        msg = MagicMock()
        msg.author = user
        msg.content = "etwas Sinnvolles"

        async def mock_history(limit=100, after=None, oldest_first=False):
            yield msg

        interaction.channel.history = mock_history
        self.db.get_tldr_opted_in_users.return_value = {7}

        # An empty choices list must not crash; it surfaces as a handled error.
        self.mock_ai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[])
        )

        await self.cog.tldr.callback(self.cog, interaction, anzahl=10, zeit=None)

        interaction.followup.send.assert_called_once_with(
            "⚠️ Beim Erstellen der Zusammenfassung ist ein Fehler aufgetreten.",
            ephemeral=True,
        )
