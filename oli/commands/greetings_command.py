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
    
    @discord.app_commands.command(name="greetings", description="Show all users who have greeted today")
    async def greetings(self, interaction: discord.Interaction):
        try:
            today = datetime.now().date()
            greetings_data = self.db_manager.get_daily_greetings(today)
            
            if not greetings_data:
                embed = discord.Embed(
                    description=f"""
> ## {today.strftime('%B %d, %Y')}
> 
> **No greetings yet today**
> 
> *Be the first to say good morning!*
                    """,
                    color=0x2F3136,
                    timestamp=datetime.now()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            greeting_count = len(greetings_data)
            unique_users = len(set(g['user_id'] for g in greetings_data))
            
            # Create motivational message
            if greeting_count >= 10:
                vibe = "Amazing activity today"
                vibe_desc = "The community is thriving"
            elif greeting_count >= 5:
                vibe = "Great community spirit"
                vibe_desc = "Keep up the good energy"
            else:
                vibe = "Growing stronger each day"
                vibe_desc = "Every greeting counts"
            
            avg_per_person = round(greeting_count/unique_users, 1) if unique_users > 0 else 0
            
            # Modern card-style embed
            embed = discord.Embed(
                description=f"""
> ## {today.strftime('%B %d, %Y')}
> 
> **{greeting_count}** greetings from **{unique_users}** members
> 
> `{greeting_count} messages` • `{unique_users} people` • `{avg_per_person} avg`
> 
> *{vibe} — {vibe_desc}*
                """,
                color=0x2F3136,
                timestamp=datetime.now()
            )
            
            # Create recent greetings list with minimal design
            if greetings_data:
                greeting_lines = []
                for i, greeting in enumerate(greetings_data[:5]):
                    # Convert timedelta to time string
                    td = greeting['greeting_time']
                    hours, remainder = divmod(td.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_str = f"{int(hours):02d}:{int(minutes):02d}"
                    
                    # Clean message truncation
                    greeting_text = greeting['greeting_message'][:30] + "..." if len(greeting['greeting_message']) > 30 else greeting['greeting_message']
                    
                    # Minimal ranking system
                    rank = ["①", "②", "③", "④", "⑤"][i]
                    greeting_lines.append(f"`{time_str}` **{greeting['username']}** — {greeting_text}")
                
                recent_greetings = "\n".join(greeting_lines)
                
                # Show remaining count
                remaining_text = ""
                if len(greetings_data) > 5:
                    remaining = len(greetings_data) - 5
                    remaining_text = f"\n\n*+{remaining} more today*"
                
                embed.add_field(
                    name="Recent Activity",
                    value=f"```\n{recent_greetings}\n```{remaining_text}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Greetings command executed by {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error in greetings command: {e}")
            await interaction.response.send_message(
                "Sorry, there was an error retrieving the greetings data.", 
                ephemeral=True
            )

    @discord.app_commands.command(name="greetings-help", description="Learn about the greetings system and supported languages")
    async def greetings_help(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                description=f"""
> ## Greetings System Help
> 
> **How it works**
> Send any greeting message and I'll react with 👋
> 
> **Commands**
> `/greetings` — View today's greeting activity
> `/greetings-help` — Show this help message
                """,
                color=0x2F3136,
                timestamp=datetime.now()
            )
            
            # Supported languages
            languages_text = """
**English**
`morning` `good morning` `gm` `hello` `hi` `hey`
`good evening` `evening` `gn` `good night`
`yo` `sup` `whatsup` `what's up` `howdy`

**German**
`guten morgen` `morgen` `moin` `moin moin` `servus`
`hallo` `tach` `tag` `guten tag` `guten abend`
`abend` `n8` `nacht` `gute nacht` `tschüss`
`ciao` `bye` `tschau`

**Regional**
`grüezi` `grüß gott` `pfiat di` `baba`

**International**
`salut` `bonjour` `bonsoir` `buongiorno`
`buenos días` `buenas noches` `hola`
            """
            
            embed.add_field(
                name="Supported Greetings",
                value=languages_text,
                inline=False
            )
            
            features_text = """
• **Auto-detection** — I recognize greetings in any message
• **Multi-language** — Support for 40+ greetings across languages
• **Daily tracking** — All greetings are saved and displayed
• **Statistics** — View community activity and engagement
• **Simple reactions** — Clean 👋 responses without message spam
            """
            
            embed.add_field(
                name="Features",
                value=features_text,
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Greetings help command executed by {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error in greetings help command: {e}")
            await interaction.response.send_message(
                "Sorry, there was an error displaying the help information.", 
                ephemeral=True
            )

async def setup(bot, db_manager):
    await bot.add_cog(GreetingsCommand(bot, db_manager))