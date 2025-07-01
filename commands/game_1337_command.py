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
        logger.debug("Bot is ready, daily scheduler will start")

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
        try:
            logger.debug("Starting daily winner determination")
            game_date = self.game_logic.get_game_date()
            win_time = self.game_logic.get_daily_win_time(game_date)
            logger.debug(f"Game date: {game_date}, Win time: {win_time}")

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

            try:
                logger.debug(f"Determining winner for {game_date} at {win_time}")
                winner_result = self.game_logic.determine_winner(game_date, win_time)
                logger.debug(f"Winner result: {winner_result}")
            except Exception as e:
                logger.error(f"Error determining winner: {e}", exc_info=True)
                return

            if not winner_result:
                logger.info(f"No winner for {game_date}")
                try:
                    await self._announce_no_winner()
                except Exception as e:
                    logger.error(f"Error announcing no winner: {e}", exc_info=True)
                return

            if winner_result.get('catastrophic_event'):
                logger.info(f"Catastrophic event detected for {game_date}")
                try:
                    await self._announce_catastrophic_event()
                except Exception as e:
                    logger.error(f"Error announcing catastrophic event: {e}", exc_info=True)
                return

            # Get current role holders before updating roles
            current_role_holders = {}
            try:
                logger.debug(f"Getting current role holders for {len(self.bot.guilds)} guilds")
                for guild in self.bot.guilds:
                    try:
                        logger.debug(f"Processing guild: {guild.name} (ID: {guild.id})")
                        guild_roles = {
                            'general': self.db_manager.get_role_assignment(guild.id, 'general'),
                            'commander': self.db_manager.get_role_assignment(guild.id, 'commander'),
                            'sergeant': self.db_manager.get_role_assignment(guild.id, 'sergeant')
                        }
                        current_role_holders[guild.id] = guild_roles
                        logger.debug(f"Guild {guild.id} roles: {guild_roles}")
                    except Exception as e:
                        logger.error(f"Error getting role assignments for guild {guild.id}: {e}", exc_info=True)
                        current_role_holders[guild.id] = {'general': None, 'commander': None, 'sergeant': None}
            except Exception as e:
                logger.error(f"Error getting current role holders: {e}", exc_info=True)
                current_role_holders = {}

            # Save winner to database
            try:
                logger.debug(f"Saving winner to database: {winner_result}")
                success = self.game_logic.save_winner(winner_result)
                logger.debug(f"Save winner result: {success}")
            except Exception as e:
                logger.error(f"Error saving winner to database: {e}", exc_info=True)
                success = False

            if success:
                logger.info(f"Winner saved to database successfully")
                try:
                    logger.debug("Updating roles...")
                    await self._update_roles()
                    logger.debug("Announcing winner...")
                    await self._announce_winner(winner_result, current_role_holders)
                except Exception as e:
                    logger.error(f"Error in post-save operations: {e}", exc_info=True)
            else:
                logger.error(f"Failed to save winner to database")

            logger.info(f"Winner determination complete for {game_date}: {winner_result.get('username', 'Unknown')}")
        
        except Exception as e:
            logger.error(f"Critical error in _determine_daily_winner: {e}", exc_info=True)

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

    async def _announce_no_winner(self):
        """Announce that there was no winner for today's game"""
        message = "📅 **No winner today!** 🤷‍♂️"
        
        for guild in self.bot.guilds:
            try:
                # Try configured announcement channel first
                if Config.ANNOUNCEMENT_CHANNEL_ID:
                    announcement_channel = guild.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
                    if announcement_channel and announcement_channel.permissions_for(guild.me).send_messages:
                        await announcement_channel.send(message)
                        logger.info(f"No winner announced in configured channel: {announcement_channel.name} (Guild: {guild.name})")
                        continue
                
                # Fallback to first available text channel
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(message)
                        logger.info(f"No winner announced in fallback channel: {channel.name} (Guild: {guild.name})")
                        break
                        
            except Exception as e:
                logger.error(f"Error sending no winner announcement in guild {guild.id}: {e}")

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

        # Convert current assignments to expected format
        current_roles = {}
        for assignment in current_assignments:
            current_roles[assignment['role_type']] = {
                'user_id': assignment['user_id'],
                'username': assignment.get('username', 'Unknown')
            }
        
        # Determine new role assignments
        new_assignments = self._determine_new_role_assignments(winner_today, current_roles, guild.id)
        logger.debug(f"New role assignments: {new_assignments}")

        # Update roles efficiently - only change what needs to be changed
        await self._update_role_assignments_efficiently(guild, current_roles, new_assignments, sergeant_role, commander_role, general_role)

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

    def _determine_new_role_assignments(self, winner_today, current_roles, guild_id):
        """Determine who should get which roles based on game statistics"""
        return self.game_logic.determine_new_role_assignments(winner_today, current_roles, guild_id)

    async def _update_role_assignments_efficiently(self, guild, current_roles, new_assignments, sergeant_role, commander_role, general_role):
        """Update role assignments efficiently - only change what needs to be changed"""
        role_objects = {
            'sergeant': sergeant_role,
            'commander': commander_role, 
            'general': general_role
        }
        
        # For each role type, check if there's a change needed
        for role_type in ['sergeant', 'commander', 'general']:
            role = role_objects.get(role_type)
            if not role:
                logger.warning(f"Role {role_type} not configured, skipping")
                continue
            
            # Get current holder
            current_holder = current_roles.get(role_type)
            current_user_id = current_holder['user_id'] if current_holder else None
            
            # Get new holder
            new_user_id = new_assignments.get(role_type)
            
            # Only make changes if there's actually a difference
            if current_user_id != new_user_id:
                # Remove role from current holder (if any)
                if current_user_id:
                    current_member = guild.get_member(current_user_id)
                    if current_member and role in current_member.roles:
                        logger.info(f"Removing {role_type} role from {current_member.display_name}")
                        await current_member.remove_roles(role)
                    # Remove from database
                    self.db_manager.remove_role_assignment(guild.id, role_type)
                
                # Add role to new holder (if any)
                if new_user_id:
                    new_member = guild.get_member(new_user_id)
                    if new_member:
                        logger.info(f"Assigning {role_type} role to {new_member.display_name}")
                        await new_member.add_roles(role)
                        # Update database
                        success = self.db_manager.set_role_assignment(guild.id, new_user_id, role_type, role.id)
                        if not success:
                            logger.error(f"Failed to update database for {role_type} assignment to {new_member.display_name}")
                    else:
                        logger.warning(f"Member {new_user_id} not found in guild {guild.name}, skipping {role_type} assignment")
            else:
                logger.debug(f"No change needed for {role_type} role")

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

    async def _announce_winner(self, winner_data, current_role_holders):
        """Announce the daily winner to configured channels"""
        try:
            logger.debug(f"Starting winner announcement. Winner data: {winner_data}")
            logger.debug(f"Current role holders: {current_role_holders}")
            
            # Get role information for announcement
            logger.debug("Getting winner stats for announcement")
            winner_14_days = self.game_logic.get_winner_stats(days=14)
            winner_365_days = self.game_logic.get_winner_stats(days=365)
            logger.debug(f"14-day stats: {winner_14_days}")
            logger.debug(f"365-day stats: {winner_365_days}")
            
            top_14_day = winner_14_days[0] if winner_14_days else None
            top_365_day = winner_365_days[0] if winner_365_days else None
            logger.debug(f"Top 14-day: {top_14_day}, Top 365-day: {top_365_day}")
            
            # Send to configured announcement channel or fallback to first available channel
            await self._send_winner_announcement(winner_data, top_14_day, top_365_day, current_role_holders)
                
        except Exception as e:
            logger.error(f"Error in winner announcement: {e}", exc_info=True)


    async def _send_winner_announcement(self, winner_data, top_14_day, top_365_day, current_role_holders):
        """Send winner announcement to all guilds"""
        message_sent = False
        logger.debug(f"Sending winner announcement to {len(self.bot.guilds)} guilds")
        
        for guild in self.bot.guilds:
            try:
                logger.debug(f"Processing announcement for guild: {guild.name} (ID: {guild.id})")
                
                # Create guild-specific message with role change info
                guild_current_roles = current_role_holders.get(guild.id, {})
                logger.debug(f"Guild {guild.id} current roles: {guild_current_roles}")
                
                if guild_current_roles is None:
                    logger.warning(f"Guild {guild.id} has None for current_role_holders - this may cause the NoneType error")
                    guild_current_roles = {}
                
                logger.debug(f"Creating winner message for guild {guild.id}")
                message = self.game_logic.create_winner_message(winner_data, guild.id, guild_current_roles)
                logger.debug(f"Created message for guild {guild.id}: {message[:100]}...")
                
                # Try configured announcement channel first
                if Config.ANNOUNCEMENT_CHANNEL_ID:
                    announcement_channel = guild.get_channel(Config.ANNOUNCEMENT_CHANNEL_ID)
                    if announcement_channel and announcement_channel.permissions_for(guild.me).send_messages:
                        await announcement_channel.send(message)
                        logger.info(f"Winner announced in configured channel: {announcement_channel.name} (Guild: {guild.name})")
                        message_sent = True
                        continue
                
                # Fallback to first available text channel
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(message)
                        logger.info(f"Winner announced in fallback channel: {channel.name} (Guild: {guild.name})")
                        message_sent = True
                        break
                        
            except Exception as e:
                logger.error(f"Error sending winner announcement in guild {guild.id}: {e}", exc_info=True)
                logger.debug(f"Guild {guild.id} details - Name: {guild.name}, current_role_holders entry: {current_role_holders.get(guild.id)}")
                logger.debug(f"Full current_role_holders: {current_role_holders}")
        
        if not message_sent:
            logger.warning("Could not send winner announcement to any channel")





async def setup(bot, db_manager):
    """Setup function for the cog"""
    await bot.add_cog(Game1337Command(bot, db_manager))