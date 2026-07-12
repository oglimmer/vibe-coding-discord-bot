import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import timedelta
import openai

from config import Config

logger = logging.getLogger(__name__)


class TldrCommand(commands.Cog):
    """Slash command for summarizing recent channel messages."""

    def __init__(self, bot, db_manager):
        self.bot = bot
        self.openai_client = openai.AsyncOpenAI(api_key=Config.OPENAI_API_KEY)

    @app_commands.command(
        name="tldr",
        description="Fasse die letzten Nachrichten dieses Channels zusammen.",
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
        anzahl: int = 50,
        zeit: str = None,
    ):
        """Summarize recent messages of this channel."""
        await interaction.response.defer(ephemeral=False)

        if not Config.OPENAI_API_KEY:
            await interaction.followup.send(
                "❌ OpenAI API-Schlüssel fehlt. TL;DR kann nicht genutzt werden.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(
                "❌ Dieser Befehl funktioniert nur in Textkanälen.",
                ephemeral=True,
            )
            return

        limit = max(5, min(anzahl, 200))
        after = None
        if zeit == "1h":
            after = discord.utils.utcnow() - timedelta(hours=1)
        elif zeit == "24h":
            after = discord.utils.utcnow() - timedelta(hours=24)

        try:
            messages = []
            async for msg in channel.history(limit=limit, after=after):
                if msg.author.bot:
                    continue
                messages.append(msg)

            if not messages:
                await interaction.followup.send(
                    "Keine Nachrichten gefunden, die zusammengefasst werden können.",
                    ephemeral=True,
                )
                return

            # Build a combined text to send to OpenAI
            lines = []
            total_chars = 0
            max_chars = 3000
            for msg in messages:
                author = msg.author.display_name
                content = msg.content[:200]  # truncate per message
                line = f"{author}: {content}"
                if total_chars + len(line) > max_chars:
                    break
                lines.append(line)
                total_chars += len(line)

            combined = "\n".join(lines)

            summary = await self._summarize(combined)

            embed = discord.Embed(
                title="📝 TL;DR Zusammenfassung",
                description=summary,
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Basierend auf {len(messages)} Nachrichten")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Fehler im tldr-Befehl: {e}", exc_info=True)
            await interaction.followup.send(
                "⚠️ Beim Erstellen der Zusammenfassung ist ein Fehler aufgetreten.",
                ephemeral=True,
            )

    async def _summarize(self, context: str) -> str:
        """Use OpenAI to summarize the given context in German bullet points."""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
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
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI-Summarization failed: {e}")
            raise


async def setup(bot, db_manager):
    await bot.add_cog(TldrCommand(bot, db_manager))
