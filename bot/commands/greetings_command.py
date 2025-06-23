import logging
import discord
from discord.ext import commands
from datetime import datetime
from greeting_client import GreetingClient

logger = logging.getLogger(__name__)

class GreetingsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.greeting_client = bot.greeting_client

    @staticmethod
    def format_time(dt) -> str:
        from datetime import timedelta
        if isinstance(dt, timedelta):
            # Convert timedelta to hours:minutes format
            total_seconds = int(dt.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}"
        else:
            return dt.strftime("%H:%M")

    @discord.app_commands.command(name="greetings", description="Show today's greeting activity")
    async def greetings(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            guild_id = str(interaction.guild.id) if interaction.guild else None
            greeting_data = await self.greeting_client.get_todays_greetings(guild_id)

            embed = discord.Embed(
                title="Today's Greetings 👋",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            if not greeting_data.get("leaderboard"):
                embed.description = "No one has greeted today yet! Be the first to say good morning! 🌅"
                embed.color = discord.Color.orange()
            else:
                lines = []
                for i, entry in enumerate(greeting_data["leaderboard"], 1):
                    username = entry["username"]
                    reaction_count = entry["reaction_count"]
                    reactions = entry.get("reactions", [])
                    
                    reaction_emoji = "🔥" if reaction_count > 5 else "👍" if reaction_count > 2 else "👋"
                    reaction_str = " ".join(reactions[:3]) if reactions else ""
                    lines.append(f"{i}. **{username}** - {reaction_count} reactions {reaction_emoji} {reaction_str}")

                embed.description = "\n".join(lines)
                embed.add_field(name="Total Reactions Today", value=str(greeting_data["total_reactions"]), inline=True)
                embed.add_field(name="Unique Greeters", value=str(greeting_data["unique_greeters"]), inline=True)

                if greeting_data.get("first_greeting_time"):
                    first_time = datetime.fromisoformat(greeting_data["first_greeting_time"].replace("Z", "+00:00"))
                    embed.add_field(name="First Greeting", value=f"at {first_time.strftime('%H:%M')}", inline=True)
                
                if greeting_data.get("latest_greeting_time"):
                    latest_time = datetime.fromisoformat(greeting_data["latest_greeting_time"].replace("Z", "+00:00"))
                    embed.add_field(name="Latest Greeting", value=f"at {latest_time.strftime('%H:%M')}", inline=True)

            embed.set_footer(
                text="Reactions show how much the community appreciated your greetings! Use /greeting-help for all options.",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Greetings command used by {interaction.user} in {interaction.guild}")
        except Exception as e:
            logger.error(f"Error in greetings command: {e}", exc_info=True)
            error_embed = discord.Embed(
                title="❌ Error",
                description="Sorry, I couldn't retrieve the greetings data right now. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)


    @discord.app_commands.command(name="greetings-help", description="Learn about the greetings system and supported languages")
    async def greetings_help(self, interaction: discord.Interaction):
        """
        Display all possible greetings that the bot recognizes.

        Args:
            interaction: Discord interaction object
        """
        await interaction.response.defer()
        try:
            languages = await self.greeting_client.get_supported_languages()
            
            embed = discord.Embed(
                title="🌍 Recognized Greetings",
                description="The bot recognizes all of these greetings and will react with 👋:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            language_flags = {
                "English": "🇺🇸",
                "German": "🇩🇪", 
                "Regional (Austria/Switzerland)": "🏔️",
                "International": "🌐"
            }

            for language, greetings in languages.items():
                flag = language_flags.get(language, "🌐")
                embed.add_field(
                    name=f"{flag} {language}",
                    value=", ".join([f"`{g}`" for g in greetings]),
                    inline=False
                )

            embed.add_field(
                name="💡 How it works",
                value="Simply type any of these greetings in chat and the bot will:\n• React with 👋\n• Count it in your daily greeting stats\n• Show it in `/greetings` command",
                inline=False
            )

            embed.set_footer(
                text="New greetings can be added by request! Contact an admin.",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Greeting help command used by {interaction.user}")

        except Exception as e:
            logger.error(f"Error in greeting help command: {e}", exc_info=True)

            error_embed = discord.Embed(
                title="❌ Error",
                description="Sorry, I couldn't retrieve the greeting information right now. Please try again later.",
                color=discord.Color.red()
            )

            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GreetingsCommand(bot))