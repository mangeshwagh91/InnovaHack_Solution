import logging
from database.connection import get_db

logger = logging.getLogger(__name__)


def init_db():
    db = get_db()
    try:
        # Enable WAL mode for better concurrent write performance
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA cache_size=-64000")  # 64MB page cache
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                size_mw REAL,
                deadline TEXT,
                budget REAL,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                location TEXT,
                capacity_unit TEXT,
                equipment_budget REAL,
                tier TEXT,
                description TEXT,
                pm TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                filename TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                upload_ts TEXT NOT NULL,
                file_path TEXT,
                status TEXT NOT NULL DEFAULT 'uploaded',
                page_count INTEGER DEFAULT 0
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS spec_clauses (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id),
                clause_number TEXT NOT NULL,
                clause_title TEXT,
                equipment_class TEXT NOT NULL DEFAULT 'UPS',
                clause_type TEXT DEFAULT 'TECHNICAL',
                raw_text TEXT,
                requirements_json TEXT NOT NULL DEFAULT '[]',
                tier TEXT DEFAULT 'TIER_IV',
                page_refs_json TEXT DEFAULT '[]',
                extracted_ts TEXT,
                confidence_score REAL DEFAULT 0.5
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS equipment_items (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                item_code TEXT NOT NULL,
                description TEXT NOT NULL,
                equipment_class TEXT NOT NULL,
                design_zone TEXT,
                quantity INTEGER DEFAULT 1,
                unit TEXT DEFAULT 'EA',
                required_by_date TEXT,
                spec_clause_ids_json TEXT DEFAULT '[]',
                criticality TEXT DEFAULT 'HIGH',
                compliance_score REAL DEFAULT 1.0
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                po_number TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                vendor_country TEXT DEFAULT 'India',
                document_id TEXT REFERENCES documents(id),
                equipment_item_id TEXT REFERENCES equipment_items(id),
                po_date TEXT,
                technical_attributes_json TEXT DEFAULT '{}',
                compliance_status TEXT DEFAULT 'PENDING',
                deviation_count INTEGER DEFAULT 0,
                conformance_score REAL DEFAULT 1.0,
                checked_ts TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS deviations (
                id TEXT PRIMARY KEY,
                po_id TEXT NOT NULL REFERENCES purchase_orders(id),
                spec_clause_id TEXT REFERENCES spec_clauses(id),
                attribute_name TEXT NOT NULL,
                specified_value TEXT NOT NULL,
                submitted_value TEXT NOT NULL,
                deviation_pct REAL,
                severity TEXT NOT NULL,
                deviation_type TEXT DEFAULT 'VALUE',
                w_conform REAL DEFAULT 0.5,
                justification TEXT,
                recommended_action TEXT,
                detected_ts TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS ncrs (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                deviation_id TEXT NOT NULL REFERENCES deviations(id),
                po_id TEXT NOT NULL REFERENCES purchase_orders(id),
                equipment_item_id TEXT REFERENCES equipment_items(id),
                title TEXT NOT NULL,
                description TEXT,
                severity TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                raised_ts TEXT NOT NULL,
                due_date TEXT,
                assigned_to TEXT DEFAULT 'Quality Manager',
                resolution_text TEXT,
                spec_clause_ref TEXT,
                page_ref TEXT,
                schedule_impact_json TEXT DEFAULT '{}',
                actions_json TEXT DEFAULT '[]'
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS schedule_tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                task_code TEXT NOT NULL,
                description TEXT NOT NULL,
                planned_start TEXT NOT NULL,
                planned_finish TEXT NOT NULL,
                total_float_days INTEGER NOT NULL DEFAULT 0,
                original_float_days INTEGER NOT NULL DEFAULT 0,
                predecessor_ids_json TEXT DEFAULT '[]',
                equipment_item_id TEXT REFERENCES equipment_items(id),
                percent_complete REAL DEFAULT 0.0,
                risk_score REAL DEFAULT 0.0,
                delay_probability REAL DEFAULT 0.0,
                risk_level TEXT DEFAULT 'negligible',
                is_critical_path INTEGER DEFAULT 0,
                mitigation_text TEXT,
                risk_checked_ts TEXT,
                actual_start TEXT,
                actual_finish TEXT,
                actual_delay_days INTEGER DEFAULT 0,
                predicted_delay_days INTEGER DEFAULT 0,
                historical_avg_delay REAL DEFAULT 0.0
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS commissioning_records (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES schedule_tasks(id),
                step_number INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                step_type TEXT DEFAULT 'CHECK',
                acceptance_criteria TEXT,
                actual_value TEXT,
                status TEXT DEFAULT 'pending',
                pass_fail TEXT DEFAULT 'pending',
                flagged_ncr_id TEXT REFERENCES ncrs(id),
                checked_by TEXT DEFAULT 'System',
                checked_ts TEXT,
                notes TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS rfis (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                rfi_code TEXT NOT NULL,
                rfi_type TEXT DEFAULT 'TECHNICAL',
                title TEXT NOT NULL,
                description TEXT,
                raised_by TEXT,
                raised_ts TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                response_due_ts TEXT,
                resolution_text TEXT,
                equipment_item_ids_json TEXT DEFAULT '[]',
                spec_clause_refs_json TEXT DEFAULT '[]',
                chroma_doc_id TEXT,
                is_resolved INTEGER DEFAULT 0
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(id),
                agent_name TEXT NOT NULL,
                agent_version TEXT DEFAULT '1.0.0',
                trigger_event TEXT,
                input_summary TEXT,
                output_summary TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                started_ts TEXT NOT NULL,
                completed_ts TEXT,
                error_text TEXT,
                records_processed INTEGER DEFAULT 0,
                records_created INTEGER DEFAULT 0,
                metadata_json TEXT
            )
        """)



        db.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                id TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS tenders (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                vendor_id TEXT NOT NULL REFERENCES vendors(id),
                price REAL NOT NULL,
                lead_time_days INTEGER NOT NULL,
                equipment_catalog_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'submitted',
                ai_recommendation TEXT,
                ai_scores_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS cost_records (
                id TEXT PRIMARY KEY,
                po_id TEXT REFERENCES purchase_orders(id),
                equipment_item_id TEXT REFERENCES equipment_items(id),
                delay_days INTEGER NOT NULL DEFAULT 0,
                daily_rate REAL NOT NULL DEFAULT 0,
                total_impact REAL NOT NULL DEFAULT 0,
                mitigation_cost REAL DEFAULT 0,
                impact_category TEXT DEFAULT 'Liquidated Damages',
                currency TEXT DEFAULT 'USD',
                narrative TEXT,
                calculated_ts TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS vendor_scores (
                id TEXT PRIMARY KEY,
                vendor_id TEXT NOT NULL REFERENCES vendors(id),
                project_id TEXT REFERENCES projects(id),
                compliance_score REAL DEFAULT 1.0,
                delivery_score REAL DEFAULT 1.0,
                quality_score REAL DEFAULT 1.0,
                overall_score REAL DEFAULT 1.0,
                ncr_count INTEGER DEFAULT 0,
                critical_ncr_count INTEGER DEFAULT 0,
                tenders_submitted INTEGER DEFAULT 0,
                tenders_won INTEGER DEFAULT 0,
                narrative TEXT,
                calculated_ts TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS workforce_demand (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES schedule_tasks(id),
                week_start TEXT NOT NULL,
                discipline TEXT NOT NULL,
                required_headcount INTEGER NOT NULL DEFAULT 0,
                available_headcount INTEGER DEFAULT 0,
                conflict INTEGER DEFAULT 0
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                report_type TEXT NOT NULL DEFAULT 'project_health',
                project_id TEXT REFERENCES projects(id),
                generated_ts TEXT NOT NULL,
                summary_json TEXT DEFAULT '{}',
                executive_summary TEXT,
                status TEXT DEFAULT 'complete'
            )
        """)

        # Indexes
        db.execute("CREATE INDEX IF NOT EXISTS idx_spec_clauses_doc ON spec_clauses(document_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_spec_clauses_class ON spec_clauses(equipment_class)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_deviations_po ON deviations(po_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_deviations_severity ON deviations(severity)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_deviations_clause ON deviations(spec_clause_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_ncrs_severity ON ncrs(severity)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_ncrs_status ON ncrs(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_ncrs_po ON ncrs(po_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_ncrs_equipment ON ncrs(equipment_item_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_schedule_risk ON schedule_tasks(risk_score)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_schedule_equipment ON schedule_tasks(equipment_item_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_schedule_critical ON schedule_tasks(is_critical_path)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_rfis_resolved ON rfis(is_resolved)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_po_equipment ON purchase_orders(equipment_item_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_name ON agent_runs(agent_name)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tenders_project ON tenders(project_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tenders_vendor ON tenders(vendor_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_commissioning_task ON commissioning_records(task_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_commissioning_status ON commissioning_records(status)")
        
        # Seed default projects if none exist removed as per user request

        db.commit()
        # Migrate existing tables to add new columns if missing
        _migrate_schedule_tasks(db)
        _migrate_projects(db)
        _migrate_tenders(db)
        _migrate_new_tables(db)
        _migrate_project_ids(db)
        _seed_mock_shipments(db)
        _seed_demo_vendor(db)
    finally:
        db.close()

def _seed_demo_vendor(db) -> None:
    count = db.execute("SELECT count(*) FROM vendors WHERE id = 'demo-vendor'").fetchone()[0]
    if count == 0:
        db.execute('''
            INSERT INTO vendors (id, company_name, email, password_hash, registered_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', ('demo-vendor', 'Delta Systems', 'vendor@delta.com', 'dummyhash'))
        db.commit()
        logger.info("Demo vendor seeded.")

def _seed_mock_shipments(db) -> None:
    """Seed some mock shipments if none exist to demonstrate the supply chain tracking."""
    count = db.execute("SELECT count(*) FROM shipments").fetchone()[0]
    if count == 0:
        import uuid
        from datetime import datetime, timedelta, timezone
        
        now = datetime.now(timezone.utc)
        
        # We'll create a dummy project, vendor, equipment, and PO just in case none exist,
        # but realistically we just want the shipment row to exist so we can query it.
        # Texas to Data Center (Mock) - At Risk!
        s1_id = str(uuid.uuid4())
        db.execute('''
            INSERT INTO shipments (
                id, carrier_name, tracking_number, origin_lat, origin_lng, dest_lat, dest_lng,
                current_lat, current_lng, status, estimated_arrival, required_delivery, risk_level, last_updated_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            s1_id, "FedEx Custom Critical", "FX-88392019-UPS", 
            32.7767, -96.7970, # Dallas, TX
            39.0438, -77.4874, # Ashburn, VA (Data Center Alley)
            35.1495, -90.0490, # Currently near Memphis, TN (Delayed by weather)
            "delayed",
            (now + timedelta(days=5)).isoformat(), # Estimated in 5 days
            (now + timedelta(days=2)).isoformat(), # Required in 2 days (LATE!)
            "HIGH",
            now.isoformat()
        ))
        
        # New York to Ashburn - On Time
        s2_id = str(uuid.uuid4())
        db.execute('''
            INSERT INTO shipments (
                id, carrier_name, tracking_number, origin_lat, origin_lng, dest_lat, dest_lng,
                current_lat, current_lng, status, estimated_arrival, required_delivery, risk_level, last_updated_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            s2_id, "ATS Logistics", "ATS-99482-GEN", 
            40.7128, -74.0060, # NY
            39.0438, -77.4874, # Ashburn, VA
            39.9526, -75.1652, # Near Philly
            "in_transit",
            (now + timedelta(days=1)).isoformat(),
            (now + timedelta(days=3)).isoformat(),
            "LOW",
            now.isoformat()
        ))
        db.commit()
        logger.info("Mock shipments seeded.")



def _migrate_project_ids(db) -> None:
    """Add project_id column to core tables if missing."""
    tables = ["documents", "equipment_items", "purchase_orders", "ncrs", "schedule_tasks", "rfis", "agent_runs"]
    for table in tables:
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if "project_id" not in existing:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN project_id TEXT REFERENCES projects(id)")
                logger.info(f"Migrated {table}: added column project_id")
            except Exception as e:
                logger.warning(f"Could not add column project_id to {table}: {e}")
    db.commit()


def _migrate_projects(db) -> None:
    """Add new columns to projects if they don't exist (migration-safe)."""
    new_cols = [
        ("location", "TEXT"),
    ]
    existing = {row[1] for row in db.execute("PRAGMA table_info(projects)").fetchall()}
    for col_name, col_type in new_cols:
        if col_name not in existing:
            try:
                db.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                logger.info(f"Migrated projects: added column {col_name}")
            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")
    db.commit()


def _migrate_schedule_tasks(db) -> None:
    """Add new columns to schedule_tasks if they don't exist (migration-safe)."""
    new_cols = [
        ("actual_start", "TEXT"),
        ("actual_finish", "TEXT"),
        ("actual_delay_days", "INTEGER DEFAULT 0"),
        ("predicted_delay_days", "INTEGER DEFAULT 0"),
        ("historical_avg_delay", "REAL DEFAULT 0.0"),
    ]
    existing = {row[1] for row in db.execute("PRAGMA table_info(schedule_tasks)").fetchall()}
    for col_name, col_type in new_cols:
        if col_name not in existing:
            try:
                db.execute(f"ALTER TABLE schedule_tasks ADD COLUMN {col_name} {col_type}")
                logger.info(f"Migrated schedule_tasks: added column {col_name}")
            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")
    db.commit()


def _migrate_tenders(db) -> None:
    """Add ai_recommendation and ai_scores_json columns to tenders if missing."""
    new_cols = [
        ("ai_recommendation", "TEXT"),
        ("ai_scores_json", "TEXT DEFAULT '{}'"),
    ]
    existing = {row[1] for row in db.execute("PRAGMA table_info(tenders)").fetchall()}
    for col_name, col_type in new_cols:
        if col_name not in existing:
            try:
                db.execute(f"ALTER TABLE tenders ADD COLUMN {col_name} {col_type}")
                logger.info(f"Migrated tenders: added column {col_name}")
            except Exception as e:
                logger.warning(f"Could not add column {col_name} to tenders: {e}")
    db.commit()


def _migrate_new_tables(db) -> None:
    """
    Create new tables added in the production upgrade if they do not yet exist.
    Safe to call multiple times (CREATE TABLE IF NOT EXISTS).
    """
    tables = [
        (
            "cost_records",
            """CREATE TABLE IF NOT EXISTS cost_records (
                id TEXT PRIMARY KEY,
                po_id TEXT REFERENCES purchase_orders(id),
                equipment_item_id TEXT REFERENCES equipment_items(id),
                delay_days INTEGER NOT NULL DEFAULT 0,
                daily_rate REAL NOT NULL DEFAULT 0,
                total_impact REAL NOT NULL DEFAULT 0,
                mitigation_cost REAL DEFAULT 0,
                impact_category TEXT DEFAULT 'Liquidated Damages',
                currency TEXT DEFAULT 'USD',
                narrative TEXT,
                calculated_ts TEXT NOT NULL
            )"""
        ),
        (
            "vendor_scores",
            """CREATE TABLE IF NOT EXISTS vendor_scores (
                id TEXT PRIMARY KEY,
                vendor_id TEXT NOT NULL REFERENCES vendors(id),
                project_id TEXT REFERENCES projects(id),
                compliance_score REAL DEFAULT 1.0,
                delivery_score REAL DEFAULT 1.0,
                quality_score REAL DEFAULT 1.0,
                overall_score REAL DEFAULT 1.0,
                ncr_count INTEGER DEFAULT 0,
                critical_ncr_count INTEGER DEFAULT 0,
                bids_submitted INTEGER DEFAULT 0,
                bids_won INTEGER DEFAULT 0,
                narrative TEXT,
                calculated_ts TEXT NOT NULL
            )"""
        ),
        (
            "workforce_demand",
            """CREATE TABLE IF NOT EXISTS workforce_demand (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES schedule_tasks(id),
                week_start TEXT NOT NULL,
                discipline TEXT NOT NULL,
                required_headcount INTEGER NOT NULL DEFAULT 0,
                available_headcount INTEGER DEFAULT 0,
                conflict INTEGER DEFAULT 0
            )"""
        ),
        (
            "reports",
            """CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                report_type TEXT NOT NULL DEFAULT 'project_health',
                project_id TEXT REFERENCES projects(id),
                generated_ts TEXT NOT NULL,
                summary_json TEXT DEFAULT '{}',
                executive_summary TEXT,
                status TEXT DEFAULT 'complete'
            )"""
        ),
        (
            "shipments",
            """CREATE TABLE IF NOT EXISTS shipments (
                id TEXT PRIMARY KEY,
                po_id TEXT REFERENCES purchase_orders(id),
                equipment_item_id TEXT REFERENCES equipment_items(id),
                vendor_id TEXT REFERENCES vendors(id),
                carrier_name TEXT,
                tracking_number TEXT,
                origin_lat REAL,
                origin_lng REAL,
                dest_lat REAL,
                dest_lng REAL,
                current_lat REAL,
                current_lng REAL,
                status TEXT DEFAULT 'in_transit',
                estimated_arrival TEXT,
                required_delivery TEXT,
                risk_level TEXT DEFAULT 'LOW',
                ai_alternatives_json TEXT DEFAULT '[]',
                last_updated_ts TEXT
            )"""
        ),
    ]
    for table_name, create_sql in tables:
        try:
            db.execute(create_sql)
            logger.info(f"Table '{table_name}' ensured.")
        except Exception as e:
            logger.warning(f"Could not ensure table '{table_name}': {e}")
    db.commit()