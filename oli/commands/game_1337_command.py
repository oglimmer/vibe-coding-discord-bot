import logging
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
import random
import re
import asyncio
from config import Config
from database import DatabaseManager

logger = logging.getLogger(__name__)


class Game1337Command(commands.Cog):
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
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
            game_start_time = self._parse_game_start_time()

            # Calculate next game time (today or tomorrow)
            next_game_time = datetime.combine(now.date(), game_start_time)
            if now >= next_game_time:
                # Game time has passed today, schedule for tomorrow
                next_game_time = next_game_time + timedelta(days=1)

            # Calculate delay until game time
            delay_seconds = (next_game_time - now).total_seconds()

            logger.info(
                f"Scheduling next winner determination for {next_game_time.strftime('%Y-%m-%d %H:%M:%S.%f')} (in {delay_seconds:.3f} seconds)")

            # Cancel existing task if any
            if self.winner_determination_task:
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
            await asyncio.sleep(delay_seconds)

            # Verify we're at the right time (within 100ms tolerance)
            now = datetime.now()
            game_start_time = self._parse_game_start_time()
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

    def _parse_game_start_time(self):
        time_str = Config.GAME_START_TIME
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second_parts = parts[2].split('.')
        second = int(second_parts[0])
        microsecond = int(second_parts[1]) * 1000 if len(second_parts) > 1 else 0
        return time(hour, minute, second, microsecond)

    def _get_game_date(self):
        return datetime.now().date()

    def _get_win_time(self):
        now = datetime.now()
        game_start_time = self._parse_game_start_time()
        game_datetime = datetime.combine(now.date(), game_start_time)

        random_ms = random.randint(0, 60000)
        win_time = game_datetime + timedelta(milliseconds=random_ms)
        logger.debug(
            f"Generated win time: {self._format_time_with_ms(win_time)} (base: {self._format_time_with_ms(game_datetime)}, +{random_ms}ms)")
        return win_time

    def _parse_timestamp(self, timestamp_str, game_date):
        timestamp_str = timestamp_str.strip()
        logger.debug(f"Parsing timestamp: '{timestamp_str}' for date {game_date}")

        patterns = [
            r'^(\d{1,2}):(\d{2}):(\d{1,2})\.(\d{1,3})$',  # hh:mm:ss.SSS
            r'^(\d{1,2}):(\d{2}):(\d{1,2})$',  # hh:mm:ss
            r'^(\d{1,2})\.(\d{1,3})$',  # ss.SSS
            r'^(\d{1,2})$'  # ss
        ]

        for i, pattern in enumerate(patterns):
            match = re.match(pattern, timestamp_str)
            if match:
                groups = match.groups()
                logger.debug(f"Matched pattern {i}: {groups}")

                if len(groups) == 4:  # hh:mm:ss.SSS
                    hour, minute, second, ms = groups
                    ms = ms.ljust(3, '0')[:3]
                elif len(groups) == 3:  # hh:mm:ss
                    hour, minute, second = groups
                    ms = '000'
                elif len(groups) == 2:  # ss.SSS
                    hour, minute = '13', '37'
                    second, ms = groups
                    ms = ms.ljust(3, '0')[:3]
                else:  # ss
                    hour, minute = '13', '37'
                    second = groups[0]
                    ms = '000'

                try:
                    hour, minute, second = int(hour), int(minute), int(second)
                    microsecond = int(ms) * 1000

                    if hour == 13 and minute == 37 and 0 <= second <= 59:
                        dt = datetime.combine(game_date, time(hour, minute, second, microsecond))
                        logger.debug(f"Successfully parsed timestamp: {self._format_time_with_ms(dt)}")
                        return dt
                    else:
                        logger.debug(f"Invalid time components: {hour}:{minute}:{second}")
                except ValueError as e:
                    logger.debug(f"ValueError parsing time components: {e}")
                    continue

        logger.debug("No patterns matched, returning None")
        return None

    async def _determine_daily_winner(self):
        game_date = self._get_game_date()
        win_time = self._get_win_time()

        logger.info(f"Determining winner for {game_date}, win time: {self._format_time_with_ms(win_time)}")

        daily_bets = self.db_manager.get_daily_bets(game_date)
        logger.debug(f"Found {len(daily_bets)} total bets for {game_date}")

        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        logger.debug(f"Found {len(valid_bets)} valid bets (≤ win time)")

        for bet in daily_bets:
            valid = "✓" if bet['play_time'] <= win_time else "✗"
            logger.debug(
                f"  {valid} {bet['username']}: {self._format_time_with_ms(bet['play_time'])} ({bet['bet_type']})")

        if not valid_bets:
            logger.info(f"No valid bets for {game_date}")
            return

        if len(valid_bets) == 1:
            winner = valid_bets[0]
            logger.debug("Single valid bet, automatic winner")
        else:
            regular_bets = [bet for bet in valid_bets if bet['bet_type'] == 'regular']
            early_bird_bets = [bet for bet in valid_bets if bet['bet_type'] == 'early_bird']

            logger.debug(f"Regular bets: {len(regular_bets)}, Early bird bets: {len(early_bird_bets)}")

            three_seconds_before = win_time - timedelta(seconds=3)
            recent_regular_bets = [bet for bet in regular_bets if bet['play_time'] >= three_seconds_before]

            logger.debug(f"Recent regular bets (within 3s of win): {len(recent_regular_bets)}")
            logger.debug(f"Three seconds before win time: {self._format_time_with_ms(three_seconds_before)}")

            if recent_regular_bets:
                winner = max(regular_bets, key=lambda x: x['play_time'])
                logger.debug(f"Winner from recent regular bets: {winner['username']}")
            elif regular_bets:
                winner = max(regular_bets, key=lambda x: x['play_time'])
                logger.debug(f"Winner from all regular bets: {winner['username']}")
            elif early_bird_bets:
                winner = max(early_bird_bets, key=lambda x: x['play_time'])
                logger.debug(f"Winner from early bird bets: {winner['username']}")
            else:
                logger.info("No winner determined")
                return

        # Check for catastrophic event (identical times)
        identical_times = [bet for bet in valid_bets if bet['play_time'] == winner['play_time']]
        if len(identical_times) > 1:
            logger.warning(
                f"Catastrophic event! {len(identical_times)} players with identical time: {self._format_time_with_ms(winner['play_time'])}")
            await self._announce_catastrophic_event()
            return

        millisecond_diff = int((win_time - winner['play_time']).total_seconds() * 1000)
        logger.info(
            f"Winner: {winner['username']} - {self._format_time_with_ms(winner['play_time'])} ({winner['bet_type']}) - {millisecond_diff}ms before win time")

        success = self.db_manager.save_1337_winner(
            winner['user_id'],
            winner['username'],
            game_date,
            win_time,
            winner['play_time'],
            winner['bet_type'],
            millisecond_diff,
            winner['server_id']
        )

        if success:
            logger.info(f"Winner saved to database successfully")
            await self._update_roles()
            await self._announce_winner(winner, win_time, millisecond_diff)
        else:
            logger.error(f"Failed to save winner to database")

        logger.info(f"Winner determination complete for {game_date}: {winner['username']}")

    async def _announce_catastrophic_event(self):
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
        try:
            logger.debug("Starting role update process")
            if not any([Config.SERGEANT_ROLE_ID, Config.COMMANDER_ROLE_ID, Config.GENERAL_ROLE_ID]):
                logger.debug("No role IDs configured, skipping role update")
                return

            game_date = self._get_game_date()
            winner_today = self.db_manager.get_daily_winner(game_date)

            if not winner_today:
                logger.debug("No winner found for today, skipping role update")
                return

            logger.debug(f"Today's winner: {winner_today['username']} (ID: {winner_today['user_id']})")

            winner_14_days = self.db_manager.get_winner_stats(days=14)
            winner_365_days = self.db_manager.get_winner_stats(days=365)

            top_14_day = winner_14_days[0] if winner_14_days else None
            top_365_day = winner_365_days[0] if winner_365_days else None

            if top_14_day:
                logger.debug(f"Top 14-day player: {top_14_day['username']} ({top_14_day['wins']} wins)")
            if top_365_day:
                logger.debug(f"Top 365-day player: {top_365_day['username']} ({top_365_day['wins']} wins)")

            for guild in self.bot.guilds:
                try:
                    logger.debug(f"Processing guild: {guild.name} (ID: {guild.id})")
                    member = guild.get_member(winner_today['user_id'])
                    if not member:
                        logger.debug(f"Winner not found in guild {guild.name}")
                        continue

                    logger.debug(f"Found winner {member.display_name} in guild {guild.name}")

                    sergeant_role = guild.get_role(Config.SERGEANT_ROLE_ID) if Config.SERGEANT_ROLE_ID else None
                    commander_role = guild.get_role(Config.COMMANDER_ROLE_ID) if Config.COMMANDER_ROLE_ID else None
                    general_role = guild.get_role(Config.GENERAL_ROLE_ID) if Config.GENERAL_ROLE_ID else None

                    logger.debug(
                        f"Roles found - Sergeant: {sergeant_role}, Commander: {commander_role}, General: {general_role}")

                    # Remove all roles first
                    roles_to_remove = [r for r in [sergeant_role, commander_role, general_role] if
                                       r and r in member.roles]
                    if roles_to_remove:
                        logger.debug(f"Removing roles from {member.display_name}: {[r.name for r in roles_to_remove]}")
                        await member.remove_roles(*roles_to_remove)

                    # Assign appropriate role
                    if top_365_day and member.id == top_365_day['user_id'] and general_role:
                        logger.debug(f"Assigning General role to {member.display_name}")
                        await member.add_roles(general_role)
                    elif top_14_day and member.id == top_14_day['user_id'] and commander_role:
                        logger.debug(f"Assigning Commander role to {member.display_name}")
                        await member.add_roles(commander_role)
                    elif sergeant_role:
                        logger.debug(f"Assigning Sergeant role to {member.display_name}")
                        await member.add_roles(sergeant_role)

                    # Update roles for other members who should have commander/general
                    if top_365_day and top_365_day['user_id'] != member.id and general_role:
                        general_member = guild.get_member(top_365_day['user_id'])
                        if general_member:
                            logger.debug(f"Updating General role for {general_member.display_name}")
                            await general_member.remove_roles(
                                *[r for r in [sergeant_role, commander_role] if r and r in general_member.roles])
                            if general_role not in general_member.roles:
                                await general_member.add_roles(general_role)

                    if top_14_day and top_14_day['user_id'] != member.id and top_14_day['user_id'] != (
                    top_365_day['user_id'] if top_365_day else None) and commander_role:
                        commander_member = guild.get_member(top_14_day['user_id'])
                        if commander_member:
                            logger.debug(f"Updating Commander role for {commander_member.display_name}")
                            if sergeant_role and sergeant_role in commander_member.roles:
                                await commander_member.remove_roles(sergeant_role)
                            if commander_role not in commander_member.roles:
                                await commander_member.add_roles(commander_role)

                except Exception as e:
                    logger.error(f"Error updating roles in guild {guild.id}: {e}")

        except Exception as e:
            logger.error(f"Error in role update: {e}")

        logger.debug("Role update process completed")

    async def _announce_general_bet(self, user, play_time):
        message = f"🎖️ **The General has placed their bet at {play_time.strftime('%H:%M:%S.%f')[:-3]}!** 🎖️"

        for guild in self.bot.guilds:
            if guild.get_member(user.id):
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(message)
                        break
    
    async def _announce_winner(self, winner, win_time, millisecond_diff):
        """Announce the daily winner and role updates to configured channels"""
        try:
            # Get role information for announcement
            winner_14_days = self.db_manager.get_winner_stats(days=14)
            winner_365_days = self.db_manager.get_winner_stats(days=365)
            
            top_14_day = winner_14_days[0] if winner_14_days else None
            top_365_day = winner_365_days[0] if winner_365_days else None
            
            # Determine winner's new role
            winner_role = "🏅 Sergeant"
            if top_365_day and winner['user_id'] == top_365_day['user_id']:
                winner_role = "🎖️ General"
            elif top_14_day and winner['user_id'] == top_14_day['user_id']:
                winner_role = "🔥 Commander"
            
            # Create winner announcement embed
            embed = discord.Embed(
                title="🏆 Daily 1337 Winner Announced!",
                color=0x00FF00,
                timestamp=datetime.now()
            )
            
            # Winner info
            embed.add_field(
                name="🎯 Winner",
                value=f"**{winner['username']}**",
                inline=True
            )
            
            # Timing info
            embed.add_field(
                name="⏰ Bet Time", 
                value=f"`{self._format_time_with_ms(winner['play_time'])}`",
                inline=True
            )
            
            embed.add_field(
                name="🎲 Win Time",
                value=f"`{self._format_time_with_ms(win_time)}`", 
                inline=True
            )
            
            # Performance info
            bet_type_emoji = "🐦 Early Bird" if winner['bet_type'] == 'early_bird' else "⚡ Regular"
            embed.add_field(
                name="📊 Performance",
                value=f"{bet_type_emoji}\n**{millisecond_diff}ms** before win time",
                inline=True
            )
            
            # Role info
            embed.add_field(
                name="🏅 New Role",
                value=winner_role,
                inline=True
            )
            
            # Total wins
            user_total_wins = self.db_manager.get_winner_stats(user_id=winner['user_id'])
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
            
            # Send to configured announcement channel or fallback to first available channel
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
                
        except Exception as e:
            logger.error(f"Error in winner announcement: {e}")

    def _format_time_with_ms(self, dt):
        return dt.strftime('%H:%M:%S.%f')[:-3]

    def _get_yesterday_date(self):
        return (datetime.now() - timedelta(days=1)).date()

    @discord.app_commands.command(name="1337", description="Place a regular bet for today's 1337 game")
    async def bet_1337(self, interaction: discord.Interaction):
        try:
            logger.debug(f"User {interaction.user.display_name} (ID: {interaction.user.id}) attempting regular bet")
            game_date = self._get_game_date()
            play_time = datetime.now()
            logger.debug(f"Current time: {self._format_time_with_ms(play_time)}")

            # Check if game time has passed
            game_start_time = self._parse_game_start_time()
            game_datetime = datetime.combine(game_date, game_start_time)
            logger.debug(f"Game deadline: {self._format_time_with_ms(game_datetime + timedelta(minutes=1))}")

            if play_time > game_datetime + timedelta(minutes=1):  # Allow 1 minute buffer
                logger.debug(f"Bet rejected - game time has passed")
                await interaction.response.send_message(
                    "❌ **Game time has passed!** The 1337 window is closed for today. Try again tomorrow!",
                    ephemeral=True
                )
                return

            # Check if user already has a bet
            existing_bet = self.db_manager.get_user_bet(interaction.user.id, game_date)
            if existing_bet:
                logger.debug(f"Bet rejected - user already has a {existing_bet['bet_type']} bet")
                await interaction.response.send_message(
                    f"❌ **You've already placed a bet today!** Your {existing_bet['bet_type']} bet is at {self._format_time_with_ms(existing_bet['play_time'])}",
                    ephemeral=True
                )
                return

            # Save the bet
            logger.debug(f"Saving regular bet for user {interaction.user.display_name}")
            success = self.db_manager.save_1337_bet(
                interaction.user.id,
                interaction.user.display_name,
                play_time,
                game_date,
                'regular',
                interaction.guild_id,
                interaction.channel_id
            )

            if success:
                logger.info(
                    f"Regular bet saved successfully for {interaction.user.display_name} at {self._format_time_with_ms(play_time)}")

                # Check if user is General and announce
                if Config.GENERAL_ROLE_ID:
                    general_role = interaction.guild.get_role(Config.GENERAL_ROLE_ID)
                    if general_role and general_role in interaction.user.roles:
                        logger.debug(f"User is General, announcing bet")
                        await self._announce_general_bet(interaction.user, play_time)

                await interaction.response.send_message(
                    f"✅ **Bet placed!** Your time: {self._format_time_with_ms(play_time)}\nGood luck! 🍀",
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

    @discord.app_commands.command(name="1337-early-bird",
                                  description="Place an early bird bet with a specific timestamp")
    async def bet_1337_early_bird(self, interaction: discord.Interaction, timestamp: str):
        try:
            logger.debug(
                f"User {interaction.user.display_name} (ID: {interaction.user.id}) attempting early bird bet with timestamp: '{timestamp}'")
            game_date = self._get_game_date()

            # Parse the timestamp
            play_time = self._parse_timestamp(timestamp, game_date)
            if not play_time:
                logger.debug(f"Early bird bet rejected - invalid timestamp format: '{timestamp}'")
                await interaction.response.send_message(
                    "❌ **Invalid timestamp format!**\n\nSupported formats:\n"
                    "`3` → 13:37:03.000\n"
                    "`3.45` → 13:37:03.450\n"
                    "`13:37:3` → 13:37:03.000\n"
                    "`13:37:3.333` → 13:37:03.333",
                    ephemeral=True
                )
                return

            # Check if timestamp is in the future
            now = datetime.now()
            logger.debug(
                f"Parsed timestamp: {self._format_time_with_ms(play_time)}, current time: {self._format_time_with_ms(now)}")

            if play_time <= now:
                logger.debug(f"Early bird bet rejected - timestamp is in the past")
                await interaction.response.send_message(
                    "❌ **Timestamp must be in the future!** Early bird bets must be scheduled ahead of time.",
                    ephemeral=True
                )
                return

            # Check if user already has a bet
            existing_bet = self.db_manager.get_user_bet(interaction.user.id, game_date)
            if existing_bet:
                await interaction.response.send_message(
                    f"❌ **You've already placed a bet today!** Your {existing_bet['bet_type']} bet is at {self._format_time_with_ms(existing_bet['play_time'])}",
                    ephemeral=True
                )
                return

            # Save the bet
            success = self.db_manager.save_1337_bet(
                interaction.user.id,
                interaction.user.display_name,
                play_time,
                game_date,
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
                    f"✅ **Early bird bet scheduled!** Your time: {self._format_time_with_ms(play_time)}\nGood luck! 🍀",
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
        try:
            game_date = self._get_game_date()
            user_bet = self.db_manager.get_user_bet(interaction.user.id, game_date)

            if not user_bet:
                await interaction.response.send_message(
                    "❌ **No bet placed today!** Use `/1337` or `/1337-early-bird` to place a bet.",
                    ephemeral=True
                )
                return

            # Check if game time has passed
            game_start_time = self._parse_game_start_time()
            game_datetime = datetime.combine(game_date, game_start_time)
            now = datetime.now()
            game_passed = now > game_datetime

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
                value=f"`{self._format_time_with_ms(user_bet['play_time'])}`",
                inline=True
            )

            if game_passed:
                winner = self.db_manager.get_daily_winner(game_date)
                if winner:
                    embed.add_field(
                        name="Win Time",
                        value=f"`{self._format_time_with_ms(winner['win_time'])}`",
                        inline=True
                    )

                    millisecond_diff = int((winner['win_time'] - user_bet['play_time']).total_seconds() * 1000)
                    embed.add_field(
                        name="Difference",
                        value=f"`{millisecond_diff}ms`",
                        inline=True
                    )

                    if winner['user_id'] == interaction.user.id:
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

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in 1337-info command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    @discord.app_commands.command(name="1337-stats", description="Show 1337 game statistics")
    async def stats_1337(self, interaction: discord.Interaction):
        try:
            view = StatsView(self.db_manager)
            embed = await view.get_page_embed(0)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in 1337-stats command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )


