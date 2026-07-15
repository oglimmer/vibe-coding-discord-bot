import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, AsyncMock

import discord
from discord.ext import commands

from commands.birthday_command import BirthdayCommand, BIRTHDAY_GREETINGS


class TestBirthdayCommand(unittest.TestCase):
    def test_parse_birthday_valid(self):
        self.assertEqual(BirthdayCommand._parse_birthday("25-12-2000"), (25, 12))
        self.assertEqual(BirthdayCommand._parse_birthday("01-01-2023"), (1, 1))

    def test_parse_birthday_invalid(self):
        for value in ("32-13-2000", "12-25-2000", "25-12-99", "abc", "25-12-0xxx"):
            self.assertIsNone(BirthdayCommand._parse_birthday(value))

    def test_birthday_set_success(self):
        async def _run():
            fake_bot = MagicMock(spec=commands.Bot)

            with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w+", delete=False
            ) as tmp:
                json.dump({}, tmp)
                tmp_path = tmp.name

            try:
                cog = BirthdayCommand(fake_bot, birthdays_file=tmp_path)
                interaction = MagicMock(spec=discord.Interaction)
                interaction.user.id = 12345
                interaction.user.mention = "<@12345>"
                interaction.response.send_message = AsyncMock()

                await cog.birthday_set.callback(cog, interaction, birthday="14-02-1995")

                # Verify response
                interaction.response.send_message.assert_awaited_once()
                text = interaction.response.send_message.call_args[0][0]
                self.assertIn("14-02-1995", text)
                self.assertIn("✅", text)
                self.assertIn("12345", cog.birthdays)
                self.assertEqual(cog.birthdays["12345"], "14-02-1995")

                # Verify persistence
                with open(tmp_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertIn("12345", loaded)
                self.assertEqual(loaded["12345"], "14-02-1995")
            finally:
                os.unlink(tmp_path)

        asyncio.run(_run())

    def test_birthday_set_invalid(self):
        async def _run():
            fake_bot = MagicMock(spec=commands.Bot)
            with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w+", delete=False
            ) as tmp:
                json.dump({}, tmp)
                tmp_path = tmp.name

            try:
                cog = BirthdayCommand(fake_bot, birthdays_file=tmp_path)
                interaction = MagicMock(spec=discord.Interaction)
                interaction.user.id = 12345
                interaction.response.send_message = AsyncMock()

                await cog.birthday_set.callback(cog, interaction, birthday="99-99-9999")

                interaction.response.send_message.assert_awaited_once()
                text = interaction.response.send_message.call_args[0][0]
                self.assertIn("❌", text)
                # Ensure that the file hasn't changed
                with open(tmp_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertNotIn("12345", loaded)
            finally:
                os.unlink(tmp_path)

        asyncio.run(_run())

    def test_greetings_vary(self):
        self.assertGreater(len(BIRTHDAY_GREETINGS), 1)


if __name__ == "__main__":
    unittest.main()
