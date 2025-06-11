"""
Discord command handling for the about functionality.
Shows bot information including build date, git revision, and branch.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)


class AboutCommand(commands.Cog):
    """Discord command handler for the about functionality"""
    
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="about", description="Show information about this bot")
    async def about(self, interaction: discord.Interaction):
        """Show bot information including build date, git revision, and branch"""
        try:
            embed = self._create_about_embed()
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    def _create_about_embed(self):
        """Create embed with bot information"""
        embed = discord.Embed(
            title='🤖 Bot Information',
            color=0x1337FF,
            timestamp=datetime.now()
        )
        
        # Bot name and description
        embed.add_field(
            name='Bot Name',
            value='**Vibe Coding Discord Bot**',
            inline=True
        )
        
        embed.add_field(
            name='Purpose',
            value='1337 Game & Greeting Management',
            inline=True
        )
        
        # Build information from build-info.json
        build_info = self._get_build_info()
        
        if build_info.get('build_time'):
            embed.add_field(
                name='🔨 Build Time',
                value=f"`{build_info['build_time']}`",
                inline=False
            )
        
        if build_info.get('git_branch'):
            embed.add_field(
                name='🌿 Git Branch',
                value=f"`{build_info['git_branch']}`",
                inline=True
            )
        
        if build_info.get('git_revision'):
            embed.add_field(
                name='📝 Git Revision',
                value=f"`{build_info['git_revision'][:8]}`",
                inline=True
            )
        
        # Runtime information
        embed.add_field(
            name='⚡ Status',
            value='✅ **Online and Running**',
            inline=False
        )
        
        embed.set_footer(text='Vibe Coding Discord Bot')
        return embed
    
    def _get_build_info(self):
        """Get build information from build-info.json file"""
        build_info = {
            'build_time': None,
            'git_branch': None,
            'git_revision': None
        }
        
        try:
            build_info_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'build-info.json')
            if os.path.exists(build_info_path):
                with open(build_info_path, 'r') as f:
                    data = json.load(f)
                    build_info.update(data)
            else:
                # Fallback for development/local runs
                build_info['build_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
                build_info['git_branch'] = "development"
                build_info['git_revision'] = "local-build"
                
        except Exception as e:
            logger.debug(f"Could not read build info: {e}")
            # Fallback values
            build_info['build_time'] = "Unknown"
            build_info['git_branch'] = "Unknown"
            build_info['git_revision'] = "Unknown"
        
        return build_info


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(AboutCommand(bot))