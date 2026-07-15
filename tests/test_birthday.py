import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.birthday_command import BirthdayCommand, GERMANY_TZ


class TestBirthdaySetCommand(unittest.TestCase):
    def test_birthday_set_valid_date(self):
        async def async_test():
            bot = MagicMock()
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
            self.assertEqual(embed.color.value, discord_color_green())
            self.assertIn("Geburtstag gespeichert", embed.title)

        asyncio.run(async_test())

    def test_birthday_set_valid_date_no_guild(self):
        async def async_test():
            bot = MagicMock()
            db_manager = MagicMock()
            db_manager.set_birthday = MagicMock(return_value=True)
            bot.db_manager = db_manager

            cog = BirthdayCommand(bot, db_manager)
            cog.daily_check.cancel()

            interaction = MagicMock()
            interaction.user.id = 111
            interaction.user.display_name = "DmUser"
            interaction.guild = None
            interaction.response.defer = AsyncMock()
            interaction.followup.send = AsyncMock()

            await cog.birthday_set.callback(cog, interaction, datum="01-01-2000")

            args, _ = db_manager.set_birthday.call_args
            expected_date = datetime.date(2000, 1, 1)
            self.assertEqual(args[2], expected_date)
            self.assertIsNone(args[3])

        asyncio.run(async_test())

    def test_birthday_set_invalid_format(self):
        async def async_test():
            bot = MagicMock()
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


class TestBirthdayDailyCheck(unittest.TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.db_manager = MagicMock()
        self.bot.db_manager = self.db_manager
        self.channel = MagicMock()
        self.channel.send = AsyncMock()
        self.bot.get_channel.return_value = self.channel

    def test_daily_check_not_8am_skips(self):
        async def async_test():
            cog = BirthdayCommand(self.bot, self.db_manager)
            cog.daily_check.cancel()

            fake_now = datetime.datetime(2025, 7, 15, 9, 30, 0, tzinfo=GERMANY_TZ)
            with patch("commands.birthday_command.dt") as mock_dt:
                mock_dt.datetime.now.return_value = fake_now
                mock_dt.datetime.strptime = datetime.datetime.strptime
                await cog.daily_check.coro(cog)

            self.db_manager.get_birthdays_for_today.assert_not_called()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_daily_check_at_8am_sends_greetings(self):
        async def async_test():
            cog = BirthdayCommand(self.bot, self.db_manager)
            cog.daily_check.cancel()

            self.db_manager.get_birthdays_for_today.return_value = [
                {
                    "user_id": 555,
                    "username": "Geburtstagskind",
                    "birthday": datetime.date(1990, 7, 15),
                    "server_id": 1,
                }
            ]

            fake_user = MagicMock()
            fake_user.mention = "<@555>"
            self.bot.get_user.return_value = fake_user

            fake_now = datetime.datetime(2025, 7, 15, 8, 0, 0, tzinfo=GERMANY_TZ)
            with patch("commands.birthday_command.dt") as mock_dt:
                mock_dt.datetime.now.return_value = fake_now
                mock_dt.datetime.strptime = datetime.datetime.strptime
                with patch("commands.birthday_command.Config") as mock_config:
                    mock_config.BIRTHDAY_CHANNEL_ID = 12345
                    mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                    await cog.daily_check.coro(cog)

            self.db_manager.get_birthdays_for_today.assert_called_once()
            self.channel.send.assert_called_once()
            _, kwargs = self.channel.send.call_args
            embed = kwargs.get("embed")
            self.assertIsNotNone(embed)
            self.assertIn("Geburtstag", embed.title)

        asyncio.run(async_test())

    def test_daily_check_skips_when_already_announced(self):
        async def async_test():
            cog = BirthdayCommand(self.bot, self.db_manager)
            cog.daily_check.cancel()

            cog._last_announced_date = datetime.date(2025, 7, 15)

            fake_now = datetime.datetime(2025, 7, 15, 8, 0, 0, tzinfo=GERMANY_TZ)
            with patch("commands.birthday_command.dt") as mock_dt:
                mock_dt.datetime.now.return_value = fake_now
                mock_dt.datetime.strptime = datetime.datetime.strptime
                await cog.daily_check.coro(cog)

            self.db_manager.get_birthdays_for_today.assert_not_called()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_daily_check_no_channel_configured(self):
        async def async_test():
            cog = BirthdayCommand(self.bot, self.db_manager)
            cog.daily_check.cancel()

            self.bot.get_channel.return_value = None

            fake_now = datetime.datetime(2025, 7, 15, 8, 0, 0, tzinfo=GERMANY_TZ)
            with patch("commands.birthday_command.dt") as mock_dt:
                mock_dt.datetime.now.return_value = fake_now
                mock_dt.datetime.strptime = datetime.datetime.strptime
                with patch("commands.birthday_command.Config") as mock_config:
                    mock_config.BIRTHDAY_CHANNEL_ID = 12345
                    mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                    await cog.daily_check.coro(cog)

            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_daily_check_no_birthdays_today(self):
        async def async_test():
            cog = BirthdayCommand(self.bot, self.db_manager)
            cog.daily_check.cancel()

            self.db_manager.get_birthdays_for_today.return_value = []

            fake_now = datetime.datetime(2025, 7, 15, 8, 0, 0, tzinfo=GERMANY_TZ)
            with patch("commands.birthday_command.dt") as mock_dt:
                mock_dt.datetime.now.return_value = fake_now
                mock_dt.datetime.strptime = datetime.datetime.strptime
                with patch("commands.birthday_command.Config") as mock_config:
                    mock_config.BIRTHDAY_CHANNEL_ID = 12345
                    mock_config.ANNOUNCEMENT_CHANNEL_ID = None
                    await cog.daily_check.coro(cog)

            self.db_manager.get_birthdays_for_today.assert_called_once()
            self.channel.send.assert_not_called()

        asyncio.run(async_test())

    def test_age_computation(self):
        """Test the _compute_age_text static method directly."""
        with patch("commands.birthday_command.dt") as mock_dt:
            mock_dt.datetime.now.return_value = datetime.datetime(
                2025, 7, 15, 8, 0, 0, tzinfo=GERMANY_TZ
            )

            # Age 35
            bday = datetime.date(1990, 7, 15)
            text = BirthdayCommand._compute_age_text(bday)
            self.assertIn("35 Jahre", text)

            # Age 0 (born today)
            bday_today = datetime.date(2025, 7, 15)
            text = BirthdayCommand._compute_age_text(bday_today)
            self.assertIn("Herzlich willkommen", text)

    def test_birthday_messages_vary(self):
        """Ensure that the message list offers some variation."""
        from commands.birthday_command import BIRTHDAY_MESSAGES

        self.assertGreater(len(BIRTHDAY_MESSAGES), 3)
        for msg in BIRTHDAY_MESSAGES:
            self.assertIn("{mention}", msg)


def discord_color_green():
    import discord

    return discord.Color.green().value


if __name__ == "__main__":
    unittest.main()
