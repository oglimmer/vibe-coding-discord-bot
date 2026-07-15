import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from commands.birthday_command import BirthdayCommand, GERMANY_TZ

TODAY = datetime.date(2025, 7, 15)
GUILD_ID = 42


class TestBirthdaySetCommand(unittest.TestCase):
    def test_birthday_set_valid_date(self):
        async def async_test():
            bot = MagicMock()
            bot.wait_until_ready = AsyncMock()
            db_manager = MagicMock()
            db_manager.set_birthday = MagicMock(return_value=True)
            bot.db_manager = db_manager

            cog = BirthdayCommand(bot, db_manager)
            cog.daily_check.cancel()

            interaction = MagicMock()
            interaction.user.id = 123456789
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 987654321
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await cog.birthday_set.callback(cog, interaction, datum="15-07-1990")

            interaction.response.defer.assert_called_once_with(ephemeral=True)

            db_manager.set_birthday.assert_called_once()
            args, _kwargs = db_manager.set_birthday.call_args
            self.assertEqual(args[0], 123456789)
            self.assertEqual(args[1], "TestUser")
            expected_date = datetime.date(1990, 7, 15)
            self.assertEqual(args[2], expected_date)
            self.assertEqual(args[3], 987654321)

            interaction.followup.send.assert_called_once()
            _, kwargs = interaction.followup.send.call_args
            embed = kwargs.get("embed")
            self.assertIsNotNone(embed)
            self.assertEqual(embed.color.value, discord.Color.green().value)
            self.assertIn("Geburtstag gespeichert", embed.title)

        asyncio.run(async_test())

    def test_birthday_commands_are_guild_only(self):
        """Birthdays are stored per server, so a DM has no server to store under."""
        self.assertTrue(BirthdayCommand.birthday_set.guild_only)
        self.assertTrue(BirthdayCommand.birthday_remove.guild_only)

    def test_birthday_set_invalid_format(self):
        async def async_test():
            bot = MagicMock()
            bot.wait_until_ready = AsyncMock()
            db_manager = MagicMock()
            bot.db_manager = db_manager

            cog = BirthdayCommand(bot, db_manager)
            cog.daily_check.cancel()

            interaction = MagicMock()
            interaction.user.id = 111
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 1
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await cog.birthday_set.callback(cog, interaction, datum="15/07/1990")

            db_manager.set_birthday.assert_not_called()
            interaction.followup.send.assert_called_once()
            _, kwargs = interaction.followup.send.call_args
            embed = kwargs.get("embed")
            self.assertIsNotNone(embed)
            self.assertIn("Ungültiges Datum", embed.title)

        asyncio.run(async_test())

    def test_birthday_set_future_date(self):
        async def async_test():
            bot = MagicMock()
            bot.wait_until_ready = AsyncMock()
            db_manager = MagicMock()
            bot.db_manager = db_manager

            cog = BirthdayCommand(bot, db_manager)
            cog.daily_check.cancel()

            interaction = MagicMock()
            interaction.user.id = 111
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 1
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await cog.birthday_set.callback(cog, interaction, datum="15-07-2099")

            db_manager.set_birthday.assert_not_called()
            interaction.followup.send.assert_called_once()
            _, kwargs = interaction.followup.send.call_args
            embed = kwargs.get("embed")
            self.assertIn("Zukunft", embed.title)

        asyncio.run(async_test())

    def test_birthday_set_db_error(self):
        async def async_test():
            bot = MagicMock()
            bot.wait_until_ready = AsyncMock()
            db_manager = MagicMock()
            db_manager.set_birthday = MagicMock(return_value=False)
            bot.db_manager = db_manager

            cog = BirthdayCommand(bot, db_manager)
            cog.daily_check.cancel()

            interaction = MagicMock()
            interaction.user.id = 111
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 1
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await cog.birthday_set.callback(cog, interaction, datum="15-07-1990")

            interaction.followup.send.assert_called_once()
            _, kwargs = interaction.followup.send.call_args
            embed = kwargs.get("embed")
            self.assertIn("Fehler", embed.title)

        asyncio.run(async_test())


