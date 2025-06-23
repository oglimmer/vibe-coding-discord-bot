import re
from typing import Optional, List, Dict

class GreetingDetector:
    def __init__(self):
        # English greetings
        self.english_greetings = [
            "morning", "good morning", "gm", "gn", "good night",
            "hello", "hi", "hey", "good evening", "evening",
            "yo", "sup", "whatsup", "what's up", "howdy",
            "hiya", "heya", "hi there", "greetings", "hey there",
            "top of the morning", "nighty night", "good day"
        ]

        # German greetings
        self.german_greetings = [
            "guten morgen", "moin",
            "servus", "hallo", "hi", "hey", "tach", "tag",
            "guten tag", "guten abend", "n8", "nacht",
            "gute nacht", "tschüss", "ciao", "bye", "tschau",
            "grüß dich", "na", "alles klar", "na du", "ey", "was geht",
            "hallihallo", "halöle", "mosche"
        ]

        # Regional variations (Austria/Switzerland)
        self.regional_greetings = [
            "grüezi", "grüß gott", "pfiat di", "baba",
            "hoi", "salü", "servas", "ade", "tschau zäme",
            "griaß di", "grüzi mitenand", "habedere"
        ]

        # International greetings
        self.international_greetings = [
            "salut", "bonjour", "bonsoir", "buongiorno",
            "buenos días", "buenas noches", "hola",
            "namaste", "shalom", "ciao", "konnichiwa",
            "annyeong", "hej", "hallå", "hei", "hola amigo",
            "ola", "ahlan", "salaam", "merhaba", "dobry den"
        ]

        # Combine all greetings and create regex patterns
        self.all_greetings = (
            self.english_greetings + self.german_greetings + 
            self.regional_greetings + self.international_greetings
        )
        self.greeting_patterns = [rf'\b{re.escape(greeting)}\b' for greeting in self.all_greetings]

    def is_greeting(self, content: str) -> tuple[bool, Optional[str]]:
        """
        Check if the content contains a greeting.
        Returns (is_greeting, matched_pattern).
        """
        content = content.lower().strip()
        words = content.split()
        
        for pattern in self.greeting_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Find the position of the matched greeting in the word list
                greeting_text = match.group()
                greeting_words = greeting_text.split()
                
                # Find where the greeting starts in the word list
                for i in range(len(words) - len(greeting_words) + 1):
                    if ' '.join(words[i:i+len(greeting_words)]).lower() == greeting_text.lower():
                        # Check words before greeting (max 2)
                        words_before = i
                        # Check words after greeting (max 2)
                        words_after = len(words) - (i + len(greeting_words))
                        
                        if words_before <= 2 and words_after <= 2:
                            return True, greeting_text
                        break
        return False, None

    def get_supported_languages(self) -> Dict[str, List[str]]:
        """Get all supported greeting languages and their patterns."""
        return {
            "English": self.english_greetings,
            "German": self.german_greetings,
            "Regional (Austria/Switzerland)": self.regional_greetings,
            "International": self.international_greetings
        }