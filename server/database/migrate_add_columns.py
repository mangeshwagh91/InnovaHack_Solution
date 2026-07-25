"""
Migration script: add new columns to existing DCPI database.
Run once: python migrate_add_columns.py
Safe to run on a database that already has these columns (uses IF NOT EXISTS logic).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from database.connection import get_db

db = get_db()

migrations = [
    # deviations: add justification and recommended_action
    "ALTER TABLE deviations ADD COLUMN justification TEXT",
    "ALTER TABLE deviations ADD COLUMN recommended_action TEXT",
    # purchase_orders: add conformance_score
    "ALTER TABLE purchase_orders ADD COLUMN conformance_score REAL DEFAULT 1.0",
    # schedule_tasks: add risk_level and is_critical_path
    "ALTER TABLE schedule_tasks ADD COLUMN risk_level TEXT DEFAULT 'negligible'",
    "ALTER TABLE schedule_tasks ADD COLUMN is_critical_path INTEGER DEFAULT 0",
    # agent_runs: add agent_version and metadata_json
    "ALTER TABLE agent_runs ADD COLUMN agent_version TEXT DEFAULT '1.0.0'",
    "ALTER TABLE agent_runs ADD COLUMN metadata_json TEXT",
    # spec_clauses: add confidence_score
    "ALTER TABLE spec_clauses ADD COLUMN confidence_score REAL DEFAULT 0.5",
]

print("Running DCPI database migrations...")
for sql in migrations:
    try:
        db.execute(sql)
        print(f"  ✓ {sql[:60]}")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"  ↷ Already exists: {sql[28:60]}")
        else:
            print(f"  ✗ Failed: {e}")

db.commit()
db.close()
print("Migration complete.")