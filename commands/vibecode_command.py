"""
Discord command handling for the vibecode functionality.

/vibecode lets any user ask the bot to implement a new feature for itself:
a Kubernetes Job runs an agentic coding AI (aider + DeepSeek), verifies the
change with tests and lint, then opens a pull request.
"""

import asyncio
import logging
from datetime import datetime

import discord
from discord.ext import commands

from services.vibecode_service import VibeCodeError, VibeCodeService

logger = logging.getLogger(__name__)

MIN_FEATURE_LENGTH = 20
MAX_LOG_TAIL_CHARS = 900


class VibeCodeCommand(commands.Cog):
    """Discord command handler for the vibecode functionality"""

    def __init__(self, bot, vibecode_service: VibeCodeService):
        self.bot = bot
        self.vibecode_service = vibecode_service

    @discord.app_commands.command(
        name="vibecode",
        description="Lass den Bot ein neues Feature für sich selbst bauen (erstellt einen PR)",
    )
    @discord.app_commands.describe(
        feature="Beschreibe das Feature, das der Bot bekommen soll"
    )
    async def vibecode(self, interaction: discord.Interaction, feature: str):
        try:
            if len(feature.strip()) < MIN_FEATURE_LENGTH:
                await interaction.response.send_message(
                    "❌ Bitte beschreibe das Feature etwas ausführlicher "
                    f"(mindestens {MIN_FEATURE_LENGTH} Zeichen).",
                    ephemeral=True,
                )
                return

            try:
                job_name = await self.vibecode_service.start_job(
                    user_id=interaction.user.id,
                    username=interaction.user.display_name,
                    feature=feature,
                )
            except VibeCodeError as e:
                await interaction.response.send_message(f"❌ {e}", ephemeral=True)
                return

            await interaction.response.send_message(
                embed=self._create_started_embed(interaction.user, feature, job_name)
            )

            # Watch in the background; the job can run far longer than the
            # 15-minute interaction token, so results go to the channel.
            asyncio.create_task(
                self._watch_job(interaction, job_name, feature),
                name=f"vibecode-watch-{job_name}",
            )

        except Exception as e:
            logger.error(f"Error in vibecode command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ **Something went wrong.** Please try again later.",
                    ephemeral=True,
                )

    async def _watch_job(
        self, interaction: discord.Interaction, job_name: str, feature: str
    ):
        try:
            result = await self.vibecode_service.wait_for_job(job_name)

            if result.succeeded:
                embed = self._create_success_embed(feature, result)
            else:
                embed = self._create_failure_embed(feature, result)

            destination = interaction.channel or interaction.user
            await destination.send(content=interaction.user.mention, embed=embed)

        except Exception as e:
            logger.error(f"Error watching vibecode job {job_name}: {e}")

    def _create_started_embed(self, user, feature, job_name):
        embed = discord.Embed(
            title="🛠️ Vibecode gestartet",
            description=(
                "Der Coding-Agent baut jetzt dein Feature. Das kann eine "
                "Weile dauern - ich melde mich hier, sobald der PR fertig ist."
            ),
            color=0x1337FF,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Feature", value=feature[:1000], inline=False)
        embed.add_field(name="Job", value=f"`{job_name}`", inline=True)
        embed.add_field(name="Angefordert von", value=user.mention, inline=True)
        embed.set_footer(text="Vibe Coding Discord Bot")
        return embed

    def _create_success_embed(self, feature, result):
        embed = discord.Embed(
            title="✅ Vibecode fertig - PR erstellt!",
            description=(
                f"Das Feature wurde implementiert und getestet.\n"
                f"**Pull Request:** {result.pr_url or 'siehe Repository'}"
            ),
            color=0x2ECC71,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Feature", value=feature[:1000], inline=False)
        if result.branch:
            embed.add_field(name="Branch", value=f"`{result.branch}`", inline=True)
        embed.set_footer(text="Vibe Coding Discord Bot")
        return embed

    def _create_failure_embed(self, feature, result):
        embed = discord.Embed(
            title="❌ Vibecode gescheitert",
            description=result.reason or "Unbekannter Fehler.",
            color=0xE74C3C,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Feature", value=feature[:1000], inline=False)
        if result.log_tail:
            tail = result.log_tail[-MAX_LOG_TAIL_CHARS:]
            embed.add_field(
                name="Log (Ende)", value=f"```\n{tail}\n```"[:1024], inline=False
            )
        embed.set_footer(text="Vibe Coding Discord Bot")
        return embed


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(VibeCodeCommand(bot, VibeCodeService()))
