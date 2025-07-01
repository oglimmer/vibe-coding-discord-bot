#!/usr/bin/env python3
"""
Migration script to convert factcheck scores from 0-9 scale to 0-100% scale.

This script:
1. Converts existing scores using the formula: percentage = (score / 9) * 100
2. Updates the database schema to allow scores 0-100
3. Creates a backup before migration

Usage: python migrate_score_to_percentage.py
"""

import mariadb
import logging
from config import Config
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connection():
    """Get database connection"""
    try:
        connection = mariadb.connect(
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME
        )
        return connection
    except mariadb.Error as e:
        logger.error(f"Error connecting to MariaDB: {e}")
        raise

def backup_table():
    """Create backup of factcheck_requests table"""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        backup_table_name = f"factcheck_requests_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Creating backup table: {backup_table_name}")
        cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM factcheck_requests")
        connection.commit()
        
        logger.info(f"Backup created successfully: {backup_table_name}")
        return backup_table_name
        
    except mariadb.Error as e:
        logger.error(f"Error creating backup: {e}")
        raise
    finally:
        if connection:
            connection.close()

def get_current_scores():
    """Get all current scores to convert"""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT id, score FROM factcheck_requests WHERE score IS NOT NULL")
        results = cursor.fetchall()
        
        logger.info(f"Found {len(results)} records with scores to convert")
        return results
        
    except mariadb.Error as e:
        logger.error(f"Error getting current scores: {e}")
        raise
    finally:
        if connection:
            connection.close()

def convert_scores(score_records):
    """Convert scores from 0-9 to 0-100% scale"""
    conversion_map = {}
    
    for record_id, old_score in score_records:
        # Convert 0-9 scale to 0-100% scale
        # 0 stays 0%, 9 becomes 100%
        new_score = round((old_score / 9) * 100)
        conversion_map[record_id] = {
            'old_score': old_score,
            'new_score': new_score
        }
    
    logger.info(f"Conversion mapping created for {len(conversion_map)} records")
    
    # Show some examples
    examples = list(conversion_map.items())[:5]
    for record_id, scores in examples:
        logger.info(f"ID {record_id}: {scores['old_score']}/9 -> {scores['new_score']}%")
    
    return conversion_map

def update_database_schema():
    """Update database schema to allow 0-100 scores"""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        logger.info("Updating database schema to allow 0-100% scores")
        
        # Remove old constraint and add new one
        cursor.execute("""
            ALTER TABLE factcheck_requests 
            MODIFY COLUMN score TINYINT UNSIGNED CHECK (score >= 0 AND score <= 100)
        """)
        
        connection.commit()
        logger.info("Database schema updated successfully")
        
    except mariadb.Error as e:
        logger.error(f"Error updating schema: {e}")
        raise
    finally:
        if connection:
            connection.close()

def apply_score_conversion(conversion_map):
    """Apply the score conversion to the database"""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        logger.info("Applying score conversions...")
        
        for record_id, scores in conversion_map.items():
            cursor.execute(
                "UPDATE factcheck_requests SET score = ? WHERE id = ?",
                (scores['new_score'], record_id)
            )
        
        connection.commit()
        logger.info(f"Successfully converted {len(conversion_map)} scores")
        
    except mariadb.Error as e:
        logger.error(f"Error applying conversions: {e}")
        raise
    finally:
        if connection:
            connection.close()

def verify_conversion():
    """Verify the conversion was successful"""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT MIN(score), MAX(score), COUNT(*) FROM factcheck_requests WHERE score IS NOT NULL")
        min_score, max_score, count = cursor.fetchone()
        
        logger.info(f"Verification: {count} records, score range: {min_score}% - {max_score}%")
        
        if min_score < 0 or max_score > 100:
            logger.error("ERROR: Scores outside valid range (0-100%) detected!")
            return False
        
        logger.info("✅ All scores are within valid range (0-100%)")
        return True
        
    except mariadb.Error as e:
        logger.error(f"Error verifying conversion: {e}")
        return False
    finally:
        if connection:
            connection.close()

def main():
    """Run the migration"""
    try:
        logger.info("🚀 Starting score migration from 0-9 to 0-100%")
        
        # Step 1: Create backup
        backup_name = backup_table()
        
        # Step 2: Get current scores
        score_records = get_current_scores()
        
        if not score_records:
            logger.info("No scores found to convert. Migration completed.")
            return
        
        # Step 3: Calculate conversions
        conversion_map = convert_scores(score_records)
        
        # Step 4: Update schema
        update_database_schema()
        
        # Step 5: Apply conversions
        apply_score_conversion(conversion_map)
        
        # Step 6: Verify
        if verify_conversion():
            logger.info("✅ Migration completed successfully!")
            logger.info(f"Backup table: {backup_name}")
        else:
            logger.error("❌ Migration verification failed!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    main()