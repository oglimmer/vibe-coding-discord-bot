import asyncio
import logging
import time
from typing import Dict, Optional
import discord

from config import Config
from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

class FactCheckHandler:
    """Handler for managing reaction-based fact-checking on Discord messages."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.openai_service = OpenAIService()
        # Map of score ranges to descriptive emojis (0-100% scale)
        self.score_emojis = {
            'false': '❌',      # 0-20%: Definitiv falsch
            'mostly_false': '⚠️',  # 21-40%: Größtenteils falsch
            'mixed': '🤔',     # 41-60%: Gemischt
            'mostly_true': '✅',   # 61-80%: Größtenteils korrekt
            'true': '💯'       # 81-100%: Vollständig korrekt
        }
        
    async def handle_factcheck_reaction(self, reaction: discord.Reaction, user: discord.User) -> bool:
        """
        Handle when a user adds a fact-check reaction to a message.
        
        Args:
            reaction: The Discord reaction object
            user: The user who added the reaction
            
        Returns:
            True if fact-check was successfully processed, False otherwise
        """
        try:
            # Check if this is the fact-check reaction emoji
            if str(reaction.emoji) != Config.FACTCHECK_REACTION_EMOJI:
                return False
                
            # Don't process bot's own reactions
            if user.bot:
                return False
                
            # Check if OpenAI service is available
            if not self.openai_service.is_available():
                logger.debug("OpenAI service not available for fact-checking")
                return False
                
            # Check daily limit for the requester
            daily_count = self.db_manager.get_daily_factcheck_count(user.id)
            if daily_count >= Config.FACTCHECK_DAILY_LIMIT_PER_USER:
                await self._send_limit_exceeded_message(reaction.message, user)
                return False
                
            # Check if the message author has opted in
            message_author = reaction.message.author
            if message_author.bot:
                # Don't fact-check bot messages
                return False
                
            user_preference = self.db_manager.get_klugscheisser_preference(message_author.id)
            if not user_preference['opted_in']:
                await self._send_opt_in_required_message(reaction.message, user, message_author)
                return False
                
            # No minimum length requirement for fact-checks - any message can be fact-checked
                
            # Send typing indicator while processing
            async with reaction.message.channel.typing():
                # STEP 1: Pre-check if message is factcheckable
                logger.info(f"Pre-checking factcheckability for message from {message_author.display_name}")
                is_factcheckable = await self.openai_service.is_message_factcheckable(
                    message_content=reaction.message.content
                )
                
                # Save the fact-check request to database first (ALWAYS save to count towards daily limit)
                factcheck_id = self.db_manager.save_factcheck_request(
                    requester_user_id=user.id,
                    requester_username=user.display_name,
                    target_message_id=reaction.message.id,
                    target_user_id=message_author.id,
                    target_username=message_author.display_name,
                    message_content=reaction.message.content,
                    is_factcheckable=is_factcheckable,  # Store the factcheckability result
                    server_id=reaction.message.guild.id if reaction.message.guild else None,
                    channel_id=reaction.message.channel.id
                )
            
                if not factcheck_id:
                    logger.error("Failed to save fact-check request to database")
                    return False
                
                # STEP 2: Decide what to do based on factcheckability
                if is_factcheckable:
                    # NORMAL FACTCHECK: Get fact-check from OpenAI and respond publicly
                    logger.info(f"Message is factcheckable - performing full factcheck")
                    
                    factcheck_result = await self.openai_service.get_reaction_factcheck(
                        message_content=reaction.message.content,
                        user_name=message_author.display_name
                    )
                    
                    if not factcheck_result:
                        logger.warning("No fact-check response received from OpenAI service")
                        await self._send_error_message(reaction.message, user)
                        return False
                        
                    # Update database with result
                    self.db_manager.update_factcheck_result(
                        factcheck_id=factcheck_id,
                        score=factcheck_result['score'],
                        factcheck_response=factcheck_result['response']
                    )
                    
                    # Add score emoji reaction to the original message
                    score_emoji = self._get_score_emoji(factcheck_result['score'])
                    try:
                        await reaction.message.add_reaction(score_emoji)
                    except discord.HTTPException as e:
                        logger.warning(f"Failed to add score reaction: {e}")
                        
                    # Get remaining fact-checks for the user after this one
                    remaining_factchecks = Config.FACTCHECK_DAILY_LIMIT_PER_USER - (daily_count + 1)
                    
                    # Format and send the fact-check response
                    formatted_response = self._format_factcheck_response(
                        factcheck_result, user, message_author, daily_count + 1
                    )
                    
                    # Send as reply to the original message
                    await reaction.message.reply(formatted_response, mention_author=False)
                    
                    logger.info(f"Successfully processed fact-check request from {user.display_name} "
                               f"with score {factcheck_result['score']}")
                    return True
                    
                else:
                    # MESSAGE NOT FACTCHECKABLE: Send private message to requester, no public response
                    logger.info(f"Message is not factcheckable - sending private notification")
                    
                    # Update database to indicate no score (NULL) for non-factcheckable message
                    self.db_manager.update_factcheck_result(
                        factcheck_id=factcheck_id,
                        score=None,  # No score for non-factcheckable messages
                        factcheck_response="Nachricht enthält keine überprüfbaren Fakten"
                    )
                    
                    # Send private message to requester
                    await self._send_not_factcheckable_message(reaction.message, user)
                    
                    # Get remaining fact-checks for the user after this one
                    remaining_factchecks = Config.FACTCHECK_DAILY_LIMIT_PER_USER - (daily_count + 1)
                    
                    logger.info(f"Fact-check request from {user.display_name} completed - message not factcheckable")
                    return True  # Still counts as successfully processed
                
        except discord.HTTPException as e:
            logger.error(f"Failed to send fact-check response due to Discord API error: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error in fact-check handling: {e}")
            return False
    
    async def _send_limit_exceeded_message(self, message: discord.Message, user: discord.User):
        """Send a message when user has exceeded their daily fact-check limit."""
        try:
            embed = discord.Embed(
                title="🚫 Tageslimit erreicht",
                description=f"{user.mention}, du hast bereits {Config.FACTCHECK_DAILY_LIMIT_PER_USER} "
                           f"Faktenchecks heute verwendet. Versuche es morgen wieder!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=10)
        except discord.HTTPException as e:
            logger.error(f"Failed to send limit exceeded message: {e}")
    
    async def _send_opt_in_required_message(self, message: discord.Message, requester: discord.User, 
                                          message_author: discord.User):
        """Send a message when the message author hasn't opted in."""
        try:
            embed = discord.Embed(
                title="🔒 Opt-in erforderlich",
                description=f"{requester.mention}, {message_author.mention} hat nicht zugestimmt, "
                           f"dass seine Nachrichten an OpenAI gesendet werden dürfen.\n\n"
                           f"{message_author.mention} kann mit `/klugscheisser opt-in` zustimmen.",
                color=discord.Color.orange()
            )
            await message.channel.send(embed=embed, delete_after=15)
        except discord.HTTPException as e:
            logger.error(f"Failed to send opt-in required message: {e}")
    
    async def _send_message_too_short(self, message: discord.Message, user: discord.User):
        """Send a message when the target message is too short for fact-checking."""
        try:
            embed = discord.Embed(
                title="📏 Nachricht zu kurz",
                description=f"{user.mention}, die Nachricht ist zu kurz für einen Faktencheck "
                           f"(mindestens {Config.KLUGSCHEISSER_MIN_LENGTH} Zeichen erforderlich).",
                color=discord.Color.orange()
            )
            await message.channel.send(embed=embed, delete_after=10)
        except discord.HTTPException as e:
            logger.error(f"Failed to send message too short: {e}")
    
    async def _send_error_message(self, message: discord.Message, user: discord.User):
        """Send an error message when fact-checking fails."""
        try:
            embed = discord.Embed(
                title="❌ Fehler beim Faktencheck",
                description=f"{user.mention}, der Faktencheck konnte nicht durchgeführt werden. "
                           f"Versuche es später erneut.",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=10)
        except discord.HTTPException as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def _send_not_factcheckable_message(self, message: discord.Message, user: discord.User):
        """Send an ephemeral message when the message is not factcheckable."""
        try:
            # Send a short ephemeral message in the same channel (only visible to the requester)
            embed = discord.Embed(
                title="ℹ️ Nicht fact-checkbar",
                description=f"Diese Nachricht enthält keine überprüfbaren Fakten. "
                           f"Dein Limit wurde um 1 reduziert.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="💡 Tipp",
                value="Faktenchecks funktionieren bei Nachrichten mit konkreten Behauptungen am besten.",
                inline=False
            )
            
            # Try to create an interaction response (ephemeral)
            # Since we can't directly send ephemeral messages from reactions, 
            # we'll send a temporary message that deletes quickly
            temp_message = await message.channel.send(
                content=f"🔍 {user.mention}: Die Nachricht ist nicht fact-checkbar (nur Grüße/Emotionen/Meinungen). "
                       f"Dein Limit wurde trotzdem um 1 reduziert.",
                delete_after=8  # Delete after 8 seconds
            )
            
            logger.info(f"Sent not-factcheckable ephemeral message for {user.display_name}")
                
        except discord.HTTPException as e:
            logger.error(f"Failed to send not-factcheckable message: {e}")
    
    def _get_score_emoji(self, score: int) -> str:
        """Get the appropriate emoji for a given score (0-100% scale)."""
        if score <= 20:
            return self.score_emojis['false']
        elif score <= 40:
            return self.score_emojis['mostly_false']
        elif score <= 60:
            return self.score_emojis['mixed']
        elif score <= 80:
            return self.score_emojis['mostly_true']
        else:
            return self.score_emojis['true']
    
    def _format_factcheck_response(self, factcheck_result: dict, requester: discord.User, 
                                 message_author: discord.User, checks_used: int = 0) -> str:
        """Format the fact-check response with appropriate styling."""
        score = factcheck_result['score']
        response = factcheck_result['response']
        score_emoji = self._get_score_emoji(score)
        
        # Determine color and description based on score (0-100% scale)
        if score <= 20:
            level = "❌ **Größtenteils falsch**"
        elif score <= 40:
            level = "⚠️ **Teilweise falsch**"
        elif score <= 60:
            level = "🤔 **Gemischt**"
        elif score <= 80:
            level = "✅ **Größtenteils korrekt**"
        else:
            level = "✅ **Korrekt**"
        
        formatted = f"""🔍 **Faktencheck angefordert von {requester.mention}**

**Bewertung:** {score}% - {level}

{response}

📊 **Faktenchecks heute:** {checks_used}/{Config.FACTCHECK_DAILY_LIMIT_PER_USER}

*Hinweis: Dies ist eine automatisierte Bewertung und kann Fehler enthalten.*"""
        
        # Ensure the response isn't too long for Discord
        max_length = 2000  # Discord message limit
        if len(formatted) > max_length:
            # Truncate the response part while keeping the header
            available_space = max_length - len(formatted) + len(response) - 20  # -20 for truncation indicator
            truncated_response = response[:available_space] + "... *(gekürzt)*"
            formatted = formatted.replace(response, truncated_response)
            
        return formatted
    
    async def get_statistics(self) -> Dict[str, any]:
        """Get statistics about fact-check usage."""
        try:
            return {
                "openai_available": self.openai_service.is_available(),
                "factcheck_enabled": Config.KLUGSCHEISSER_ENABLED,
                "daily_limit_per_user": Config.FACTCHECK_DAILY_LIMIT_PER_USER,
                "reaction_emoji": Config.FACTCHECK_REACTION_EMOJI,
                "min_message_length": Config.KLUGSCHEISSER_MIN_LENGTH
            }
        except Exception as e:
            logger.error(f"Error getting fact-check statistics: {e}")
            return {}