class StatsView(discord.ui.View):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(timeout=300)
        self.db_manager = db_manager
        self.current_page = 0
        self.pages = ["365 Days", "14 Days", "Daily Bets"]

    async def get_page_embed(self, page: int):
        embed = discord.Embed(
            title="📊 1337 Game Statistics",
            color=0x1337FF,
            timestamp=datetime.now()
        )

        if page == 0:  # 365 Days
            stats = self.db_manager.get_winner_stats(days=365)
            embed.add_field(
                name="🏆 Top Players (Last 365 Days)",
                value=self._format_stats_list(stats) if stats else "No winners yet",
                inline=False
            )

        elif page == 1:  # 14 Days
            stats = self.db_manager.get_winner_stats(days=14)
            embed.add_field(
                name="🔥 Top Players (Last 14 Days)",
                value=self._format_stats_list(stats) if stats else "No winners yet",
                inline=False
            )

        elif page == 2:  # Daily Bets
            game_start_time = Game1337Command(None, None)._parse_game_start_time()
            game_datetime = datetime.combine(datetime.now().date(), game_start_time)
            now = datetime.now()
            game_passed = now > game_datetime

            if game_passed:
                # Show today's bets
                today_bets = self.db_manager.get_daily_bets(datetime.now().date())
                embed.add_field(
                    name="📅 Today's Players",
                    value=self._format_daily_bets(today_bets) if today_bets else "No bets today",
                    inline=False
                )
            else:
                # Show yesterday's bets
                yesterday_date = (datetime.now() - timedelta(days=1)).date()
                yesterday_bets = self.db_manager.get_daily_bets(yesterday_date)
                embed.add_field(
                    name="📅 Yesterday's Players",
                    value=self._format_daily_bets(yesterday_bets) if yesterday_bets else "No bets yesterday",
                    inline=False
                )

        embed.set_footer(text=f"Page {page + 1}/3 • {self.pages[page]}")
        return embed

    def _format_stats_list(self, stats):
        if not stats:
            return "No data available"

        lines = []
        for i, stat in enumerate(stats[:10]):
            rank = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            rank_emoji = rank[i] if i < len(rank) else "🏅"
            lines.append(f"{rank_emoji} **{stat['username']}** - {stat['wins']} wins")

        return "\n".join(lines)

    def _format_daily_bets(self, bets):
        if not bets:
            return "No bets placed"

        lines = []
        for bet in bets[:15]:
            bet_type_emoji = "🐦" if bet['bet_type'] == 'early_bird' else "⚡"
            time_str = bet['play_time'].strftime('%H:%M:%S.%f')[:-3]
            lines.append(f"{bet_type_emoji} `{time_str}` **{bet['username']}**")

        if len(bets) > 15:
            lines.append(f"*+{len(bets) - 15} more players...*")

        return "\n".join(lines)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % len(self.pages)
        embed = await self.get_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % len(self.pages)
        embed = await self.get_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot, db_manager):
    await bot.add_cog(Game1337Command(bot, db_manager))
