"""
Discord command handling for the 1337 betting game.
Bot only handles Discord communication - all game logic is in the game service.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)


class Game1337Command(commands.Cog):
    """Discord command handler for the 1337 betting game"""
    
    def __init__(self, bot, game_service):
        self.bot = bot
        self.game_service = game_service


    async def announce_catastrophic_event(self):
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

    async def _update_roles_and_announce(self, winner_result):
        """Update roles and announce winner"""
        try:
            # Get current role holders before updating roles
            current_role_holders = {}
            for guild in self.bot.guilds:
                current_role_holders[guild.id] = {
                    'general': await self.game_service.get_role_assignment(guild.id, 'general'),
                    'commander': await self.game_service.get_role_assignment(guild.id, 'commander'), 
                    'sergeant': await self.game_service.get_role_assignment(guild.id, 'sergeant')
                }
            
            await self._update_roles()
            await self._announce_winner(winner_result, current_role_holders)
            
        except Exception as e:
            logger.error(f"Error updating roles and announcing winner: {e}")

    async def _update_roles(self):
        """Update Discord roles based on new role assignments from game service"""
        try:
            logger.debug("Starting role update process")
            if not any([Config.SERGEANT_ROLE_ID, Config.COMMANDER_ROLE_ID, Config.GENERAL_ROLE_ID]):
                logger.warning("No role IDs configured, skipping role update")
                return

            for guild in self.bot.guilds:
                try:
                    await self._update_guild_roles(guild)
                except Exception as e:
                    logger.error(f"Error updating roles in guild {guild.id}: {e}")

        except Exception as e:
            logger.error(f"Error in role update: {e}")

        logger.debug("Role update process completed")

    async def _update_guild_roles(self, guild):
        """Update roles for a specific guild by getting new assignments from game service"""
        logger.info(f"Processing guild: {guild.name} (ID: {guild.id})")
        
        # Get role objects
        sergeant_role = guild.get_role(Config.SERGEANT_ROLE_ID) if Config.SERGEANT_ROLE_ID else None
        commander_role = guild.get_role(Config.COMMANDER_ROLE_ID) if Config.COMMANDER_ROLE_ID else None
        general_role = guild.get_role(Config.GENERAL_ROLE_ID) if Config.GENERAL_ROLE_ID else None

        logger.info(f"Roles found - Sergeant: {sergeant_role}, Commander: {commander_role}, General: {general_role}")

        # Get current role assignments from game service
        current_assignments = await self.game_service.get_all_role_assignments(guild.id)
        logger.debug(f"Current role assignments: {current_assignments}")

        # Remove previous role assignments from Discord members
        await self._remove_previous_role_assignments(guild, current_assignments)

        # Get new role assignments from the game service (it handles the game logic)
        try:
            # Get today's winner to trigger new role calculations
            game_date = datetime.now().date()
            winner_today = await self.game_service.get_daily_winner(game_date)
            
            if not winner_today:
                logger.info("No winner found for today, skipping role assignment")
                return
                
            # Use the game service's winner message endpoint to get new role assignments
            winner_message_data = await self.game_service.client.create_winner_message(winner_today['user_id'], guild.id)
            new_assignments = winner_message_data.get('new_role_assignments', {})
            
            logger.debug(f"New role assignments from service: {new_assignments}")

            # Apply new role assignments
            await self._apply_new_role_assignments(guild, new_assignments, sergeant_role, commander_role, general_role)
            
        except Exception as e:
            logger.error(f"Error getting new role assignments from service: {e}")

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

    async def _apply_new_role_assignments(self, guild, assignments, sergeant_role, commander_role, general_role):
        """Apply new role assignments to Discord members and update game service"""
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
            
            # Update role assignment via game service
            success = await self.game_service.set_role_assignment(guild.id, user_id, role_type, role.id)
            if not success:
                logger.error(f"Failed to update role assignment for {role_type} assignment to {member.display_name}")

    async def _announce_winner(self, winner_data, current_role_holders):
        """Announce the daily winner to configured channels using game service message"""
        try:
            await self._send_winner_announcement(winner_data, current_role_holders)
        except Exception as e:
            logger.error(f"Error in winner announcement: {e}")

    async def _send_winner_announcement(self, winner_data, current_role_holders):
        """Send winner announcement to all guilds"""
        message_sent = False
        
        for guild in self.bot.guilds:
            try:
                # Get message from game service
                winner_message_data = await self.game_service.client.create_winner_message(winner_data['user_id'], guild.id)
                message = winner_message_data.get('message', f"🏆 **{winner_data['username']}** won today's 1337 game!")
                
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
                logger.error(f"Error sending winner announcement in guild {guild.id}: {e}")
        
        if not message_sent:
            logger.warning("Could not send winner announcement to any channel")

    async def process_external_winner_notification(self, winner_data):
        """Process winner notification received from game service webhook"""
        try:
            logger.info(f"🔔 Processing external winner notification: {winner_data['username']}")
            
            # Convert ISO string datetime fields back to datetime objects for compatibility
            winner_data = self._deserialize_winner_data(winner_data)
            
            # Get current role holders before updating roles
            current_role_holders = {}
            for guild in self.bot.guilds:
                current_role_holders[guild.id] = {
                    'general': await self.game_service.get_role_assignment(guild.id, 'general'),
                    'commander': await self.game_service.get_role_assignment(guild.id, 'commander'), 
                    'sergeant': await self.game_service.get_role_assignment(guild.id, 'sergeant')
                }
            
            # Update roles and announce winner
            await self._update_roles_and_announce(winner_data)
            
            logger.info(f"🔔 Successfully processed winner notification for {winner_data['username']}")
            
        except Exception as e:
            logger.error(f"🔔 Error processing external winner notification: {e}")

    def _deserialize_winner_data(self, winner_data):
        """Convert ISO string datetime fields back to datetime objects"""
        from datetime import datetime
        import copy
        
        # Make a copy to avoid modifying the original
        deserialized = copy.deepcopy(winner_data)
        
        # Fields that should be datetime objects
        datetime_fields = ['win_time', 'play_time']
        
        for field in datetime_fields:
            if field in deserialized and isinstance(deserialized[field], str):
                try:
                    # Parse ISO format datetime string back to datetime object
                    deserialized[field] = datetime.fromisoformat(deserialized[field])
                except ValueError as e:
                    logger.warning(f"Could not parse datetime field {field}: {e}")
        
        return deserialized





async def setup(bot, game_service):
    """Setup function for the cog"""
    await bot.add_cog(Game1337Command(bot, game_service))