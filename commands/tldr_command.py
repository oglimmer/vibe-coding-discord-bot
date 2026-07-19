import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import timedelta
from typing import Optional
import openai

from config import Config

logger = logging.getLogger(__name__)


class TldrCommand(commands.Cog):
    """Slash command for summarizing recent channel messages."""

    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.ai_client = openai.AsyncOpenAI(
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
        )

    @app_commands.command(
        name="tldr",
        description="Fasse die letzten Nachrichten dieses Channels zusammen.",
    )
    @app_commands.describe(
        anzahl="Wie viele der letzten Nachrichten durchsucht werden (5–200)",
        zeit="Optional auf die letzte Stunde oder 24 Stunden beschränken",
    )
    @app_commands.choices(
        zeit=[
            app_commands.Choice(name="Letzte Stunde", value="1h"),
            app_commands.Choice(name="Letzte 24 Stunden", value="24h"),
        ],
    )
    async def tldr(
        self,
        interaction: discord.Interaction,
        anzahl: app_commands.Range[int, 5, 200] = 50,
        zeit: Optional[str] = None,
    ):
        """Summarize recent messages of this channel."""
        # Validate synchronously first so these errors stay private; only
        # defer (which posts a public placeholder) once we know we'll work.
        if not Config.DEEPSEEK_API_KEY:
            await interaction.response.send_message(
                "❌ DeepSeek API-Schlüssel fehlt. TL;DR kann nicht genutzt werden.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "❌ Dieser Befehl funktioniert nur in Textkanälen.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=False)

        limit = max(5, min(anzahl, 200))
        after = None
        if zeit == "1h":
            after = discord.utils.utcnow() - timedelta(hours=1)
        elif zeit == "24h":
            after = discord.utils.utcnow() - timedelta(hours=24)

        try:
            # Opt-in is per guild: consent given on another server must not
            # leak messages into this one's summaries.
            opted_in = self.db_manager.get_tldr_opted_in_users(interaction.guild_id)

            messages = []
            skipped_no_optin = 0
            # Always fetch newest-first so a limit keeps the *most recent*
            # messages (also relevant when `after` is set for time windows).
            async for msg in channel.history(
                limit=limit, after=after, oldest_first=False
            ):
                if msg.author.bot:
                    continue
                # Nothing to summarize for attachment-/embed-/sticker-only posts.
                if not msg.content.strip():
                    continue
                # /tldr is opt-in only: skip anyone who hasn't explicitly
                # opted in to having their messages summarized.
                if msg.author.id not in opted_in:
                    skipped_no_optin += 1
                    continue
                messages.append(msg)

            if not messages:
                if skipped_no_optin:
                    await interaction.followup.send(
                        "Keine Nachrichten zum Zusammenfassen: Niemand mit "
                        "Nachrichten in diesem Zeitraum hat `/tldr_optin` "
                        "aktiviert. Nur Nachrichten von Nutzern mit Opt-in "
                        "werden zusammengefasst.",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        "Keine Nachrichten gefunden, die zusammengefasst werden können.",
                        ephemeral=True,
                    )
                return

            # Build a combined text to send to the AI. History is newest-first,
            # so reverse it to give the model chronological order.
            lines = []
            total_chars = 0
            max_chars = 3000
            used_messages = 0
            for msg in reversed(messages):
                author = msg.author.display_name
                content = msg.content[:200]  # truncate per message
                line = f"{author}: {content}"
                if total_chars + len(line) > max_chars:
                    break
                lines.append(line)
                total_chars += len(line)
                used_messages += 1

            combined = "\n".join(lines)

            summary = await self._summarize(combined)

            embed = discord.Embed(
                title="📝 TL;DR Zusammenfassung",
                description=summary,
                color=discord.Color.blue(),
            )
            footer = f"Basierend auf {used_messages} Nachrichten"
            if skipped_no_optin:
                footer += f" · {skipped_no_optin} ausgeschlossen (kein Opt-in)"
            embed.set_footer(text=footer)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Fehler im tldr-Befehl: {e}", exc_info=True)
            await interaction.followup.send(
                "⚠️ Beim Erstellen der Zusammenfassung ist ein Fehler aufgetreten.",
                ephemeral=True,
            )

    @app_commands.command(
        name="tldr_optin",
        description="Erlaube, dass deine Nachrichten in /tldr zusammengefasst werden.",
    )
    async def tldr_optin(self, interaction: discord.Interaction):
        """Include the invoking user's messages in future /tldr summaries.

        /tldr is opt-in only, so nothing of a user's is summarized until they
        run this command. Consent applies only to the server it was given on.
        """
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "❌ Dieser Befehl funktioniert nur auf einem Server, da das "
                "Opt-in pro Server gilt.",
                ephemeral=True,
            )
            return

        ok = self.db_manager.set_tldr_optin(
            interaction.guild_id, interaction.user.id, True
        )
        if ok:
            await interaction.response.send_message(
                "🔔 Deine Nachrichten können ab jetzt auf diesem Server in "
                "/tldr-Zusammenfassungen einfließen und werden dafür an die KI "
                "gesendet. Mit `/tldr_optout` kannst du das wieder rückgängig machen.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "⚠️ Deine Einstellung konnte nicht gespeichert werden. "
                "Bitte später erneut versuchen.",
                ephemeral=True,
            )

    @app_commands.command(
        name="tldr_optout",
        description="Schließe deine Nachrichten wieder von /tldr-Zusammenfassungen aus.",
    )
    async def tldr_optout(self, interaction: discord.Interaction):
        """Exclude the invoking user's messages from /tldr summaries again.

        This is the default state; the command exists to undo a prior
        /tldr_optin on this server.
        """
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "❌ Dieser Befehl funktioniert nur auf einem Server, da das "
                "Opt-in pro Server gilt.",
                ephemeral=True,
            )
            return

        ok = self.db_manager.set_tldr_optin(
            interaction.guild_id, interaction.user.id, False
        )
        if ok:
            await interaction.response.send_message(
                "🔕 Deine Nachrichten werden auf diesem Server aus "
                "/tldr-Zusammenfassungen ausgeschlossen und nicht mehr an die "
                "KI gesendet.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "⚠️ Deine Einstellung konnte nicht gespeichert werden. "
                "Bitte später erneut versuchen.",
                ephemeral=True,
            )

    async def _summarize(self, context: str) -> str:
        """Use DeepSeek to summarize the given context in German bullet points."""
        try:
            response = await self.ai_client.chat.completions.create(
                model=Config.TLDR_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Du bist ein KI-Assistent, der Chatverläufe in "
                            "deutscher Sprache kurz und prägnant in Stichpunkten "
                            "zusammenfasst. Verwende maximal 3-5 Aufzählungspunkte."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Fasse folgenden Chatverlauf zusammen:\n\n{context}",
                    },
                ],
                max_tokens=500,
                temperature=0.5,
                timeout=30,
            )
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    return content.strip()
            raise ValueError("DeepSeek returned an empty summary")
        except Exception as e:
            logger.error(f"DeepSeek summarization failed: {e}")
            raise


async def setup(bot, db_manager):
    await bot.add_cog(TldrCommand(bot, db_manager))
