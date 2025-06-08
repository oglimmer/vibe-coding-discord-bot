"""
Discord command handling for the 1337 betting game.
Refactored to separate Discord UI logic from core game logic.
"""

import logging
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
from config import Config
from database import DatabaseManager
from game.game_1337_logic import Game1337Logic

logger = logging.getLogger(__name__)


class Game1337Command(commands.Cog):
    """Discord command handler for the 1337 betting game"""
    
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.game_logic = Game1337Logic(db_manager)
        self.winner_determination_task = None
        self.daily_scheduler.start()

    def cog_unload(self):
        self.daily_scheduler.cancel()
        if self.winner_determination_task:
            self.winner_determination_task.cancel()

    @tasks.loop(hours=24)
    async def daily_scheduler(self):
        """Runs once per day to schedule the next winner determination"""
        await self._schedule_next_winner_determination()

    @daily_scheduler.before_loop
    async def before_daily_scheduler(self):
        await self.bot.wait_until_ready()
        # Schedule the first winner determination immediately after startup
        await self._schedule_next_winner_determination()

    async def _schedule_next_winner_determination(self):
        """Calculate and schedule the exact time for winner determination"""
        try:
            now = datetime.now()
            game_start_time = self.game_logic.parse_game_start_time()

            # Calculate next game time (today or tomorrow)
            next_game_time = datetime.combine(now.date(), game_start_time)
            if now >= next_game_time:
                # Game time has passed today, schedule for tomorrow
                next_game_time = next_game_time + timedelta(days=1)

            # Calculate delay until game time
            delay_seconds = (next_game_time - now).total_seconds()

            logger.info(
                f"Scheduling next winner determination for {next_game_time.strftime('%Y-%m-%d %H:%M:%S.%f')} "
                f"(in {delay_seconds:.3f} seconds)"
            )

            # Cancel existing task if any
            if self.winner_determination_task:
                logger.warning(f"Cancelling existing winner determination task")
                self.winner_determination_task.cancel()

            # Schedule the winner determination task
            self.winner_determination_task = asyncio.create_task(
                self._delayed_winner_determination(delay_seconds)
            )

        except Exception as e:
            logger.error(f"Error scheduling winner determination: {e}")

    async def _delayed_winner_determination(self, delay_seconds):
        """Wait for the exact delay and then determine the winner"""
        try:
            logger.info(f"Waiting {delay_seconds:.3f} seconds for winner determination")
            await asyncio.sleep(delay_seconds)

            # Verify we're at the right time (within 100ms tolerance)
            now = datetime.now()
            game_start_time = self.game_logic.parse_game_start_time()
            expected_time = datetime.combine(now.date(), game_start_time)

            time_diff = abs((now - expected_time).total_seconds())
            if time_diff > 0.1:  # More than 100ms off
                logger.warning(f"Winner determination timing off by {time_diff:.3f} seconds")

            logger.info(f"Starting winner determination at exact time: {now.strftime('%H:%M:%S.%f')}")
            await self._determine_daily_winner()

            # Schedule the next day's determination
            await self._schedule_next_winner_determination()

        except asyncio.CancelledError:
            logger.debug("Winner determination task was cancelled")
        except Exception as e:
            logger.error(f"Error in delayed winner determination: {e}")
            # Reschedule in case of error
            await self._schedule_next_winner_determination()

    async def _determine_daily_winner(self):
        """Determine the daily winner using game logic"""
        game_date = self.game_logic.get_game_date()
        win_time = self.game_logic.get_daily_win_time(game_date)

        # Wait until the exact win_time passes with millisecond precision
        now = datetime.now()
        if now < win_time:
            wait_seconds = (win_time - now).total_seconds()
            logger.info(f"Waiting {wait_seconds:.3f} seconds until win time: {self.game_logic.format_time_with_ms(win_time)}")
            
            # Use asyncio.sleep for most of the wait, but switch to busy-wait for final 10ms
            if wait_seconds > 0.01:  # More than 10ms to wait
                await asyncio.sleep(wait_seconds - 0.01)  # Sleep until 10ms before target
            
            # High-precision busy-wait for the final milliseconds
            while datetime.now() < win_time:
                await asyncio.sleep(0.0001)  # Very short sleep to yield control
            
            # Verify we hit the timing correctly
            actual_time = datetime.now()
            time_diff = (actual_time - win_time).total_seconds() * 1000  # Convert to milliseconds
            logger.info(f"Winner determination triggered at: {self.game_logic.format_time_with_ms(actual_time)} (diff: {time_diff:.1f}ms)")

        winner_result = self.game_logic.determine_winner(game_date, win_time)
        
        if not winner_result:
            logger.info(f"No winner for {game_date}")
            return
            
        if winner_result.get('catastrophic_event'):
            logger.info(f"Catastrophic event detected for {game_date}")
            await self._announce_catastrophic_event()
            return

        # Save winner to database
        success = self.game_logic.save_winner(winner_result)
        
        if success:
            logger.info(f"Winner saved to database successfully")
            await self._update_roles()
            await self._announce_winner(winner_result)
        else:
            logger.error(f"Failed to save winner to database")

        logger.info(f"Winner determination complete for {game_date}: {winner_result['username']}")

    async def _announce_catastrophic_event(self):
        """Announce a catastrophic event to all guilds"""
        message = """🚨 **TEMPORAL PARADOX DETECTED!** 🚨
Multiple brave souls attempted to occupy the same moment in time!
The fabric of reality couldn't handle it and collapsed into a singularity of disappointment.

**Today's winners:** Nobody (and everybody's feelings) 💥
The 1337 gods are not amused... try again tomorrow! 😤"""

        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(message)
                    break

    async def _update_roles(self):
        """Update Discord roles based on winner statistics"""
        try:
            logger.debug("Starting role update process")
            if not any([Config.SERGEANT_ROLE_ID, Config.COMMANDER_ROLE_ID, Config.GENERAL_ROLE_ID]):
                logger.warn("No role IDs configured, skipping role update")
                return

            game_date = self.game_logic.get_game_date()
            winner_today = self.game_logic.get_daily_winner(game_date)

            if not winner_today:
                logger.info("No winner found for today, skipping role update")
                return

            logger.info(f"Today's winner: {winner_today['username']} (ID: {winner_today['user_id']})")

            winner_14_days = self.game_logic.get_winner_stats(days=14)
            winner_365_days = self.game_logic.get_winner_stats(days=365)

            top_14_day = winner_14_days[0] if winner_14_days else None
            top_365_day = winner_365_days[0] if winner_365_days else None

            if top_14_day:
                logger.info(f"Top 14-day player: {top_14_day['username']} ({top_14_day['wins']} wins)")
            if top_365_day:
                logger.info(f"Top 365-day player: {top_365_day['username']} ({top_365_day['wins']} wins)")

            for guild in self.bot.guilds:
                try:
                    await self._update_guild_roles(guild, winner_today, top_14_day, top_365_day)
                except Exception as e:
                    logger.error(f"Error updating roles in guild {guild.id}: {e}")

        except Exception as e:
            logger.error(f"Error in role update: {e}")

        logger.debug("Role update process completed")

    async def _update_guild_roles(self, guild, winner_today, top_14_day, top_365_day):
        """Update roles for a specific guild using database role tracking"""
        logger.info(f"Processing guild: {guild.name} (ID: {guild.id})")
        
        sergeant_role = guild.get_role(Config.SERGEANT_ROLE_ID) if Config.SERGEANT_ROLE_ID else None
        commander_role = guild.get_role(Config.COMMANDER_ROLE_ID) if Config.COMMANDER_ROLE_ID else None
        general_role = guild.get_role(Config.GENERAL_ROLE_ID) if Config.GENERAL_ROLE_ID else None

        logger.info(f"Roles found - Sergeant: {sergeant_role}, Commander: {commander_role}, General: {general_role}")

        # Get current role assignments from database
        current_assignments = self.db_manager.get_all_role_assignments(guild.id)
        logger.debug(f"Current role assignments: {current_assignments}")

        # Remove previous role assignments from Discord members
        await self._remove_previous_role_assignments(guild, current_assignments)

        # Determine new role assignments
        new_assignments = self._determine_new_role_assignments(winner_today, top_14_day, top_365_day)
        logger.debug(f"New role assignments: {new_assignments}")

        # Apply new role assignments
        await self._apply_new_role_assignments(guild, new_assignments, sergeant_role, commander_role, general_role)

    async def _remove_previous_role_assignments(self, guild, current_assignments):
        """Remove roles from users who currently have them"""
        for assignment in current_assignments:
            member = guild.get_member(assignment['user_id'])
            if member:
                role = guild.get_role(assignment['role_id'])
                if role and role in member.roles:
                    logger.info(f"Removing {assignment['role_type']} role from {member.display_name}")
                    await member.remove_roles(role)
                else:
                    logger.warning(f"Role {assignment['role_type']} not found or not assigned to {member.display_name}")
            else:
                logger.warning(f"Member {assignment['user_id']} not found in guild {guild.name}")

    def _determine_new_role_assignments(self, winner_today, top_14_day, top_365_day):
        """Determine who should get which roles based on game statistics"""
        assignments = {}
        
        # Start with today's winner getting Sergeant
        assignments['sergeant'] = winner_today['user_id']
        
        # Override with Commander if winner is top 14-day player
        if top_14_day and winner_today['user_id'] == top_14_day['user_id']:
            assignments['commander'] = winner_today['user_id']
            if 'sergeant' in assignments and assignments['sergeant'] == winner_today['user_id']:
                del assignments['sergeant']
        
        # Override with General if winner is top 365-day player
        if top_365_day and winner_today['user_id'] == top_365_day['user_id']:
            assignments['general'] = winner_today['user_id']
            # Remove lower roles
            if 'commander' in assignments and assignments['commander'] == winner_today['user_id']:
                del assignments['commander']
            if 'sergeant' in assignments and assignments['sergeant'] == winner_today['user_id']:
                del assignments['sergeant']
        
        # Assign special roles to non-winners
        if top_365_day and top_365_day['user_id'] != winner_today['user_id']:
            assignments['general'] = top_365_day['user_id']
        
        if (top_14_day and top_14_day['user_id'] != winner_today['user_id'] and 
            top_14_day['user_id'] != (top_365_day['user_id'] if top_365_day else None)):
            assignments['commander'] = top_14_day['user_id']
        
        return assignments

    async def _apply_new_role_assignments(self, guild, assignments, sergeant_role, commander_role, general_role):
        """Apply new role assignments to Discord members and update database"""
        role_objects = {
            'sergeant': sergeant_role,
            'commander': commander_role, 
            'general': general_role
        }
        
        for role_type, user_id in assignments.items():
            role = role_objects.get(role_type)
            if not role:
                logger.warning(f"Role {role_type} not configured, skipping assignment")
                continue
                
            member = guild.get_member(user_id)
            if not member:
                logger.warning(f"Member {user_id} not found in guild {guild.name}, skipping {role_type} assignment")
                continue
            
            # Add role to Discord member
            if role not in member.roles:
                logger.info(f"Assigning {role_type} role to {member.display_name}")
                await member.add_roles(role)
            else:
                logger.debug(f"{member.display_name} already has {role_type} role")
            
            # Update database
            success = self.db_manager.set_role_assignment(guild.id, user_id, role_type, role.id)
            if not success:
                logger.error(f"Failed to update database for {role_type} assignment to {member.display_name}")

    async def _announce_general_bet(self, user, play_time):
        """Announce when a General places a bet"""
        message = f"🎖️ **The General has placed their bet at {self.game_logic.format_time_with_ms(play_time)}!** 🎖️"

        for guild in self.bot.guilds:
            if guild.get_member(user.id):
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(message)
                        break

    async def _announce_winner(self, winner_data):
        """Announce the daily winner to configured channels"""
        try:
            # Get role information for announcement
            winner_14_days = self.game_logic.get_winner_stats(days=14)
            winner_365_days = self.game_logic.get_winner_stats(days=365)
            
            top_14_day = winner_14_days[0] if winner_14_days else None
            top_365_day = winner_365_days[0] if winner_365_days else None
            
            # Determine winner's new role
            winner_role = "🏅 Sergeant"
            if top_365_day and winner_data['user_id'] == top_365_day['user_id']:
                winner_role = "🎖️ General"
            elif top_14_day and winner_data['user_id'] == top_14_day['user_id']:
                winner_role = "🔥 Commander"
            
            # Create winner announcement embed
            embed = self._create_winner_embed(winner_data, winner_role, top_14_day, top_365_day)
            
            # Send to configured announcement channel or fallback to first available channel
            await self._send_winner_announcement(embed)
                
        except Exception as e:
            logger.error(f"Error in winner announcement: {e}")

    def _create_winner_embed(self, winner_data, winner_role, top_14_day, top_365_day):
        """Create the winner announcement embed"""
        embed = discord.Embed(
            title="🏆 Daily 1337 Winner Announced!",
            color=0x00FF00,
            timestamp=datetime.now()
        )
        
        # Winner info
        embed.add_field(
            name="🎯 Winner",
            value=f"**{winner_data['username']}**",
            inline=True
        )
        
        # Timing info
        embed.add_field(
            name="⏰ Bet Time", 
            value=f"`{self.game_logic.format_time_with_ms(winner_data['play_time'])}`",
            inline=True
        )
        
        embed.add_field(
            name="🎲 Win Time",
            value=f"`{self.game_logic.format_time_with_ms(winner_data['win_time'])}`", 
            inline=True
        )
        
        # Performance info
        bet_type_emoji = "🐦 Early Bird" if winner_data['bet_type'] == 'early_bird' else "⚡ Regular"
        embed.add_field(
            name="📊 Performance",
            value=f"{bet_type_emoji}\n**{winner_data['millisecond_diff']}ms** before win time",
            inline=True
        )
        
        # Role info
        embed.add_field(
            name="🏅 New Role",
            value=winner_role,
            inline=True
        )
        
        # Total wins
        user_total_wins = self.game_logic.get_winner_stats(user_id=winner_data['user_id'])
        embed.add_field(
            name="🏆 Total Wins",
            value=f"**{user_total_wins}** wins",
            inline=True
        )
        
        # Add role hierarchy info if there are role changes
        role_updates = []
        if top_365_day:
            role_updates.append(f"🎖️ **General:** {top_365_day['username']} ({top_365_day['wins']} wins)")
        if top_14_day and (not top_365_day or top_14_day['user_id'] != top_365_day['user_id']):
            role_updates.append(f"🔥 **Commander:** {top_14_day['username']} ({top_14_day['wins']} wins)")
        
        if role_updates:
            embed.add_field(
                name="👑 Current Leaders",
                value="\n".join(role_updates),
                inline=False
            )
        
        embed.set_footer(text="🎮 Join tomorrow's battle at 13:37! Use /1337 or /1337-early-bird")
        
        return embed

    async def _send_winner_announcement(self, embed):
        """Send winner announcement to all guilds"""
        message_sent = False
        
        for guild in self.bot.guilds:
            try:
                # Try configured announcement channel first
                if Config.ANNOUNCEMENT_CHANNEL_ID:
                    announcement_channel = guild.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
                    if announcement_channel and announcement_channel.permissions_for(guild.me).send_messages:
                        await announcement_channel.send(embed=embed)
                        logger.info(f"Winner announced in configured channel: {announcement_channel.name} (Guild: {guild.name})")
                        message_sent = True
                        continue
                
                # Fallback to first available text channel
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(embed=embed)
                        logger.info(f"Winner announced in fallback channel: {channel.name} (Guild: {guild.name})")
                        message_sent = True
                        break
                        
            except Exception as e:
                logger.error(f"Error sending winner announcement in guild {guild.id}: {e}")
        
        if not message_sent:
            logger.warning("Could not send winner announcement to any channel")

    @discord.app_commands.command(name="1337", description="Place a regular bet for today's 1337 game")
    async def bet_1337(self, interaction: discord.Interaction):
        """Handle regular bet placement"""
        try:
            logger.debug(f"User {interaction.user.display_name} (ID: {interaction.user.id}) attempting regular bet")
            
            # Validate bet placement
            validation = self.game_logic.validate_bet_placement(interaction.user.id)
            if not validation['valid']:
                await interaction.response.send_message(validation['message'], ephemeral=True)
                return

            # Place the bet
            play_time = datetime.now()
            logger.debug(f"Current time: {self.game_logic.format_time_with_ms(play_time)}")

            success = self.game_logic.save_bet(
                interaction.user.id,
                interaction.user.display_name,
                play_time,
                'regular',
                interaction.guild_id,
                interaction.channel_id
            )

            if success:
                logger.info(f"Regular bet saved successfully for {interaction.user.display_name} at {self.game_logic.format_time_with_ms(play_time)}")

                # Check if user is General and announce
                if Config.GENERAL_ROLE_ID:
                    general_role = interaction.guild.get_role(Config.GENERAL_ROLE_ID)
                    if general_role and general_role in interaction.user.roles:
                        logger.debug(f"User is General, announcing bet")
                        await self._announce_general_bet(interaction.user, play_time)

                await interaction.response.send_message(
                    f"✅ **Bet placed!** Your time: {self.game_logic.format_time_with_ms(play_time)}\nGood luck! 🍀",
                    ephemeral=True
                )
            else:
                logger.error(f"Failed to save regular bet for {interaction.user.display_name}")
                await interaction.response.send_message(
                    "❌ **Error placing bet.** Please try again later.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in 1337 command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    @discord.app_commands.command(name="1337-early-bird", description="Place an early bird bet with a specific timestamp")
    async def bet_1337_early_bird(self, interaction: discord.Interaction, timestamp: str):
        """Handle early bird bet placement"""
        try:
            logger.debug(f"User {interaction.user.display_name} (ID: {interaction.user.id}) attempting early bird bet with timestamp: '{timestamp}'")
            
            # Validate bet placement
            bet_validation = self.game_logic.validate_bet_placement(interaction.user.id)
            if not bet_validation['valid']:
                await interaction.response.send_message(bet_validation['message'], ephemeral=True)
                return

            # Validate timestamp
            timestamp_validation = self.game_logic.validate_early_bird_timestamp(timestamp)
            if not timestamp_validation['valid']:
                await interaction.response.send_message(timestamp_validation['message'], ephemeral=True)
                return

            play_time = timestamp_validation['timestamp']
            
            # Save the bet
            success = self.game_logic.save_bet(
                interaction.user.id,
                interaction.user.display_name,
                play_time,
                'early_bird',
                interaction.guild_id,
                interaction.channel_id
            )

            if success:
                # Check if user is General and announce
                if Config.GENERAL_ROLE_ID:
                    general_role = interaction.guild.get_role(Config.GENERAL_ROLE_ID)
                    if general_role and general_role in interaction.user.roles:
                        await self._announce_general_bet(interaction.user, play_time)

                await interaction.response.send_message(
                    f"✅ **Early bird bet scheduled!** Your time: {self.game_logic.format_time_with_ms(play_time)}\nGood luck! 🍀",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ **Error placing bet.** Please try again later.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in 1337-early-bird command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    @discord.app_commands.command(name="1337-info", description="Show your current bet information for today")
    async def info_1337(self, interaction: discord.Interaction):
        """Show user's bet information"""
        try:
            user_bet = self.game_logic.get_user_bet_info(interaction.user.id)

            if not user_bet:
                await interaction.response.send_message(
                    "❌ **No bet placed today!** Use `/1337` or `/1337-early-bird` to place a bet.",
                    ephemeral=True
                )
                return

            embed = self._create_user_info_embed(user_bet)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in 1337-info command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    def _create_user_info_embed(self, user_bet):
        """Create user bet info embed"""
        game_date = self.game_logic.get_game_date()
        game_passed = self.game_logic.is_game_time_passed()

        embed = discord.Embed(
            title="🎯 Your 1337 Bet Info",
            color=0x1337FF,
            timestamp=datetime.now()
        )

        bet_type_emoji = "🐦" if user_bet['bet_type'] == 'early_bird' else "⚡"
        embed.add_field(
            name="Bet Type",
            value=f"{bet_type_emoji} {user_bet['bet_type'].replace('_', ' ').title()}",
            inline=True
        )

        embed.add_field(
            name="Your Time",
            value=f"`{self.game_logic.format_time_with_ms(user_bet['play_time'])}`",
            inline=True
        )

        if game_passed:
            winner = self.game_logic.get_daily_winner(game_date)
            if winner:
                embed.add_field(
                    name="Win Time",
                    value=f"`{self.game_logic.format_time_with_ms(winner['win_time'])}`",
                    inline=True
                )

                millisecond_diff = self.game_logic.calculate_millisecond_difference(
                    user_bet['play_time'], winner['win_time']
                )
                embed.add_field(
                    name="Difference",
                    value=f"`{millisecond_diff}ms`",
                    inline=True
                )

                if winner['user_id'] == user_bet['user_id']:
                    embed.add_field(
                        name="Result",
                        value="🏆 **WINNER!**",
                        inline=True
                    )
                    embed.color = 0x00FF00
                else:
                    embed.add_field(
                        name="Result",
                        value="💔 Better luck tomorrow!",
                        inline=True
                    )
                    embed.color = 0xFF6B6B
            else:
                embed.add_field(
                    name="Status",
                    value="⏳ Waiting for results...",
                    inline=False
                )
        else:
            embed.add_field(
                name="Status",
                value="⏳ Waiting for 13:37...",
                inline=False
            )

        return embed

    @discord.app_commands.command(name="1337-stats", description="Show 1337 game statistics")
    async def stats_1337(self, interaction: discord.Interaction):
        """Show game statistics"""
        try:
            view = StatsView(self.game_logic)
            embed = await view.get_page_embed(0)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in 1337-stats command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )


class StatsView(discord.ui.View):
    """Discord UI for statistics display"""
    
    def __init__(self, game_logic: Game1337Logic):
        super().__init__(timeout=300)
        self.game_logic = game_logic
        self.current_page = 0
        self.pages = ["365 Days", "14 Days", "Daily Bets"]

    async def get_page_embed(self, page: int):
        """Get embed for specific page"""
        embed = discord.Embed(
            title="📊 1337 Game Statistics",
            color=0x1337FF,
            timestamp=datetime.now()
        )

        if page == 0:  # 365 Days
            stats = self.game_logic.get_winner_stats(days=365)
            embed.add_field(
                name="🏆 Top Players (Last 365 Days)",
                value=self._format_stats_list(stats) if stats else "No winners yet",
                inline=False
            )

        elif page == 1:  # 14 Days
            stats = self.game_logic.get_winner_stats(days=14)
            embed.add_field(
                name="🔥 Top Players (Last 14 Days)",
                value=self._format_stats_list(stats) if stats else "No winners yet",
                inline=False
            )

        elif page == 2:  # Daily Bets
            game_passed = self.game_logic.is_game_time_passed()
            
            if game_passed:
                # Show today's bets
                today_bets = self.game_logic.get_daily_bets()
                embed.add_field(
                    name="📅 Today's Players",
                    value=self._format_daily_bets(today_bets) if today_bets else "No bets today",
                    inline=False
                )
            else:
                # Show yesterday's bets
                yesterday_date = self.game_logic.get_yesterday_date()
                yesterday_bets = self.game_logic.get_daily_bets(yesterday_date)
                embed.add_field(
                    name="📅 Yesterday's Players",
                    value=self._format_daily_bets(yesterday_bets) if yesterday_bets else "No bets yesterday",
                    inline=False
                )

        embed.set_footer(text=f"Page {page + 1}/3 • {self.pages[page]}")
        return embed

    def _format_stats_list(self, stats):
        """Format statistics list for display"""
        if not stats:
            return "No data available"

        lines = []
        for i, stat in enumerate(stats[:10]):
            rank = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            rank_emoji = rank[i] if i < len(rank) else "🏅"
            lines.append(f"{rank_emoji} **{stat['username']}** - {stat['wins']} wins")

        return "\n".join(lines)

    def _format_daily_bets(self, bets):
        """Format daily bets for display"""
        if not bets:
            return "No bets placed"

        lines = []
        for bet in bets[:15]:
            bet_type_emoji = "🐦" if bet['bet_type'] == 'early_bird' else "⚡"
            time_str = self.game_logic.format_time_with_ms(bet['play_time'])
            lines.append(f"{bet_type_emoji} `{time_str}` **{bet['username']}**")

        if len(bets) > 15:
            lines.append(f"*+{len(bets) - 15} more players...*")

        return "\n".join(lines)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle previous page button"""
        self.current_page = (self.current_page - 1) % len(self.pages)
        embed = await self.get_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle next page button"""
        self.current_page = (self.current_page + 1) % len(self.pages)
        embed = await self.get_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot, db_manager):
    """Setup function for the cog"""
    await bot.add_cog(Game1337Command(bot, db_manager))