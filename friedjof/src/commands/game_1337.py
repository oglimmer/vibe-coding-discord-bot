"""
1337 Game Commands with Cron-based Scheduling.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from utils.logger import setup_logger
from utils.time_parser import validate_time_input, format_milliseconds_to_time
from utils.game_1337 import Game1337Manager

logger = setup_logger('commands_1337')


class Game1337Commands(commands.Cog):
    """Commands for the 1337 game with cron-based scheduling."""
    
    def __init__(self, bot):
        self.bot = bot
        self.game_manager = None
    
    async def cog_load(self):
        """Initialize the game manager when cog loads."""
        self.game_manager = Game1337Manager(self.bot.db_manager)
        
        # Set the bot instance for role management
        self.game_manager.set_bot(self.bot)
        
        # Add a game trigger callback (for future notifications)
        self.game_manager.add_game_callback(self._on_game_triggered)
        
        # Start the scheduler
        await self.game_manager.start_scheduler()
        
        logger.info("1337 Game cron commands loaded and scheduler started")
    
    async def cog_unload(self):
        """Clean up when cog unloads."""
        if self.game_manager:
            await self.game_manager.stop_scheduler()
    
    async def _on_game_triggered(self, game_datetime):
        """Called when a game is triggered by the scheduler."""
        logger.info(f"Game 1337 triggered at {game_datetime}")
        # Future: Send notifications, determine winners, etc.
    
    @app_commands.command(name="1337", description="🎮 Platziere eine Echtzeit-Wette im 1337 Game!")
    async def game_1337_normal(self, interaction: discord.Interaction):
        """Place a normal (real-time) bet in the 1337 game."""
        await interaction.response.defer()
        
        try:
            if not self.game_manager:
                await interaction.followup.send("❌ Game Manager nicht verfügbar.", ephemeral=True)
                return
            
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            success, message, play_time_ms = await self.game_manager.place_normal_bet(
                user_id=user_id,
                username=username,
                guild_id=guild_id
            )
            
            if success:
                # Create success embed
                embed = discord.Embed(
                    title="🎯 1337 Game - Wette platziert!",
                    description=message,
                    color=discord.Color.green()
                )
                
                if play_time_ms is not None:
                    formatted_time = format_milliseconds_to_time(play_time_ms)
                    embed.add_field(
                        name="⏱️ Deine Zeit",
                        value=f"`{formatted_time}` nach Spielstart",
                        inline=False
                    )
                
                # Add game info
                embed.add_field(
                    name="ℹ️ Info",
                    value="Verwende `/1337-info` um deine Wette anzuzeigen.",
                    inline=False
                )
                
                embed.set_footer(text="Viel Glück! 🍀")
                
            else:
                # Create error embed
                embed = discord.Embed(
                    title="❌ 1337 Game - Fehler",
                    description=message,
                    color=discord.Color.red()
                )
                
                # Add next game info if available
                _, _, next_game = self.game_manager.can_place_bet()
                if next_game:
                    embed.add_field(
                        name="⏰ Nächstes Spiel",
                        value=f"{next_game.strftime('%d.%m.%Y um %H:%M:%S')} Uhr",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in 1337 normal bet command: {e}")
            await interaction.followup.send("❌ Ein unerwarteter Fehler ist aufgetreten.", ephemeral=True)
    
    @app_commands.command(name="1337-early-bird", description="🐦 Platziere eine Early-Bird Wette mit vordefinierter Zeit!")
    @app_commands.describe(time="Zeit im Format [hh:mm:]ss[.SSS] (max 60.000s). Beispiele: '13.5', '01:13', '1:02:03.999'")
    async def game_1337_early(self, interaction: discord.Interaction, time: str):
        """Place an early bird bet with predefined time."""
        await interaction.response.defer()
        
        try:
            if not self.game_manager:
                await interaction.followup.send("❌ Game Manager nicht verfügbar.", ephemeral=True)
                return
            
            # Validate time input
            is_valid, error_message, play_time_ms = validate_time_input(time)
            
            if not is_valid:
                embed = discord.Embed(
                    title="❌ Ungültige Zeiteingabe",
                    description=error_message,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            user_id = str(interaction.user.id)
            username = interaction.user.display_name
            guild_id = str(interaction.guild.id) if interaction.guild else None
            
            success, message = await self.game_manager.place_early_bet(
                user_id=user_id,
                username=username,
                play_time_ms=play_time_ms,
                guild_id=guild_id
            )
            
            if success:
                # Create success embed
                embed = discord.Embed(
                    title="🐦 1337 Game - Early-Bird Wette platziert!",
                    description=message,
                    color=discord.Color.blue()
                )
                
                formatted_time = format_milliseconds_to_time(play_time_ms)
                embed.add_field(
                    name="⏱️ Deine Zeit",
                    value=f"`{formatted_time}` nach Spielstart",
                    inline=False
                )
                
                embed.add_field(
                    name="ℹ️ Info",
                    value="Early-Bird Wetten sind nur gültig, wenn keine normale Wette innerhalb von ±3 Sekunden der Gewinnzeit liegt.",
                    inline=False
                )
                
                embed.set_footer(text="Viel Glück! 🍀")
                
            else:
                # Create error embed
                embed = discord.Embed(
                    title="❌ 1337 Game - Fehler",
                    description=message,
                    color=discord.Color.red()
                )
                
                # Add next game info if available
                is_early_bird, next_game = self.game_manager.is_early_bird_period()
                if next_game:
                    cutoff_time = self.game_manager.get_early_bird_cutoff_time(next_game)
                    embed.add_field(
                        name="⏰ Nächstes Early-Bird Fenster",
                        value=f"Ab jetzt bis {cutoff_time.strftime('%d.%m.%Y um %H:%M:%S')} Uhr\nSpiel: {next_game.strftime('%d.%m.%Y um %H:%M:%S')} Uhr",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in 1337 early bet command: {e}")
            await interaction.followup.send("❌ Ein unerwarteter Fehler ist aufgetreten.", ephemeral=True)
    
    @app_commands.command(name="1337-next", description="⏰ Zeige die nächsten geplanten 1337 Games")
    async def game_1337_next(self, interaction: discord.Interaction):
        """Show the next scheduled 1337 games."""
        await interaction.response.defer()
        
        try:
            if not self.game_manager:
                await interaction.followup.send("❌ Game Manager nicht verfügbar.", ephemeral=True)
                return
            
            current_time = self.game_manager.get_current_datetime()
            
            # Check current game status
            is_active, game_start, game_end = self.game_manager.is_game_active()
            is_early_bird, next_game = self.game_manager.is_early_bird_period()
            
            embed = discord.Embed(
                title="⏰ 1337 Game - Zeitplan",
                color=discord.Color.blue()
            )
            
            # Current status
            if is_active:
                embed.add_field(
                    name="🎮 Aktueller Status",
                    value=f"**Spiel läuft!**\nGestartet: {game_start.strftime('%H:%M:%S')}\nEndet: {game_end.strftime('%H:%M:%S')}",
                    inline=False
                )
            elif is_early_bird:
                cutoff_time = self.game_manager.get_early_bird_cutoff_time(next_game)
                embed.add_field(
                    name="🐦 Aktueller Status",
                    value=f"**Early-Bird Periode**\nBis: {cutoff_time.strftime('%H:%M:%S')}\nSpiel: {next_game.strftime('%H:%M:%S')}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⏸️ Aktueller Status",
                    value="**Kein aktives Spiel**",
                    inline=False
                )
            
            # Next games
            next_games_text = self.game_manager.format_next_games(5)
            embed.add_field(
                name="📅 Nächste Spiele",
                value=next_games_text,
                inline=False
            )
            
            # Cron info
            embed.add_field(
                name="⚙️ Zeitplan",
                value=f"Cron: `{self.game_manager.cron_expression}`\nZeitzone: `{self.game_manager.timezone}`",
                inline=False
            )
            
            embed.set_footer(text=f"Aktuelle Zeit: {current_time.strftime('%d.%m.%Y %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in 1337 next command: {e}")
            await interaction.followup.send("❌ Ein unerwarteter Fehler ist aufgetreten.", ephemeral=True)
    
    @app_commands.command(name="1337-info", description="ℹ️ Zeige Informationen über deine aktuelle 1337 Game Wette")
    async def game_1337_info(self, interaction: discord.Interaction):
        """Show information about current 1337 game bet."""
        await interaction.response.defer()
        
        try:
            if not self.game_manager:
                await interaction.followup.send("❌ Game Manager nicht verfügbar.", ephemeral=True)
                return
            
            user_id = str(interaction.user.id)
            current_time = self.game_manager.get_current_datetime()
            
            # Check for current or upcoming game bet
            is_active, active_game_start, active_game_end = self.game_manager.is_game_active()
            is_early_bird, next_game = self.game_manager.is_early_bird_period()
            
            user_bet = None
            game_datetime = None
            
            if is_active:
                # Check for bet in current game
                user_bet = await self.game_manager.has_user_bet_for_game(user_id, active_game_start)
                if user_bet:
                    # Get the actual bet object
                    leaderboard = await self.game_manager.get_game_leaderboard(active_game_start)
                    user_bet = next((bet for bet in leaderboard if bet.user_id == user_id), None)
                    game_datetime = active_game_start
            elif is_early_bird or next_game:
                # Check for bet in next game
                target_game = next_game or self.game_manager.get_next_game_time()
                user_bet = await self.game_manager.has_user_bet_for_game(user_id, target_game)
                if user_bet:
                    leaderboard = await self.game_manager.get_game_leaderboard(target_game)
                    user_bet = next((bet for bet in leaderboard if bet.user_id == user_id), None)
                    game_datetime = target_game
            
            if not user_bet:
                embed = discord.Embed(
                    title="ℹ️ 1337 Game Info",
                    description="❌ Du hast für das aktuelle/nächste Spiel noch keine Wette platziert!",
                    color=discord.Color.orange()
                )
                
                # Add current status
                if is_active:
                    embed.add_field(
                        name="🎮 Status",
                        value=f"Spiel läuft bis {active_game_end.strftime('%H:%M:%S')}\nVerwende `/1337` für Echtzeit-Wette",
                        inline=False
                    )
                elif is_early_bird:
                    cutoff_time = self.game_manager.get_early_bird_cutoff_time(next_game)
                    embed.add_field(
                        name="🐦 Early-Bird Periode",
                        value=f"Bis {cutoff_time.strftime('%H:%M:%S')}\nVerwende `/1337-early-bird <zeit>`",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⏰ Nächstes Spiel",
                        value=f"{next_game.strftime('%d.%m.%Y um %H:%M:%S')} Uhr",
                        inline=False
                    )
                
                embed.add_field(
                    name="🎯 Befehle",
                    value="`/1337` - Echtzeit-Wette\n`/1337-early-bird <zeit>` - Early-Bird Wette\n`/1337-next` - Zeitplan",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Show bet info
            formatted_time = format_milliseconds_to_time(user_bet.play_time)
            bet_type_emoji = "🐦" if user_bet.play_type.value == "early" else "⚡"
            bet_type_name = "Early-Bird" if user_bet.play_type.value == "early" else "Echtzeit"
            
            embed = discord.Embed(
                title="ℹ️ 1337 Game - Deine Wette",
                color=discord.Color.blue() if is_active else discord.Color.green()
            )
            
            embed.add_field(
                name=f"{bet_type_emoji} Deine Wette",
                value=f"**{formatted_time}** ({bet_type_name})",
                inline=False
            )
            
            if game_datetime:
                embed.add_field(
                    name="🎮 Spiel",
                    value=f"{game_datetime.strftime('%d.%m.%Y um %H:%M:%S')} Uhr",
                    inline=True
                )
            
            if is_active and game_datetime:
                # Game is active
                embed.add_field(
                    name="⏰ Status",
                    value=f"Spiel läuft noch bis {active_game_end.strftime('%H:%M:%S')}!\nGewinnzeit wird nach Ende bekannt gegeben.",
                    inline=False
                )
            elif game_datetime and current_time > game_datetime:
                # Game ended - show results
                win_time_ms = self.game_manager.generate_win_time(game_datetime)
                delta_ms = win_time_ms - user_bet.play_time
                
                formatted_win_time = format_milliseconds_to_time(win_time_ms)
                
                embed.add_field(
                    name="🎯 Gewinnzeit",
                    value=f"**{formatted_win_time}**",
                    inline=True
                )
                
                if delta_ms >= 0:
                    embed.add_field(
                        name="📊 Dein Abstand",
                        value=f"**{delta_ms}ms** zu früh",
                        inline=True
                    )
                    if delta_ms <= 1000:  # Within 1 second
                        embed.add_field(name="🔥", value="Sehr nah dran!", inline=True)
                else:
                    embed.add_field(
                        name="❌ Status",
                        value="**Zu spät** (nach Gewinnzeit)",
                        inline=True
                    )
                
                # Check if user won
                winner_info = await self.game_manager.determine_winner(game_datetime)
                if winner_info and winner_info['winner'].user_id == user_id:
                    embed.add_field(
                        name="🏆 Ergebnis",
                        value="**Du hast gewonnen!** 🎉",
                        inline=False
                    )
                    embed.color = discord.Color.gold()
                else:
                    embed.add_field(
                        name="📈 Ergebnis",
                        value="Diesmal nicht gewonnen. Versuch es beim nächsten Spiel wieder!",
                        inline=False
                    )
            else:
                # Future game
                embed.add_field(
                    name="⏰ Status",
                    value="Wette für zukünftiges Spiel platziert.",
                    inline=False
                )
            
            embed.set_footer(text=f"Datum: {user_bet.date}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in 1337 info command: {e}")
            await interaction.followup.send("❌ Ein unerwarteter Fehler ist aufgetreten.", ephemeral=True)
    
    @app_commands.command(name="1337-stats", description="📊 Zeige 1337 Game Statistiken und Bestenlisten")
    async def game_1337_stats(self, interaction: discord.Interaction):
        """Show 1337 game statistics and leaderboards."""
        await interaction.response.defer()
        
        try:
            if not self.game_manager:
                await interaction.followup.send("❌ Game Manager nicht verfügbar.", ephemeral=True)
                return
            
            current_time = self.game_manager.get_current_datetime()
            
            # Get the most recent game (either active or previous)
            is_active, active_game_start, active_game_end = self.game_manager.is_game_active()
            
            if is_active:
                display_game = active_game_start
                display_name = "Aktuelles Spiel"
            else:
                # Get previous game
                display_game = self.game_manager.get_previous_game_time()
                display_name = "Letztes Spiel"
            
            daily_bets = await self.game_manager.get_game_leaderboard(display_game)
            
            embed = discord.Embed(
                title="📊 1337 Game Statistiken",
                description=f"**{display_name}**\n{display_game.strftime('%d.%m.%Y um %H:%M:%S')} Uhr",
                color=discord.Color.blue()
            )
            
            if daily_bets:
                bet_list = []
                for i, bet in enumerate(daily_bets, 1):
                    formatted_time = format_milliseconds_to_time(bet.play_time)
                    bet_type_emoji = "🐦" if bet.play_type.value == "early" else "⚡"
                    bet_list.append(f"{i}. {bet_type_emoji} **{bet.username}** - {formatted_time}")
                
                embed.add_field(
                    name=f"🎮 Spieler ({len(daily_bets)})",
                    value="\n".join(bet_list[:10]),  # Show max 10
                    inline=False
                )
                
                if not is_active:
                    # Show winner if game ended
                    winner_info = await self.game_manager.determine_winner(display_game)
                    if winner_info:
                        winner = winner_info['winner']
                        win_time_ms = winner_info['win_time_ms']
                        
                        formatted_win_time = format_milliseconds_to_time(win_time_ms)
                        formatted_winner_time = format_milliseconds_to_time(winner.play_time)
                        delta_ms = winner_info['delta_ms']
                        
                        embed.add_field(
                            name="🏆 Gewinner",
                            value=f"**{winner.username}**\nWette: {formatted_winner_time}\nGewinnzeit: {formatted_win_time}\nAbstand: {delta_ms}ms",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="⏰ Status",
                        value=f"Spiel läuft noch bis {active_game_end.strftime('%H:%M:%S')} Uhr",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="🎮 Spieler",
                    value="Noch keine Wetten platziert.",
                    inline=False
                )
            
            # Add next game info
            next_game = self.game_manager.get_next_game_time()
            embed.add_field(
                name="⏰ Nächstes Spiel",
                value=f"{next_game.strftime('%d.%m.%Y um %H:%M:%S')} Uhr",
                inline=False
            )
            
            # Add instructions
            embed.add_field(
                name="🎯 Befehle",
                value="`/1337` - Echtzeit-Wette\n`/1337-early-bird <zeit>` - Early-Bird Wette\n`/1337-next` - Zeitplan",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in 1337 stats command: {e}")
            await interaction.followup.send("❌ Ein unerwarteter Fehler ist aufgetreten.", ephemeral=True)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(Game1337Commands(bot))
