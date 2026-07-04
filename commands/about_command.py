"""
Discord command handling for the about functionality.
Shows bot information including build date, git revision, and branch.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime, timezone
import json
import os

logger = logging.getLogger(__name__)


class AboutCommand(commands.Cog):
    """Discord command handler for the about functionality"""

    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now(timezone.utc)

    @discord.app_commands.command(
        name="about", description="Show information about this bot"
    )
    async def about(self, interaction: discord.Interaction):
        """Show bot information including build date, git revision, and branch"""
        try:
            embed = self._create_about_embed()
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.", ephemeral=True
            )

    def _create_about_embed(self):
        """Create embed with bot information"""
        embed = discord.Embed(
            title="🤖 Bot Information", color=0x1337FF, timestamp=datetime.now()
        )

        # Bot name and description
        embed.add_field(
            name="Bot Name", value="**Vibe Coding Discord Bot**", inline=True
        )

        embed.add_field(
            name="Purpose",
            value="1337 Game & Greeting Management\n*Most sophisticated in Discord VibeCoding*",
            inline=True,
        )

        # Build information from build-info.json
        build_info = self._get_build_info()

        if build_info.get("build_time"):
            embed.add_field(
                name="🔨 Build Time",
                value=f"`{build_info['build_time']}`",
                inline=False,
            )

        if build_info.get("git_branch"):
            embed.add_field(
                name="🌿 Git Branch", value=f"`{build_info['git_branch']}`", inline=True
            )

        if build_info.get("git_revision"):
            embed.add_field(
                name="📝 Git Revision",
                value=f"`{build_info['git_revision'][:8]}`",
                inline=True,
            )

        # Runtime information
        embed.add_field(
            name="⚡ Status", value="✅ **Online and Running**", inline=False
        )

        # ----- Runtime statistics (new) -----
        try:
            uptime = self._get_uptime()
        except Exception:
            uptime = "N/A"

        try:
            latency = self.bot.latency
            if latency is not None:
                latency_ms = round(latency * 1000)
                latency_str = f"{latency_ms} ms"
            else:
                latency_str = "N/A"
        except Exception:
            latency_str = "N/A"

        try:
            guild_count = len(self.bot.guilds)
        except Exception:
            guild_count = 0

        try:
            member_count = sum(getattr(g, "member_count", 0) for g in self.bot.guilds)
        except Exception:
            member_count = 0

        try:
            command_count = len(self.bot.tree.get_commands())
        except Exception:
            command_count = 0

        embed.add_field(
            name="📊 Runtime Statistics",
            value=(
                f"**Uptime:** {uptime}\n"
                f"**Latency:** {latency_str}\n"
                f"**Servers:** {guild_count}\n"
                f"**Members:** {member_count}\n"
                f"**Commands:** {command_count}"
            ),
            inline=False,
        )
        # ------------------------------------

        embed.set_footer(text="Vibe Coding Discord Bot")
        return embed

    def _get_uptime(self):
        """Return human-friendly uptime string"""
        delta = datetime.now(timezone.utc) - self.start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0 or days > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return " ".join(parts) if parts else "0 minutes"

    def _get_build_info(self):
        """Get build information from build-info.json file"""
        build_info = {"build_time": None, "git_branch": None, "git_revision": None}

        try:
            build_info_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "build-info.json"
            )
            if os.path.exists(build_info_path):
                with open(build_info_path, "r") as f:
                    data = json.load(f)
                    build_info.update(data)
            else:
                # Fallback for development/local runs
                build_info["build_time"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
                build_info["git_branch"] = "development"
                build_info["git_revision"] = "local-build"

        except Exception as e:
            logger.debug(f"Could not read build info: {e}")
            # Fallback values
            build_info["build_time"] = "Unknown"
            build_info["git_branch"] = "Unknown"
            build_info["git_revision"] = "Unknown"

        return build_info


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(AboutCommand(bot))
