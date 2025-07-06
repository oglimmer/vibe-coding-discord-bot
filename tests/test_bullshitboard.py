#!/usr/bin/env python3
"""
Test script to verify bullshitboard demo data
"""

from database import DatabaseManager

def test_bullshitboard():
    db = DatabaseManager()
    conn = db._get_connection()
    cursor = conn.cursor()
    
    print('🎯 BULLSHITBOARD DEMO DATA TEST')
    print('=' * 50)
    
    print('\n👥 DEMO USERS:')
    cursor.execute('SELECT user_id, opted_in FROM klugscheisser_user_preferences ORDER BY user_id')
    users = cursor.fetchall()
    
    usernames = {
        112345678901234567: "MythbusterMax",
        123456789012345678: "BullshitBingo_Pro",
        234567890123456789: "FactCheckFan", 
        345678901234567890: "WissenschaftlerWilli",
        456789012345678901: "KlugscheißerKing",
        567890123456789012: "SkeptischerSven",
        678901234567890123: "DatenDetektiv",
        789012345678901234: "LogikLuise",
        890123456789012345: "SchweigsamerSam",
        901234567890123456: "QuellencheckQueen",
    }
    
    for user_id, opted_in in users:
        username = usernames.get(user_id, f"User_{user_id}")
        status = '✅ Opted In' if opted_in else '❌ Opted Out'
        print(f'   {username:<20} ({user_id}): {status}')
    
    print('\n📊 BULLSHITBOARD RANKINGS:')
    print('   (Users who received fact-checks from others)')
    cursor.execute('''
        SELECT target_user_id, 
               COUNT(*) as total_checks,
               AVG(score) as avg_score,
               MIN(score) as min_score,
               MAX(score) as max_score
        FROM factcheck_requests 
        WHERE requester_user_id <> target_user_id
        GROUP BY target_user_id 
        HAVING COUNT(*) >= 3
        ORDER BY avg_score DESC
    ''')
    
    stats = cursor.fetchall()
    print(f'   {"Username":<20} | {"Checks":<6} | {"Avg BS":<8} | {"Range":<8}')
    print('   ' + '-' * 55)
    
    for user_id, total, avg, min_score, max_score in stats:
        username = usernames.get(user_id, f"User_{user_id}")
        print(f'   {username:<20} | {total:6} | {avg:8.2f} | {min_score}-{max_score}')
    
    print('\n🔍 RECENT FACT-CHECKS:')
    cursor.execute('''
        SELECT requester_username, target_username, message_content, score, request_date
        FROM factcheck_requests 
        ORDER BY request_date DESC, created_at DESC
        LIMIT 10
    ''')
    
    recent = cursor.fetchall()
    for req, target, content, score, date in recent:
        content_short = content[:40] + "..." if len(content) > 40 else content
        print(f'   {date} | {req} → {target} | Score: {score} | "{content_short}"')
    
    print('\n📈 OVERALL STATISTICS:')
    cursor.execute('SELECT COUNT(*) FROM factcheck_requests')
    total_checks = cursor.fetchone()[0]
    
    cursor.execute('SELECT AVG(score) FROM factcheck_requests WHERE score IS NOT NULL')
    avg_score = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT target_user_id) FROM factcheck_requests')
    unique_targets = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT requester_user_id) FROM factcheck_requests')
    unique_requesters = cursor.fetchone()[0]
    
    print(f'   Total fact-checks: {total_checks}')
    print(f'   Average BS score: {avg_score:.2f}')
    print(f'   Unique targets: {unique_targets}')
    print(f'   Unique requesters: {unique_requesters}')
    
    print('\n🏆 TOP BULLSHITTERS (Highest average BS scores):')
    cursor.execute('''
        SELECT target_user_id, AVG(score) as avg_score, COUNT(*) as checks
        FROM factcheck_requests 
        WHERE requester_user_id <> target_user_id AND score IS NOT NULL
        GROUP BY target_user_id 
        HAVING COUNT(*) >= 3
        ORDER BY avg_score DESC
        LIMIT 5
    ''')
    
    top_bullshitters = cursor.fetchall()
    for i, (user_id, avg_score, checks) in enumerate(top_bullshitters, 1):
        username = usernames.get(user_id, f"User_{user_id}")
        print(f'   {i}. {username} - Avg BS: {avg_score:.2f} ({checks} checks)')
    
    print('\n🏅 LEAST BULLSHITTERS (Lowest average BS scores):')
    cursor.execute('''
        SELECT target_user_id, AVG(score) as avg_score, COUNT(*) as checks
        FROM factcheck_requests 
        WHERE requester_user_id <> target_user_id AND score IS NOT NULL
        GROUP BY target_user_id 
        HAVING COUNT(*) >= 3
        ORDER BY avg_score ASC
        LIMIT 5
    ''')
    
    least_bullshitters = cursor.fetchall()
    for i, (user_id, avg_score, checks) in enumerate(least_bullshitters, 1):
        username = usernames.get(user_id, f"User_{user_id}")
        print(f'   {i}. {username} - Avg BS: {avg_score:.2f} ({checks} checks)')
    
    conn.close()
    print('\n✅ Bullshitboard test completed! The demo data looks great for testing.')

if __name__ == "__main__":
    test_bullshitboard()