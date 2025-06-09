import logging
import discord
from discord.ext import commands
from datetime import datetime
from database import DatabaseManager

logger = logging.getLogger(__name__)

class GreetingsCommand(commands.Cog):
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager

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
            guild_id = interaction.guild.id if interaction.guild else None
            # adapt this call to your database layer
            greetings = self.bot.db_manager.get_todays_greetings(guild_id)

            embed = discord.Embed(
                title="Today's Greetings 👋",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            if not greetings:
                embed.description = "No one has greeted today yet! Be the first to say good morning! 🌅"
                embed.color = discord.Color.orange()
            else:
                # Group by user and sum reaction counts
                user_reactions = {}
                latest_times = {}
                total_reactions = 0
                
                for g in greetings:
                    name = g.username
                    if name not in user_reactions:
                        user_reactions[name] = 0
                        latest_times[name] = g.greeting_time
                    
                    user_reactions[name] += g.reaction_count
                    total_reactions += g.reaction_count
                    
                    # Update latest time
                    if g.greeting_time > latest_times[name]:
                        latest_times[name] = g.greeting_time

                # Sort by reaction count (descending)
                sorted_users = sorted(user_reactions.items(), key=lambda x: x[1], reverse=True)
                lines = []
                for i, (user, reaction_count) in enumerate(sorted_users, 1):
                    time_str = self.format_time(latest_times[user])
                    reaction_emoji = "🔥" if reaction_count > 5 else "👍" if reaction_count > 2 else "👋"
                    lines.append(f"{i}. **{user}** - {reaction_count} reactions {reaction_emoji} (latest: {time_str})")

                embed.description = "\n".join(lines)
                embed.add_field(name="Total Reactions Today", value=str(total_reactions), inline=True)
                embed.add_field(name="Unique Greeters", value=str(len(user_reactions)), inline=True)

                first = greetings[0]
                last = greetings[-1]
                embed.add_field(name="First Greeting", value=f"{first.username} at {self.format_time(first.greeting_time)}", inline=True)
                if len(greetings) > 1:
                    embed.add_field(name="Latest Greeting", value=f"{last.username} at {self.format_time(last.greeting_time)}", inline=True)

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
            embed = discord.Embed(
                title="🌍 Recognized Greetings",
                description="The bot recognizes all of these greetings and will react with 👋:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            # English greetings
            english_greetings = [
                "morning", "good morning", "gm", "gn", "good night",
                "hello", "hi", "hey", "good evening", "evening",
                "yo", "sup", "whatsup", "what's up", "howdy",
                "hiya", "heya", "hi there", "greetings", "hey there",
                "top of the morning", "nighty night", "good day"
            ]

            # German greetings
            german_greetings = [
                "guten morgen", "morgen", "moin", "moin moin",
                "servus", "hallo", "hi", "hey", "tach", "tag",
                "guten tag", "guten abend", "abend", "n8", "nacht",
                "gute nacht", "tschüss", "ciao", "bye", "tschau",
                "grüß dich", "na", "alles klar", "na du", "ey", "was geht"
            ]

            # Regional variations (Austria/Switzerland)
            regional_greetings = [
                "grüezi", "grüß gott", "pfiat di", "baba",
                "hoi", "salü", "servas", "ade", "tschau zäme",
                "griaß di", "grüzi mitenand", "habedere"
            ]

            # International greetings
            international_greetings = [
                "salut", "bonjour", "bonsoir", "buongiorno",
                "buenos días", "buenas noches", "hola",
                "namaste", "shalom", "ciao", "konnichiwa",
                "annyeong", "hej", "hallå", "hei", "hola amigo",
                "ola", "ahlan", "salaam", "merhaba", "dobry den"
            ]

            embed.add_field(
                name="🇺🇸 English",
                value=", ".join([f"`{g}`" for g in english_greetings]),
                inline=False
            )

            embed.add_field(
                name="🇩🇪 German",
                value=", ".join([f"`{g}`" for g in german_greetings]),
                inline=False
            )

            embed.add_field(
                name="🏔️ Regional (Austria/Switzerland)",
                value=", ".join([f"`{g}`" for g in regional_greetings]),
                inline=False
            )

            embed.add_field(
                name="🌐 International",
                value=", ".join([f"`{g}`" for g in international_greetings]),
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

async def setup(bot, db_manager):
    await bot.add_cog(GreetingsCommand(bot, db_manager))