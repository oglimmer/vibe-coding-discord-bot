import json
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config

logger = logging.getLogger(__name__)

BIRTHDAY_GREETINGS = [
    "🎉 Alles Gute zum Geburtstag, {mention}! 🎂",
    "Herzlichen Glückwunsch, {mention}! Feier schön! 🥳",
    "Happy Birthday, {mention}! Lass es krachen! 🎈🎁",
    "Heute ist dein Tag, {mention}. Genieße ihn! 🎉🍰",
    "Alles Gute, {mention}! Bleib wie du bist! 🎂🎊",
]


class BirthdayCommand(commands.Cog):
    def __init__(self, bot: commands.Bot, birthdays_file: str = None):
        self.bot = bot
        if birthdays_file is None:
            birthdays_file = Config.BIRTHDAY_FILE
        self.birthdays_file = birthdays_file
        self.birthdays = self._load_birthdays()
        self.last_checked_date: str = ""  # "YYYYMMDD"

    def _load_birthdays(self) -> dict:
        try:
            with open(self.birthdays_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("birthdays.json not found – starting with empty data")
            return {}
        except Exception as e:
            logger.error(f"Could not load birthdays: {e}")
            return {}

    def _save_birthdays(self):
        try:
            with open(self.birthdays_file, "w", encoding="utf-8") as f:
                json.dump(self.birthdays, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save birthdays: {e}")

    @staticmethod
    def _parse_birthday(value: str):
        """Return (day, month) as ints if value matches DD-MM-YYYY, else None."""
        try:
            dt = datetime.strptime(value.strip(), "%d-%m-%Y")
            return (dt.day, dt.month)
        except ValueError:
            return None

    @app_commands.command(
        name="birthday-set",
        description="Trage deinen Geburtstag ein (Format TT-MM-JJJJ)",
    )
    async def birthday_set(self, interaction: discord.Interaction, birthday: str):
        parsed = self._parse_birthday(birthday)
        if parsed is None:
            await interaction.response.send_message(
                "❌ Ungültiges Datum. Verwende das Format **TT-MM-JJJJ** "
                "(z.B. 25-12-2000).",
                ephemeral=True,
            )
            return

        self.birthdays[str(interaction.user.id)] = birthday.strip()
        self._save_birthdays()

        await interaction.response.send_message(
            f"✅ Dein Geburtstag wurde gespeichert! 🎉  ({birthday.strip()})",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.birthday_check_loop.is_running():
            self.birthday_check_loop.start()

    @tasks.loop(minutes=1)
    async def birthday_check_loop(self):
        now = datetime.now(ZoneInfo("Europe/Berlin"))
        today_str = now.strftime("%Y%m%d")

        # proceed if we've reached 8:00 local time and haven't run today
        if now.hour * 60 + now.minute < 8 * 60:
            return
        if self.last_checked_date == today_str:
            return

        self.last_checked_date = today_str
        today_day_month = (now.day, now.month)

        for user_id_str, birthday_str in list(self.birthdays.items()):
            bday = self._parse_birthday(birthday_str)
            if bday is None:
                continue
            if bday != today_day_month:
                continue

            user = None
            try:
                user = await self.bot.fetch_user(int(user_id_str))
            except Exception as e:
                logger.warning(f"Could not fetch user {user_id_str} for birthday: {e}")
                continue

            greeting = random.choice(BIRTHDAY_GREETINGS).format(mention=user.mention)

            try:
                await user.send(greeting)
                logger.info(
                    f"Birthday greeting sent to {user.name}#{user.discriminator}"
                )
            except discord.Forbidden:
                logger.warning(f"Could not DM {user_id_str} (maybe DMs disabled)")

    @birthday_check_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(BirthdayCommand(bot))
