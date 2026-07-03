"""
Discord command handling for the about functionality.
Shows bot information (build metadata) plus live runtime stats:
uptime, gateway latency, server/user reach, memory, and library versions.
"""

import json
import logging
import math
import os
import platform
import resource
import time
from datetime import datetime

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AboutCommand(commands.Cog):
    """Discord command handler for the about functionality"""

    def __init__(self, bot):
        self.bot = bot
        # Captured when the cog loads, i.e. during setup_hook at startup, so
        # this closely tracks process uptime.
        self.start_monotonic = time.monotonic()

    @discord.app_commands.command(
        name="about", description="Show information about this bot"
    )
    async def about(self, interaction: discord.Interaction):
        """Show bot build info and live runtime stats"""
        try:
            embed = self._create_about_embed()
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.", ephemeral=True
            )

    def _create_about_embed(self):
        """Create embed with bot information and runtime stats"""
        embed = discord.Embed(
            title="🤖 Bot Information", color=0x1337FF, timestamp=datetime.now()
        )

        embed.add_field(
            name="Bot Name", value="**Vibe Coding Discord Bot**", inline=True
        )
        embed.add_field(
            name="Purpose", value="1337 Game & Greeting Management", inline=True
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

        # Live runtime stats
        for name, value in self._runtime_fields():
            embed.add_field(name=name, value=value, inline=True)

        embed.set_footer(text="Vibe Coding Discord Bot")
        return embed

    def _runtime_fields(self):
        """Return (name, value) embed fields describing the live runtime."""
        fields = [
            ("⏱️ Uptime", f"`{self._format_uptime(self._uptime_seconds())}`"),
            ("📡 Latency", f"`{self._latency_ms_str()}`"),
            ("🌐 Servers", f"`{len(self.bot.guilds)}`"),
            ("👥 Users", f"`{self._user_count()}`"),
        ]
        memory = self._memory_mb()
        if memory is not None:
            fields.append(("🧠 Memory", f"`{memory:.0f} MB`"))
        fields.append(
            (
                "🐍 Versions",
                f"`Python {platform.python_version()} · "
                f"discord.py {discord.__version__}`",
            )
        )
        return fields

    def _uptime_seconds(self):
        return time.monotonic() - self.start_monotonic

    @staticmethod
    def _format_uptime(seconds):
        """Format a duration in seconds as e.g. '1d 3h 12m 4s'."""
        seconds = int(max(0, seconds))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    def _latency_ms_str(self):
        """Gateway heartbeat latency in ms, or 'n/a' before the first beat."""
        latency = self.bot.latency
        if latency is None or math.isnan(latency):
            return "n/a"
        return f"{latency * 1000:.0f} ms"

    def _user_count(self):
        return sum((guild.member_count or 0) for guild in self.bot.guilds)

    @staticmethod
    def _memory_mb():
        """Resident set size in MB, or None if it can't be read."""
        try:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss is kilobytes on Linux (the deployment target).
            return rss / 1024
        except (ValueError, OSError):
            return None

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
