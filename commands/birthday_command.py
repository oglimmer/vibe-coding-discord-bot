import asyncio
import logging
import random
import datetime as dt
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config
from database import DatabaseManager

logger = logging.getLogger(__name__)

GERMANY_TZ = ZoneInfo("Europe/Berlin")
BIRTHDAY_HOUR = 8
ANNOUNCE_TIME = dt.time(hour=BIRTHDAY_HOUR, tzinfo=GERMANY_TZ)

BIRTHDAY_MESSAGES = [
    "🎂 Alles Gute zum Geburtstag, {mention}! Lass es dir heute so richtig gut gehen! 🎉",
    "🎉 Happy Birthday, {mention}! Möge dein Tag voller Freude, Kuchen und guter Laune sein! 🎂",
    "🎈 Herzlichen Glückwunsch zum Geburtstag, {mention}! Feier schön und lass dich reich beschenken! 🎁",
    "🥳 Happy Birthday, {mention}! Ein weiteres Jahr weiser, cooler und fantastischer! Genieß deinen Tag! 🎂",
    "🎂 Geburtstagskind-Alarm! Alles Liebe zum Geburtstag, {mention}! Mögen all deine Wünsche in Erfüllung gehen! ✨",
    "🎉 Heute ist DEIN Tag, {mention}! Herzlichen Glückwunsch zum Geburtstag und ein wunderbares neues Lebensjahr! 🎈",
    "🍰 Alles Gute, {mention}! Möge dein Geburtstagskuchen so groß sein wie dein Herz! 🎂",
    "🎁 Herzlichen Glückwunsch, {mention}! Ein Hoch auf dich und deinen besonderen Tag! 🥂🎂",
    "🎂 Juhu, {mention} hat Geburtstag! Feier schön, genieß den Tag und lass dich feiern! 🎉",
    "🌟 Alles Liebe zum Geburtstag, {mention}! Möge das kommende Jahr dein bestes werden! 🎂✨",
]


