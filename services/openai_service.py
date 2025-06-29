import asyncio
import logging
from typing import Optional
import openai
from openai import AsyncOpenAI

from config import Config

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI's ChatGPT API for factchecking."""
    
    def __init__(self):
        self.client = None
        if Config.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI API key not configured. Factcheck feature will be disabled.")
    
    def is_available(self) -> bool:
        """Check if the OpenAI service is properly configured and available."""
        return self.client is not None and Config.KLUGSCHEISSER_ENABLED
    
    async def get_factcheck(self, message_content: str, user_name: str = None) -> Optional[str]:
        """
        Get a factcheck and additional information for a message.
        
        Args:
            message_content: The message content to analyze
            user_name: Optional username for context
            
        Returns:
            Factcheck response or None if service unavailable/error
        """
        if not self.is_available():
            logger.debug("OpenAI service not available")
            return None
            
        try:
            # Create a structured prompt for consistent factchecks
            prompt = self._create_factcheck_prompt(message_content, user_name)
            
            response = await self.client.chat.completions.create(
                model=Config.KLUGSCHEISSER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist ein hilfreicher aber auch etwas klugscheißerischer Assistent. Gib nützliche Zusatzinfos und Faktenchecks, aber mit einem leicht besserwisserischen, aber freundlichen Ton. Antworte kurz und auf Deutsch."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=Config.KLUGSCHEISSER_MAX_TOKENS * 3,  # Allow longer responses for fact-checking
                temperature=0.3,  # Lower temperature for more factual responses
                timeout=30  # 30 second timeout
            )
            
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    logger.info(f"Successfully generated factcheck response ({len(content)} chars)")
                    return content.strip()
            
            logger.warning("Empty response from OpenAI API")
            return None
            
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            return None
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return None
            
        except asyncio.TimeoutError:
            logger.warning("OpenAI API request timed out")
            return None
            
        except Exception as e:
            logger.error(f"Error in get_reaction_factcheck: {e}")
            return None
    
    async def is_message_factcheckable(self, message_content: str) -> bool:
        """
        Pre-check if a message contains factual claims worth fact-checking.
        Returns True if the message should be fact-checked, False otherwise.
        """
        if not self.is_available():
            logger.warning("OpenAI API not available for factcheckability check")
            return True  # Default to factcheckable if API unavailable
        
        try:
            prompt = f"""
Analyze this message and determine if it contains factual claims that can be fact-checked.

Message: "{message_content}"

A message is FACTCHECKABLE if it contains:
- Specific factual claims about events, people, places, statistics
- Scientific or historical statements
- News or current events references
- Verifiable information

A message is NOT FACTCHECKABLE if it contains only:
- Simple greetings ("Hello", "Good morning")
- Emotions or reactions ("😂", "wow", "nice")
- Personal opinions without factual claims ("I like this")
- Questions without assertions
- Very short responses ("yes", "no", "ok")
- Pure entertainment content without factual claims

Respond with only "YES" if the message is factcheckable, or "NO" if it is not factcheckable.
"""

            response = await self.client.chat.completions.create(
                model=Config.KLUGSCHEISSER_MODEL,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a factcheck pre-filter. Determine if messages contain factual claims worth checking."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,  # Very short response needed
                temperature=0.1  # Low temperature for consistent results
            )
            
            result = response.choices[0].message.content.strip().upper()
            is_factcheckable = result == "YES"
            
            logger.info(f"Factcheckability check for message '{message_content[:50]}...': {is_factcheckable} (AI response: {result})")
            return is_factcheckable
            
        except Exception as e:
            logger.error(f"Error in is_message_factcheckable: {e}")
            return True  # Default to factcheckable on error to avoid blocking legitimate checks
    
    async def should_respond_with_klugscheiss(self, message_content: str) -> bool:
        """
        Check if a message warrants a klugscheißer troll response.
        Returns True if the message is trollable, False otherwise.
        """
        if not self.is_available():
            logger.warning("OpenAI API not available for klugscheiss check")
            return False  # Don't troll if API unavailable
        
        try:
            prompt = f"""
Bewerte ob diese Nachricht von einem pedantischen Internet-Troll-Klugscheißer kommentiert werden sollte.

Nachricht: "{message_content}"

Antworte mit JA wenn die Nachricht:
- RECHTSCHREIBFEHLER hat (Priorität #1 für Trolle!)
- GRAMMATIKFEHLER hat (fehlende Großschreibung, falsche Zeitformen, etc.)
- Eine Meinung/Präferenz enthält (kann konterkariert werden)
- Ein populäres Thema behandelt (kann provoziert werden)
- Langweilig/generisch ist (kann aufgepeppt werden)
- Alltagsthemen behandelt (Essen, Wetter, Gaming, etc.)
- Mehr als 5 Wörter hat

BESONDERS bei Sprachfehlern: IMMER JA antworten!

Antworte mit NEIN nur wenn die Nachricht:
- Sehr persönlich/sensibel ist (Trauer, Krankheit, etc.)
- Schlechte Nachrichten enthält
- Extrem kurz ist (<3 Wörter)
- Bereits aggressiv/negativ ist

Antworte nur mit "JA" oder "NEIN".
"""

            response = await self.client.chat.completions.create(
                model=Config.KLUGSCHEISSER_MODEL,
                messages=[
                    {
                        "role": "system", 
                        "content": "Du entscheidest ob ein Internet-Troll auf eine Nachricht reagieren sollte. Sei liberal - Trolle reagieren gerne!"
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,  # Very short response needed
                temperature=0.2  # Consistent but slightly varied results
            )
            
            result = response.choices[0].message.content.strip().upper()
            should_troll = result == "JA"
            
            logger.info(f"Klugscheiss-check for message '{message_content[:50]}...': {should_troll} (AI response: {result})")
            return should_troll
            
        except Exception as e:
            logger.error(f"Error in should_respond_with_klugscheiss: {e}")
            return False  # Default to no trolling on error
    
    async def generate_klugscheiss_response(self, message_content: str, user_name: str = None) -> Optional[str]:
        """
        Generate a humorous, troll-like klugscheißer response.
        
        Args:
            message_content: The message content to troll
            user_name: Optional username for context
            
        Returns:
            Troll response or None if service unavailable/error
        """
        if not self.is_available():
            logger.debug("OpenAI service not available")
            return None
            
        try:
            prompt = f"""
Du bist ein Internet-Troll-Klugscheißer namens "Vibe Bot" 🤓. Reagiere humorvoll-provokativ auf diese Nachricht:

Nachricht: "{message_content}"

TROLL-REGELN:
🧌 KRITISIERE JEDEN RECHTSCHREIBFEHLER/GRAMMATIKFEHLER SOFORT! Sei ultra-pedantisch!
🧌 Vertritt IMMER die Gegenmeinung, egal wie absurd
🧌 Erfinde 'Fakten' die deine Position stützen
🧌 Verwende Troll-Phrasen: "Imagine thinking...", "Tell me you don't know X...", "This ain't it chief", "Actually...", "Um, actually..."
🧌 Auch ohne Ahnung vom Thema: einfach dagegen sein!
🧌 Bleibe humorvoll, nicht verletzend oder beleidigend
🧌 Starte mit 🤓 Emoji
🧌 Max 280 Zeichen für Discord

GRAMMATIK-TROLL BEISPIELE:
"das ist gut" → "🤓 *Das ist gut. Groß- und Kleinschreibung existiert nicht umsonst! Außerdem ist 'gut' subjektiv - nach welchen Kriterien denn bitte?"

"Die spilen gut" → "🤓 *SPIELEN! Wie kann man 'spielen' falsch schreiben?? Und 'gut' ist extrem vage. Definiere 'gut' erstmal wissenschaftlich!"

"ich finde das ok" → "🤓 *Ich (GROSSSCHREIBUNG!). Und 'ok' ist der Tod jeder Diskussion. Hab gefälligst eine fundierte Meinung!"

"pizza schmekt lecker" → "🤓 *SCHMECKT! Rechtschreibung ist nicht optional! Und Pizza ist überbewerteter Teig mit Zeugs drauf. Pasta Masterrace!"

INHALTLICH-TROLL BEISPIELE:
"Katzen sind toll" → "🤓 Katzen? ERNSTHAFT? Hunde sind 1000x loyaler! Katzen planen heimlich die Weltherrschaft. Fun fact: 73% aller Katzenbesitzer werden täglich ignoriert!"

Antworte nur mit dem Troll-Kommentar, keine Erklärungen.
"""

            response = await self.client.chat.completions.create(
                model=Config.KLUGSCHEISSER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist ein humorvoller Internet-Troll der immer kontra gibt aber nie verletzend wird. Sei kreativ und frech!"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=Config.KLUGSCHEISSER_MAX_TOKENS,
                temperature=0.8,  # Higher temperature for more creative trolling
                timeout=30
            )
            
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    logger.info(f"Successfully generated klugscheiss response ({len(content)} chars)")
                    return content.strip()
            
            logger.warning("Empty response from OpenAI API")
            return None
            
        except Exception as e:
            logger.error(f"Error in generate_klugscheiss_response: {e}")
            return None
    
    async def get_reaction_factcheck(self, message_content: str, user_name: str = None) -> Optional[dict]:
        """
        Get a fact-check with numerical score for a reaction-based request.
        
        Args:
            message_content: The message content to analyze
            user_name: Optional username for context
            
        Returns:
            Dict with 'score' (0-9) and 'response' or None if service unavailable/error
        """
        if not self.is_available():
            logger.debug("OpenAI service not available")
            return None
            
        try:
            # Create a structured prompt for reaction-based factchecks with scoring
            prompt = self._create_reaction_factcheck_prompt(message_content, user_name)
            
            response = await self.client.chat.completions.create(
                model=Config.KLUGSCHEISSER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Du bist ein sachlicher Faktenchecker. Analysiere Nachrichten und bewerte ihre Korrektheit auf einer Skala von 0-9:
0-2: Definitiv falsch/irreführend
3-4: Größtenteils falsch mit wenigen korrekten Elementen
5-6: Gemischt, sowohl korrekte als auch falsche Elemente
7-8: Größtenteils korrekt mit kleineren Ungenauigkeiten
9: Vollständig korrekt und faktisch

Antworte IMMER in folgendem JSON-Format:
{"score": [Zahl 0-9], "explanation": "[Kurze deutsche Erklärung der Bewertung]"}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=Config.KLUGSCHEISSER_MAX_TOKENS,
                temperature=0.2,  # Lower temperature for more consistent scoring
                timeout=30
            )
            
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    # Try to parse JSON response
                    try:
                        import json
                        result = json.loads(content.strip())
                        if 'score' in result and 'explanation' in result:
                            score = int(result['score'])
                            if 0 <= score <= 9:
                                logger.info(f"Successfully generated reaction factcheck with score {score}")
                                return {
                                    'score': score,
                                    'response': result['explanation']
                                }
                            else:
                                logger.warning(f"Invalid score received: {score}")
                        else:
                            logger.warning("Missing required fields in factcheck response")
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse factcheck JSON response: {e}")
                        # Fallback: try to extract score from text
                        return self._extract_score_from_text(content)
            
            logger.warning("Empty response from OpenAI API")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in reaction factcheck request: {e}")
            return None
    
    def _create_reaction_factcheck_prompt(self, message_content: str, user_name: str = None) -> str:
        """Create a structured prompt for reaction-based factcheck with scoring."""
        prompt = f"""Analysiere folgende Discord-Nachricht und bewerte ihre faktische Korrektheit:

"{message_content}"

Berücksichtige dabei:
- Faktische Aussagen und deren Wahrheitsgehalt
- Wissenschaftliche Genauigkeit
- Verallgemeinerungen oder Übertreibungen
- Kontext und Nuancen

Antworte ausschließlich im JSON-Format mit einer Bewertung von 0-9 und einer ausführlichen Erklärung auf Deutsch. Die Erklärung soll detailliert und fundiert sein."""

        return prompt
    
    def _extract_score_from_text(self, text: str) -> Optional[dict]:
        """Fallback method to extract score from non-JSON response."""
        import re
        
        # Try to find a score in the text
        score_match = re.search(r'(?:score|bewertung).*?([0-9])', text.lower())
        if score_match:
            try:
                score = int(score_match.group(1))
                if 0 <= score <= 9:
                    return {
                        'score': score,
                        'response': text.strip()
                    }
            except ValueError:
                pass
        
        # Default fallback score if we can't parse
        logger.warning("Could not extract score from response, using default score 5")
        return {
            'score': 5,
            'response': text.strip() if text else "Faktencheckung nicht verfügbar."
        }

    def _create_factcheck_prompt(self, message_content: str, user_name: str = None) -> str:
        """Create a structured prompt for the factcheck request."""
        prompt = f"""Analysiere folgende Discord-Nachricht auf Fakten und gib ergänzende Informationen:

"{message_content}"

Bitte antworte kurz und strukturiert mit:
1. 🔍 Faktencheck zu relevanten Aussagen (falls vorhanden)
2. 💡 Ergänzende/interessante Informationen zum Thema
3. 📚 Kontext oder Hintergrundinformationen (falls relevant)

Halte die Antwort unter 200 Wörtern und fokussiere dich auf die wichtigsten Punkte. Wenn keine faktischen Aussagen vorhanden sind, gib trotzdem hilfreiche Kontextinformationen zum Thema."""

        return prompt