class TestBirthdayAnnouncements(unittest.TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.wait_until_ready = AsyncMock()
        self.db_manager = MagicMock()
        self.db_manager.try_claim_birthday_announcement.return_value = True
        self.bot.db_manager = self.db_manager
        self.channel = MagicMock()
        self.channel.send = AsyncMock()
        self.channel.guild.id = GUILD_ID
        self.bot.get_channel.return_value = self.channel

    def _make_cog(self):
        """Create a cog and immediately cancel its loop.

        The loop is cancelled so the background asyncio task does not fire
        during the test.  Tests drive ``_announce_birthdays`` directly with an
        explicit date, which needs no clock patching.
        """
        cog = BirthdayCommand(self.bot, self.db_manager)
        cog.daily_check.cancel()
        return cog

    def _birthday_row(self, user_id=555, username="Geburtstagskind"):
        return {
            "user_id": user_id,
            "username": username,
            "birthday": datetime.date(1990, 7, 15),
            "server_id": GUILD_ID,
        }

    def _mention_user(self, mention="<@555>"):
        fake_user = MagicMock()
        fake_user.mention = mention
        self.bot.get_user.return_value = fake_user
        return fake_user

    def test_announces_todays_birthdays(self):
        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = [
                self._birthday_row()
            ]
            self._mention_user()

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.get_birthdays_for_today.assert_called_once_with(
                GUILD_ID, TODAY
            )
            self.db_manager.try_claim_birthday_announcement.assert_called_once_with(
                GUILD_ID, TODAY
            )
            self.channel.send.assert_called_once()
            _, kwargs = self.channel.send.call_args
            embed = kwargs.get("embed")
            self.assertIsNotNone(embed)
            self.assertIn("Geburtstag", embed.title)
            self.db_manager.release_birthday_announcement.assert_not_called()

        asyncio.run(async_test())

    def test_skips_when_the_day_is_already_claimed(self):
        """A second run on the same day — e.g. after a restart — stays quiet."""

        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = [
                self._birthday_row()
            ]
            self.db_manager.try_claim_birthday_announcement.return_value = False
            self._mention_user()

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_no_channel_configured_leaves_day_unclaimed(self):
        async def async_test():
            cog = self._make_cog()

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = None
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.get_birthdays_for_today.assert_not_called()
            self.db_manager.try_claim_birthday_announcement.assert_not_called()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_missing_channel_leaves_day_unclaimed(self):
        """Channel ID is configured but the channel is gone — retry later."""

        async def async_test():
            cog = self._make_cog()
            self.bot.get_channel.return_value = None

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.try_claim_birthday_announcement.assert_not_called()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_channel_without_a_guild_leaves_day_unclaimed(self):
        """A DM channel has no server to scope the birthdays to."""

        async def async_test():
            cog = self._make_cog()
            self.channel.guild = None

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.get_birthdays_for_today.assert_not_called()
            self.db_manager.try_claim_birthday_announcement.assert_not_called()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_only_the_channels_own_server_is_greeted(self):
        """The query is scoped to the guild that owns the birthday channel."""

        async def async_test():
            cog = self._make_cog()
            self.channel.guild.id = 777
            self.db_manager.get_birthdays_for_today.return_value = []

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.get_birthdays_for_today.assert_called_once_with(777, TODAY)

        asyncio.run(async_test())

    def test_no_birthdays_today(self):
        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = []

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.get_birthdays_for_today.assert_called_once_with(
                GUILD_ID, TODAY
            )
            self.db_manager.try_claim_birthday_announcement.assert_not_called()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_claim_released_when_nothing_could_be_delivered(self):
        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = [
                self._birthday_row()
            ]
            self._mention_user()
            self.channel.send.side_effect = RuntimeError("Discord is down")

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.release_birthday_announcement.assert_called_once_with(
                GUILD_ID, TODAY
            )

        asyncio.run(async_test())

    def test_claim_kept_when_some_greetings_got_through(self):
        """A partial send must not be retried — nobody gets greeted twice."""

        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = [
                self._birthday_row(user_id=555),
                self._birthday_row(user_id=666, username="Zweiter"),
            ]
            self._mention_user()
            self.channel.send.side_effect = [None, RuntimeError("Discord is down")]

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.db_manager.release_birthday_announcement.assert_not_called()

        asyncio.run(async_test())

    def test_unknown_user_is_skipped(self):
        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = [
                self._birthday_row()
            ]
            self.bot.get_user.return_value = None
            self.bot.fetch_user = AsyncMock(
                side_effect=discord.NotFound(MagicMock(status=404), "unknown user")
            )

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = 12345
                mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                await cog._announce_birthdays(TODAY)

            self.channel.send.assert_not_called()
            self.db_manager.release_birthday_announcement.assert_called_once_with(
                GUILD_ID, TODAY
            )

        asyncio.run(async_test())

    def test_announcement_channel_used_as_fallback(self):
        async def async_test():
            cog = self._make_cog()
            self.db_manager.get_birthdays_for_today.return_value = [
                self._birthday_row()
            ]
            self._mention_user()

            with patch("commands.birthday_command.Config") as mock_config:
                mock_config.BIRTHDAY_CHANNEL_ID = None
                mock_config.ANNOUNCEMENT_CHANNEL_ID = 999
                await cog._announce_birthdays(TODAY)

            self.bot.get_channel.assert_called_once_with(999)
            self.channel.send.assert_called_once()

        asyncio.run(async_test())


class TestBirthdayCatchUp(unittest.TestCase):
    """The loop only fires at 08:00, so startup after 08:00 must catch up."""

    def setUp(self):
        self.bot = MagicMock()
        self.bot.wait_until_ready = AsyncMock()
        self.db_manager = MagicMock()

    def _make_cog(self):
        cog = BirthdayCommand(self.bot, self.db_manager)
        cog.daily_check.cancel()
        return cog

    def _run_before_loop(self, now):
        async def async_test():
            cog = self._make_cog()
            cog._announce_birthdays = AsyncMock()
            with patch.object(BirthdayCommand, "_now", staticmethod(lambda: now)):
                await cog.before_daily_check()
            return cog

        return asyncio.run(async_test())

    def test_startup_before_8am_does_not_announce(self):
        cog = self._run_before_loop(
            datetime.datetime(2025, 7, 15, 7, 59, 0, tzinfo=GERMANY_TZ)
        )
        cog._announce_birthdays.assert_not_called()

    def test_startup_after_8am_catches_up(self):
        cog = self._run_before_loop(
            datetime.datetime(2025, 7, 15, 11, 30, 0, tzinfo=GERMANY_TZ)
        )
        cog._announce_birthdays.assert_awaited_once_with(datetime.date(2025, 7, 15))


class TestBirthdayAgeText(unittest.TestCase):
    def test_age_computation_with_explicit_today(self):
        """Test _compute_age_text with an explicit ``today`` parameter.

        No mocking needed — the optional ``today`` parameter makes the method
        directly testable.
        """
        # Age 35
        bday = datetime.date(1990, 7, 15)
        today = datetime.date(2025, 7, 15)
        text = BirthdayCommand._compute_age_text(bday, today=today)
        self.assertIn("35 Jahre", text)

        # Age 0 (born today)
        bday_today = datetime.date(2025, 7, 15)
        text = BirthdayCommand._compute_age_text(bday_today, today=today)
        self.assertIn("Herzlich willkommen", text)

        # Birthday later in the year — age is one less
        bday_dec = datetime.date(1990, 12, 1)
        text = BirthdayCommand._compute_age_text(bday_dec, today=today)
        self.assertIn("34 Jahre", text)

    def test_age_computation_runs_without_today(self):
        """Smoke test: _compute_age_text works without explicit today (uses real clock)."""
        bday = datetime.date(2000, 1, 1)
        text = BirthdayCommand._compute_age_text(bday)
        # The result depends on the actual date but must be a non-empty string.
        self.assertIsInstance(text, str)
        self.assertTrue(len(text) > 0)

    def test_age_computation_none_birthday(self):
        """_compute_age_text returns empty string for None birthday."""
        text = BirthdayCommand._compute_age_text(None)
        self.assertEqual(text, "")

    def test_birthday_messages_vary(self):
        """Ensure that the message list offers some variation."""
        from commands.birthday_command import BIRTHDAY_MESSAGES

        self.assertGreater(len(BIRTHDAY_MESSAGES), 3)
        for msg in BIRTHDAY_MESSAGES:
            self.assertIn("{mention}", msg)


class TestBirthdayRemoveCommand(unittest.TestCase):
    def _run(self, remove_return):
        async def async_test():
            bot = MagicMock()
            bot.wait_until_ready = AsyncMock()
            db_manager = MagicMock()
            db_manager.remove_birthday = MagicMock(return_value=remove_return)

            cog = BirthdayCommand(bot, db_manager)
            cog.daily_check.cancel()

            interaction = MagicMock()
            interaction.user.id = 123
            interaction.user.display_name = "TestUser"
            interaction.guild.id = 987
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await cog.birthday_remove.callback(cog, interaction)

            db_manager.remove_birthday.assert_called_once_with(123, 987)
            interaction.followup.send.assert_called_once()
            _, kwargs = interaction.followup.send.call_args
            return kwargs.get("embed")

        return asyncio.run(async_test())

    def test_removes_stored_birthday(self):
        embed = self._run(True)
        self.assertIn("gelöscht", embed.title)

    def test_reports_when_nothing_was_stored(self):
        embed = self._run(False)
        self.assertIn("Kein Geburtstag", embed.title)

    def test_reports_db_failure(self):
        """A failed delete must not be reported as 'nothing stored'."""
        embed = self._run(None)
        self.assertIn("Fehler", embed.title)
        self.assertEqual(embed.color.value, discord.Color.red().value)


if __name__ == "__main__":
    unittest.main()