class BirthdayCommand(commands.Cog):
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    @staticmethod
    def _now():
        """Current time in Germany. A seam for tests, so they need no clock patching."""
        return dt.datetime.now(GERMANY_TZ)

    @tasks.loop(time=ANNOUNCE_TIME)
    async def daily_check(self):
        await self._announce_birthdays(self._now().date())

    @daily_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()
        # The loop only ever fires at the next 08:00, so a bot that was down or
        # restarted after 08:00 would skip the day entirely. Catch up on start;
        # the DB claim keeps this from double-posting if 08:00 already ran.
        now = self._now()
        if now.hour >= BIRTHDAY_HOUR:
            await self._announce_birthdays(now.date())

    async def _announce_birthdays(self, today):
        """Greet everyone whose birthday is *today*, at most once per day."""
        try:
            channel_id = Config.BIRTHDAY_CHANNEL_ID or Config.ANNOUNCEMENT_CHANNEL_ID
            if not channel_id:
                logger.warning(
                    "BIRTHDAY_CHANNEL_ID and ANNOUNCEMENT_CHANNEL_ID are not set — "
                    "skipping birthday announcements"
                )
                return

            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.error(
                    f"Cannot find birthday channel {channel_id} — "
                    "skipping birthday announcements"
                )
                return

            birthdays = await asyncio.to_thread(
                self.db_manager.get_birthdays_for_today, today
            )

            if not birthdays:
                logger.info("No birthdays today")
                return

            # Claim only once there is something to send, so that a missing
            # channel or an unreadable table leaves the day open for a retry.
            claimed = await asyncio.to_thread(
                self.db_manager.try_claim_birthday_announcement, today
            )
            if not claimed:
                logger.info(f"Birthdays for {today} were already announced — skipping")
                return

            logger.info(
                f"Announcing {len(birthdays)} birthday(s) today: "
                f"{[b['username'] for b in birthdays]}"
            )

            sent = 0
            for bday in birthdays:
                try:
                    user = self.bot.get_user(bday["user_id"])
                    if user is None:
                        try:
                            user = await self.bot.fetch_user(bday["user_id"])
                        except discord.NotFound:
                            logger.warning(
                                f"User {bday['user_id']} ({bday['username']}) "
                                "not found — skipping birthday greeting"
                            )
                            continue

                    message_template = random.choice(BIRTHDAY_MESSAGES)
                    greeting = message_template.format(mention=user.mention)
                    age_text = self._compute_age_text(bday["birthday"], today=today)
                    embed = discord.Embed(
                        title="🎂 Geburtstag! 🎂",
                        description=f"{greeting}\n\n{age_text}",
                        color=discord.Color.gold(),
                    )
                    embed.set_footer(text="Vom ganzen Server — feier schön! 🎉")
                    await channel.send(embed=embed)
                    sent += 1
                    logger.info(
                        f"Sent birthday greeting for {bday['username']} "
                        f"({bday['user_id']})"
                    )
                except Exception as e:
                    logger.error(
                        f"Error sending birthday greeting for "
                        f"{bday['username']} ({bday['user_id']}): {e}"
                    )

            # Nothing got through: drop the claim so a restart can try again.
            # A partial send keeps it, so nobody is greeted twice.
            if sent == 0:
                logger.warning(
                    f"No birthday greeting could be delivered for {today} — "
                    "releasing the claim for a later retry"
                )
                await asyncio.to_thread(
                    self.db_manager.release_birthday_announcement, today
                )
        except Exception as e:
            logger.error(f"Error in birthday daily check: {e}", exc_info=True)

    @staticmethod
    def _compute_age_text(birthday_date, today=None):
        """Return a text like 'Du wirst heute 30 Jahre alt!' or an age-neutral variant.

        Parameters
        ----------
        birthday_date : datetime.date or None
            The stored birthday.
        today : datetime.date or None
            Override for "today" (optional — defaults to the current date in
            Germany).  Useful in tests to avoid patching the clock.
        """
        if birthday_date is None:
            return ""
        if hasattr(birthday_date, "date") and callable(birthday_date.date):
            birthday_date = birthday_date.date()
        if today is None:
            today = dt.datetime.now(GERMANY_TZ).date()
        age = today.year - birthday_date.year
        if (today.month, today.day) < (birthday_date.month, birthday_date.day):
            age -= 1
        if age > 0:
            return f"Du wirst heute **{age} Jahre** alt! 🎂"
        return "Herzlich willkommen in der Welt! 👶🍼"

    @app_commands.command(
        name="birthday-set",
        description="Trage deinen Geburtstag ein (Format: dd-mm-yyyy, z.B. 15-07-1990)",
    )
    @app_commands.describe(
        datum="Dein Geburtsdatum im Format dd-mm-yyyy (z.B. 15-07-1990)"
    )
    async def birthday_set(self, interaction: discord.Interaction, datum: str):
        """Set or update the user's birthday."""
        await interaction.response.defer(ephemeral=True)
        try:
            # Parse the dd-mm-yyyy format
            try:
                parsed = dt.datetime.strptime(datum, "%d-%m-%Y").date()
            except ValueError:
                embed = discord.Embed(
                    title="❌ Ungültiges Datum",
                    description=(
                        "Bitte gib dein Geburtsdatum im Format **dd-mm-yyyy** an.\n"
                        "Beispiel: `15-07-1990` für den 15. Juli 1990."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Basic sanity: not in the future
            today = self._now().date()
            if parsed > today:
                embed = discord.Embed(
                    title="❌ Datum in der Zukunft",
                    description=(
                        "Dein Geburtsdatum kann nicht in der Zukunft liegen. "
                        "Bitte gib ein gültiges Datum ein."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Not too far in the past (older than 130 years)
            if today.year - parsed.year > 130:
                embed = discord.Embed(
                    title="❌ Datum zu weit in der Vergangenheit",
                    description=(
                        "Bitte gib ein gültiges Geburtsdatum ein. "
                        "Datumsangaben die über 130 Jahre in der Vergangenheit liegen "
                        "werden nicht akzeptiert."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            server_id = interaction.guild.id if interaction.guild else None
            username = interaction.user.display_name

            success = await asyncio.to_thread(
                self.db_manager.set_birthday,
                interaction.user.id,
                username,
                parsed,
                server_id,
            )

            if success:
                formatted = parsed.strftime("%d.%m.%Y")
                embed = discord.Embed(
                    title="🎂 Geburtstag gespeichert!",
                    description=(
                        f"Dein Geburtstag wurde auf den **{formatted}** gesetzt.\n"
                        "Am großen Tag wirst du um 8:00 Uhr morgens automatisch "
                        "eine Geburtstagsnachricht erhalten! 🎉"
                    ),
                    color=discord.Color.green(),
                )
                embed.set_footer(
                    text="Ändern mit /birthday-set, löschen mit /birthday-remove."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(
                    f"Birthday set for {username} ({interaction.user.id}): {parsed}"
                )
            else:
                embed = discord.Embed(
                    title="❌ Fehler",
                    description=(
                        "Beim Speichern deines Geburtstags ist ein Fehler aufgetreten. "
                        "Bitte versuche es später noch einmal."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in birthday-set command: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Fehler",
                description=(
                    "Es ist ein unerwarteter Fehler aufgetreten. "
                    "Bitte versuche es später noch einmal."
                ),
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="birthday-remove",
        description="Lösche deinen gespeicherten Geburtstag",
    )
    async def birthday_remove(self, interaction: discord.Interaction):
        """Remove the user's stored birthday."""
        await interaction.response.defer(ephemeral=True)
        try:
            removed = await asyncio.to_thread(
                self.db_manager.remove_birthday, interaction.user.id
            )

            if removed is None:
                embed = discord.Embed(
                    title="❌ Fehler",
                    description=(
                        "Beim Löschen deines Geburtstags ist ein Fehler aufgetreten. "
                        "Bitte versuche es später noch einmal."
                    ),
                    color=discord.Color.red(),
                )
            elif removed:
                embed = discord.Embed(
                    title="🗑️ Geburtstag gelöscht",
                    description=(
                        "Dein Geburtstag wurde gelöscht. Du bekommst keine "
                        "automatischen Glückwünsche mehr."
                    ),
                    color=discord.Color.green(),
                )
                logger.info(
                    f"Birthday removed for {interaction.user.display_name} "
                    f"({interaction.user.id})"
                )
            else:
                embed = discord.Embed(
                    title="Kein Geburtstag gespeichert",
                    description=(
                        "Für dich ist kein Geburtstag hinterlegt — "
                        "es gibt also nichts zu löschen."
                    ),
                    color=discord.Color.blue(),
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in birthday-remove command: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Fehler",
                description=(
                    "Es ist ein unerwarteter Fehler aufgetreten. "
                    "Bitte versuche es später noch einmal."
                ),
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot, db_manager):
    await bot.add_cog(BirthdayCommand(bot, db_manager))
