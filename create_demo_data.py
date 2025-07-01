#!/usr/bin/env python3
"""
Demo Data Creator for Discord Bot Database
Creates realistic test data for bullshitboard testing
"""

import mariadb
import random
import hashlib
from datetime import datetime, date, timedelta, time
from config import Config

class DemoDataCreator:
    def __init__(self):
        self.connection = None
        
    def connect(self):
        """Connect to database"""
        try:
            self.connection = mariadb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME
            )
            print("✅ Connected to database")
        except mariadb.Error as e:
            print(f"❌ Error connecting to database: {e}")
            raise
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("✅ Database connection closed")
    
    def clear_existing_data(self):
        """Clear existing demo data (optional)"""
        cursor = self.connection.cursor()
        
        # Clear in order respecting foreign key constraints
        tables = [
            'greeting_reactions',
            'greetings', 
            'game_1337_winners',
            'game_1337_bets',
            'game_1337_roles',
            'factcheck_requests',
            'ai_response_cache',
            'klugscheisser_user_preferences'
        ]
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            print(f"🗑️  Cleared {table}")
        
        self.connection.commit()
        print("✅ All existing data cleared")
    
    def create_demo_users(self):
        """Create demo user preferences for klugscheißer system"""
        demo_users = [
            (123456789012345678, True),   # BullshitBingo_Pro
            (234567890123456789, True),   # FactCheckFan 
            (345678901234567890, True),   # WissenschaftlerWilli
            (456789012345678901, True),   # KlugscheißerKing
            (567890123456789012, True),   # SkeptischerSven
            (678901234567890123, True),   # DatenDetektiv
            (789012345678901234, True),   # LogikLuise
            (890123456789012345, False),  # SchweigsamerSam (opted out)
            (901234567890123456, True),   # QuellencheckQueen
            (112345678901234567, True),   # MythbusterMax
        ]
        
        cursor = self.connection.cursor()
        
        for user_id, opted_in in demo_users:
            cursor.execute("""
                INSERT INTO klugscheisser_user_preferences (user_id, opted_in)
                VALUES (?, ?)
            """, (user_id, opted_in))
        
        self.connection.commit()
        print(f"✅ Created {len(demo_users)} demo user preferences")
    
    def create_factcheck_data(self):
        """Create realistic fact-check requests and responses"""
        
        # Demo usernames mapping
        usernames = {
            123456789012345678: "BullshitBingo_Pro",
            234567890123456789: "FactCheckFan", 
            345678901234567890: "WissenschaftlerWilli",
            456789012345678901: "KlugscheißerKing",
            567890123456789012: "SkeptischerSven",
            678901234567890123: "DatenDetektiv",
            789012345678901234: "LogikLuise",
            890123456789012345: "SchweigsamerSam",
            901234567890123456: "QuellencheckQueen",
            112345678901234567: "MythbusterMax"
        }
        
        # Realistic bullshit claims with varying levels of accuracy (0-100%)
        claims_and_responses = [
            # Low Accuracy (0-20%) - Obvious nonsense
            ("Wusstet ihr, dass Giraffen eigentlich gar keine Zunge haben? Die benutzen Telekinese!", 
             "Das ist völlig falsch! Giraffen haben sehr wohl eine Zunge - sogar eine besonders lange (bis 50cm) und dunkle Zunge, die ihnen hilft, Blätter zu greifen.", 5),
            
            ("Die Erde ist flach und NASA gibt es gar nicht, das sind alles Schauspieler!", 
             "Definitiv falsch! Die Erde ist nachweislich rund, NASA existiert seit 1958 und Tausende von Wissenschaftlern arbeiten dort.", 2),
            
            ("Chemtrails sind Regierungsverschwörung um uns zu kontrollieren!", 
             "Das ist eine Verschwörungstheorie ohne wissenschaftliche Basis. Kondensstreifen entstehen durch Wasserdampf in der Atmosphäre.", 15),
            
            ("Impfungen enthalten 5G-Chips zur Gedankenkontrolle!", 
             "Völlig haltlos! Impfstoffe enthalten keine Mikrochips. Das ist eine weit verbreitete Falschinformation.", 8),
            
            ("Katzen können durch Wände gehen, das verschweigen Wissenschaftler!", 
             "Quatsch! Katzen sind normale Säugetiere ohne übernatürliche Fähigkeiten wie Phasenverschiebung.", 3),
            
            # Medium Accuracy (21-60%) - Teilweise falsch oder übertrieben
            ("Einstein hat die Relativitätstheorie von seiner Frau geklaut!", 
             "Das ist übertrieben. Mileva Marić hat Einstein bei seinen Arbeiten unterstützt, aber die Relativitätstheorie stammt von Einstein.", 35),
            
            ("Bananen sind radioaktiv und deshalb gefährlich!", 
             "Bananen enthalten minimal Kalium-40, aber die Strahlung ist völlig ungefährlich. Man müsste Millionen essen für Schäden.", 45),
            
            ("Wir nutzen nur 10% unseres Gehirns!", 
             "Das ist ein Mythos! Moderne Hirnscans zeigen, dass wir praktisch alle Bereiche des Gehirns nutzen, nur nicht gleichzeitig.", 25),
            
            ("Haie bekommen nie Krebs!", 
             "Das stimmt nicht. Haie können durchaus Krebs bekommen, auch wenn es seltener vorkommt als bei anderen Tieren.", 40),
            
            # Higher Accuracy (61-80%) - Größtenteils korrekt oder nur kleinere Fehler
            ("Die Chinesische Mauer sieht man vom Weltraum aus!", 
             "Das ist ein weit verbreiteter Irrtum. Man kann die Mauer nicht mit bloßem Auge aus dem Weltraum sehen.", 65),
            
            ("Menschen haben nur 5 Sinne!", 
             "Nicht ganz richtig. Menschen haben mehr als 5 Sinne, z.B. Gleichgewichtssinn, Temperatursinn, Schmerzempfindung.", 70),
            
            ("Gold ist das schwerste Element!", 
             "Falsch. Gold ist schwer, aber nicht das schwerste Element. Osmium und andere sind dichter.", 62),
            
            ("Kamele speichern Wasser in ihren Höckern!", 
             "Nicht korrekt. Kamele speichern Fett in den Höckern, nicht Wasser. Das Fett kann aber zu Wasser umgewandelt werden.", 55),
            
            # High Accuracy (81-100%) - Mostly correct with minor issues
            ("Diamanten sind die härtesten natürlichen Materialien!", 
             "Das stimmt! Diamanten haben eine Härte von 10 auf der Mohs-Skala und sind tatsächlich das härteste natürliche Material.", 95),
            
            ("Der menschliche Körper besteht zu etwa 60% aus Wasser!", 
             "Das ist im Wesentlichen korrekt! Bei Erwachsenen liegt der Wasseranteil zwischen 50-70%, je nach Alter und Geschlecht.", 88),
        ]
        
        cursor = self.connection.cursor()
        
        # Create fact-check requests over the last 30 days
        user_ids = list(usernames.keys())
        
        for i, (claim, response, bs_score) in enumerate(claims_and_responses):
            # Random dates in the last 30 days
            days_ago = random.randint(1, 30)
            check_date = date.today() - timedelta(days=days_ago)
            
            # Random requester and target (different users)
            requester_id = random.choice(user_ids)
            target_id = random.choice([uid for uid in user_ids if uid != requester_id])
            
            # Generate realistic message ID
            message_id = 1000000000000000000 + i * 1000 + random.randint(1, 999)
            
            cursor.execute("""
                INSERT INTO factcheck_requests (
                    requester_user_id, requester_username, target_message_id,
                    target_user_id, target_username, message_content,
                    request_date, score, factcheck_response, is_factcheckable,
                    server_id, channel_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                requester_id, usernames[requester_id], message_id,
                target_id, usernames[target_id], claim,
                check_date, bs_score, response, True,
                987654321098765432, 123456789012345678  # Demo server and channel IDs
            ))
        
        # Add some additional random fact-checks to create variety
        for _ in range(50):
            requester_id = random.choice(user_ids)
            target_id = random.choice([uid for uid in user_ids if uid != requester_id])
            
            days_ago = random.randint(1, 60)
            check_date = date.today() - timedelta(days=days_ago)
            
            # Reuse existing claims for more data
            claim, response, bs_score = random.choice(claims_and_responses)
            
            # Add some variation to scores (0-100% scale)
            score_variation = random.randint(-5, 5)
            final_score = max(0, min(100, bs_score + score_variation))
            
            message_id = 1000000000000000000 + random.randint(100000, 999999)
            
            cursor.execute("""
                INSERT INTO factcheck_requests (
                    requester_user_id, requester_username, target_message_id,
                    target_user_id, target_username, message_content,
                    request_date, score, factcheck_response, is_factcheckable,
                    server_id, channel_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                requester_id, usernames[requester_id], message_id,
                target_id, usernames[target_id], claim,
                check_date, final_score, response, True,
                987654321098765432, 123456789012345678
            ))
        
        self.connection.commit()
        print(f"✅ Created {len(claims_and_responses) + 50} fact-check requests")
    
    def create_ai_cache_data(self):
        """Create AI response cache entries"""
        cursor = self.connection.cursor()
        
        sample_caches = [
            ("Ist die Erde flach?", "factcheck", "Nein, die Erde ist nicht flach. Sie ist ein Geoid...", 15),
            ("Chemtrails existieren", "klugscheiss", "Kondensstreifen sind normale Wetterphänomene...", 20),
            ("5G verursacht Corona", "factcheck", "Es gibt keinen wissenschaftlichen Zusammenhang...", 5),
            ("Impfungen sind gefährlich", "klugscheiss", "Impfungen sind sicher und schützen vor Krankheiten...", 85),
        ]
        
        for content, response_type, ai_response, score in sample_caches:
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            hit_count = random.randint(1, 10)
            
            cursor.execute("""
                INSERT INTO ai_response_cache (
                    message_content_hash, message_content, response_type,
                    ai_response, score, hit_count
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (content_hash, content, response_type, ai_response, score, hit_count))
        
        self.connection.commit()
        print(f"✅ Created {len(sample_caches)} AI cache entries")
    
    def create_greeting_data(self):
        """Create greeting and reaction data"""
        cursor = self.connection.cursor()
        
        usernames = {
            123456789012345678: "BullshitBingo_Pro",
            234567890123456789: "FactCheckFan", 
            345678901234567890: "WissenschaftlerWilli",
            456789012345678901: "KlugscheißerKing",
            567890123456789012: "SkeptischerSven",
        }
        
        greetings = [
            "Guten Morgen zusammen! ☀️",
            "Moin moin! 🌅",
            "Hallo Leute! 👋",
            "Guten Tag! 😊",
            "Hi zusammen! 🙋‍♂️",
        ]
        
        greeting_ids = []
        
        # Create greetings for the last 14 days
        for days_ago in range(14):
            greeting_date = date.today() - timedelta(days=days_ago)
            user_id = random.choice(list(usernames.keys()))
            greeting_msg = random.choice(greetings)
            greeting_time = time(hour=random.randint(6, 10), minute=random.randint(0, 59))
            
            cursor.execute("""
                INSERT INTO greetings (
                    user_id, username, greeting_message, greeting_date,
                    greeting_time, server_id, channel_id, message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, usernames[user_id], greeting_msg, greeting_date,
                greeting_time, 987654321098765432, 123456789012345678,
                2000000000000000000 + days_ago
            ))
            
            greeting_ids.append(cursor.lastrowid)
        
        # Add reactions to greetings
        reactions = ["👍", "❤️", "😊", "🌅", "☀️", "👋"]
        
        for greeting_id in greeting_ids:
            # Random number of reactions per greeting
            for _ in range(random.randint(1, 5)):
                reactor_id = random.choice(list(usernames.keys()))
                reaction = random.choice(reactions)
                reaction_date = date.today() - timedelta(days=random.randint(0, 13))
                reaction_time = time(hour=random.randint(6, 23), minute=random.randint(0, 59))
                
                try:
                    cursor.execute("""
                        INSERT INTO greeting_reactions (
                            greeting_id, user_id, username, reaction_emoji,
                            reaction_date, reaction_time, server_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        greeting_id, reactor_id, usernames[reactor_id], reaction,
                        reaction_date, reaction_time, 987654321098765432
                    ))
                except mariadb.IntegrityError:
                    # Skip duplicate reactions (unique constraint)
                    pass
        
        self.connection.commit()
        print(f"✅ Created {len(greeting_ids)} greetings with reactions")
    
    def create_game_data(self):
        """Create Game 1337 data"""
        cursor = self.connection.cursor()
        
        usernames = {
            123456789012345678: "BullshitBingo_Pro",
            234567890123456789: "FactCheckFan", 
            345678901234567890: "WissenschaftlerWilli",
            456789012345678901: "KlugscheißerKing",
            567890123456789012: "SkeptischerSven",
        }
        
        # Create game bets and winners for last 10 days
        for days_ago in range(10):
            game_date = date.today() - timedelta(days=days_ago)
            
            # Create multiple bets per day
            bet_users = random.sample(list(usernames.keys()), random.randint(2, 4))
            
            winner_id = None
            best_diff = float('inf')
            
            for user_id in bet_users:
                # Random play time around 13:37
                base_time = datetime.combine(game_date, time(13, 37, 0))
                milliseconds = random.randint(-5000, 5000)  # ±5 seconds
                play_time = base_time + timedelta(milliseconds=milliseconds)
                
                bet_type = 'early_bird' if random.random() < 0.3 else 'regular'
                
                cursor.execute("""
                    INSERT INTO game_1337_bets (
                        user_id, username, play_time, game_date, bet_type,
                        server_id, channel_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, usernames[user_id], play_time, game_date, bet_type,
                    987654321098765432, 123456789012345678
                ))
                
                # Track best time for winner
                diff = abs((play_time - base_time).total_seconds() * 1000)
                if diff < best_diff:
                    best_diff = diff
                    winner_id = user_id
                    winner_time = play_time
                    winner_bet_type = bet_type
            
            # Create winner entry
            if winner_id:
                cursor.execute("""
                    INSERT INTO game_1337_winners (
                        user_id, username, game_date, win_time, play_time,
                        bet_type, millisecond_diff, server_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    winner_id, usernames[winner_id], game_date, winner_time,
                    winner_time, winner_bet_type, int(best_diff), 987654321098765432
                ))
        
        self.connection.commit()
        print("✅ Created Game 1337 bets and winners")
    
    def run(self, clear_data=False):
        """Run the complete demo data creation process"""
        print("🚀 Starting demo data creation...")
        
        try:
            self.connect()
            
            if clear_data:
                self.clear_existing_data()
            
            self.create_demo_users()
            self.create_factcheck_data()
            self.create_ai_cache_data()
            self.create_greeting_data()
            self.create_game_data()
            
            print("\n🎉 Demo data creation completed successfully!")
            print("\n📊 Summary:")
            print("- 10 demo users with klugscheißer preferences")
            print("- 65+ fact-check requests with varied BS scores") 
            print("- AI response cache entries")
            print("- 14 days of greeting data with reactions")
            print("- 10 days of Game 1337 data")
            print("\nYou can now test the bullshitboard functionality! 🎯")
            
        except Exception as e:
            print(f"❌ Error during demo data creation: {e}")
            raise
        finally:
            self.disconnect()

if __name__ == "__main__":
    import sys
    
    clear_data = "--clear" in sys.argv
    
    creator = DemoDataCreator()
    creator.run(clear_data=clear_data)