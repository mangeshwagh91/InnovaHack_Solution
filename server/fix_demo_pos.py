import sqlite3
import uuid

db = sqlite3.connect('dcpi.db')
cursor = db.cursor()

# Get all submittal documents that don't have a PO
submittals = cursor.execute("""
    SELECT d.id, d.project_id 
    FROM documents d 
    LEFT JOIN purchase_orders p ON d.id = p.document_id 
    WHERE d.doc_type = 'submittal' AND p.id IS NULL
""").fetchall()

for doc_id, project_id in submittals:
    po_id = "po-" + doc_id[:8]
    cursor.execute("""
        INSERT INTO purchase_orders (id, project_id, po_number, vendor_name, document_id, po_date, compliance_status, deviation_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (po_id, project_id, f"PO-{doc_id[:4].upper()}", "Demo Vendor", doc_id, "2026-07-19", "PENDING", 0))

db.commit()
db.close()
print("Fixed POs")
