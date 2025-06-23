import unittest
from unittest.mock import Mock, AsyncMock
from greeting_detector import GreetingDetector

class TestGreetingDetector(unittest.TestCase):
    def setUp(self):
        self.db_manager = Mock()
        self.greeting_detector = GreetingDetector()
    
    def test_is_greeting_morning(self):
        self.assertTrue(self.greeting_detector.is_greeting("good morning")[0])
        self.assertTrue(self.greeting_detector.is_greeting("morning")[0])
        self.assertTrue(self.greeting_detector.is_greeting("Good Morning everyone!")[0])
    
    def test_is_greeting_gn(self):
        self.assertTrue(self.greeting_detector.is_greeting("gn")[0])
        self.assertTrue(self.greeting_detector.is_greeting("gn everyone")[0])
        self.assertTrue(self.greeting_detector.is_greeting("GN")[0])

    def test_is_not_greeting(self):
        self.assertFalse(self.greeting_detector.is_greeting("huhu")[0])
        self.assertFalse(self.greeting_detector.is_greeting("gnome")[0])
        self.assertFalse(self.greeting_detector.is_greeting("mourning coffee")[0])
    
    def test_greeting_word_limit_validation(self):
        # Valid greetings (2 words or less on each side)
        self.assertTrue(self.greeting_detector.is_greeting("hey there friend")[0])  # 0 before, 1 after
        self.assertTrue(self.greeting_detector.is_greeting("oh hi there")[0])  # 1 before, 1 after
        self.assertTrue(self.greeting_detector.is_greeting("well good morning everyone")[0])  # 1 before, 1 after
        self.assertTrue(self.greeting_detector.is_greeting("so hey buddy")[0])  # 1 before, 1 after
        
        # Invalid greetings (more than 2 words on either side)
        self.assertFalse(self.greeting_detector.is_greeting("I was just thinking good morning everyone today")[0])  # 4 before, 2 after
        self.assertFalse(self.greeting_detector.is_greeting("hey there my good friend today")[0])  # 0 before, 4 after
        self.assertFalse(self.greeting_detector.is_greeting("well I think hey there sounds nice today")[0])  # 3 before, 3 after

    def test_get_supported_languages(self):
        languages = self.greeting_detector.get_supported_languages()
        self.assertIn("English", languages)
        self.assertIn("German", languages)
        self.assertIn("Regional (Austria/Switzerland)", languages)
        self.assertIn("International", languages)

if __name__ == '__main__':
    unittest.main()