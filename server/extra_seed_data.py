import sys
import os
import json
from datetime import datetime

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_db

def run_extra_seed():
    db = get_db()
    db.execute("PRAGMA foreign_keys = OFF;")
    print("Seeding extra demo data (projects, vendors, tenders, ncrs, commissioning)...")

    # 1. Projects
    project_id_1 = "proj-vertex-001"
    project_id_2 = "proj-helios-002"
    project_id_3 = "proj-neon-003"

    now_iso = datetime.now().isoformat()

    db.execute("""
        INSERT OR REPLACE INTO projects 
        (id, name, size_mw, deadline, budget, status, created_at, location, tier, pm)
        VALUES 
        (?, 'Project VERTEX (Demo)', 50.0, '2026-12-31', 120000000.0, 'active', ?, 'Ashburn, VA', 'TIER_IV', 'Sarah Jenkins'),
        (?, 'Project HELIOS', 25.0, '2025-10-15', 65000000.0, 'active', ?, 'Frankfurt, DE', 'TIER_III', 'Markus Berg'),
        (?, 'Project NEON', 10.0, '2024-11-20', 30000000.0, 'paused', ?, 'Singapore', 'TIER_III', 'Li Wei')
    """, (project_id_1, now_iso, project_id_2, now_iso, project_id_3, now_iso))

    # 2. Update existing records to link to project_id_1
    db.execute("UPDATE documents SET project_id = ?", (project_id_1,))
    db.execute("UPDATE equipment_items SET project_id = ?", (project_id_1,))
    db.execute("UPDATE purchase_orders SET project_id = ?", (project_id_1,))
    db.execute("UPDATE schedule_tasks SET project_id = ?", (project_id_1,))
    db.execute("UPDATE rfis SET project_id = ?", (project_id_1,))
    db.execute("UPDATE shipments SET po_id = 'po-ps1500-001', vendor_id = 'ven-ps-001', equipment_item_id = 'eq-ups-moda-001'")

    # 3. Vendors
    vendor_id_1 = "ven-ps-001"
    vendor_id_2 = "ven-schneider-002"
    db.execute("""
        INSERT OR REPLACE INTO vendors (id, company_name, email, password_hash, registered_at)
        VALUES 
        (?, 'PowerShield Technologies', 'contact@powershield.demo', 'hash', ?),
        (?, 'Schneider Electric', 'sales@schneider.demo', 'hash', ?)
    """, (vendor_id_1, now_iso, vendor_id_2, now_iso))

    # 4. Tenders
    db.execute("""
        INSERT OR REPLACE INTO tenders (id, project_id, vendor_id, price, lead_time_days, status, ai_recommendation, created_at)
        VALUES 
        ('tender-001', ?, ?, 1250000.0, 120, 'submitted', 'Recommended based on price and compliance.', ?),
        ('tender-002', ?, ?, 1400000.0, 90, 'submitted', 'Alternative: Faster delivery but higher cost.', ?)
    """, (project_id_1, vendor_id_1, now_iso, project_id_1, vendor_id_2, now_iso))

    # 5. Commissioning Records
    db.execute("""
        INSERT OR REPLACE INTO commissioning_records (id, task_id, step_number, step_name, acceptance_criteria, actual_value, status, pass_fail)
        VALUES 
        ('cr-001', 'T-009', 1, 'Visual Inspection', 'No damage', 'No damage observed', 'completed', 'PASS'),
        ('cr-002', 'T-009', 2, 'Battery Autonomy', '>= 10 mins', '8 mins', 'completed', 'FAIL')
    """)

    # 6. NCRs (mock an NCR for the failing battery autonomy)
    db.execute("""
        INSERT OR REPLACE INTO deviations (id, po_id, attribute_name, specified_value, submitted_value, deviation_pct, severity, detected_ts)
        VALUES ('dev-001', 'po-ps1500-001', 'battery_autonomy_min', '10', '8', 20.0, 'MAJOR', ?)
    """, (now_iso,))

    db.execute("""
        INSERT OR REPLACE INTO ncrs (id, project_id, deviation_id, po_id, title, description, severity, status, raised_ts)
        VALUES ('ncr-001', ?, 'dev-001', 'po-ps1500-001', 'Battery Autonomy Non-Compliance', 'Submitted 8 min vs required 10 min.', 'MAJOR', 'open', ?)
    """, (project_id_1, now_iso))

    db.commit()
    db.close()
    print("Extra demo data seeded successfully!")

if __name__ == "__main__":
    run_extra_seed()
