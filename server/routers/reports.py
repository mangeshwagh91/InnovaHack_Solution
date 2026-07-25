import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from database.connection import get_db

router = APIRouter()

@router.get("/{project_id}/export")
async def export_project_report(project_id: str):
    db = get_db()
    try:
        # Fetch Project Info
        project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Fetch NCRs
        ncrs = db.execute("""
            SELECT n.title, n.severity, n.status, d.attribute_name, d.specified_value, d.submitted_value 
            FROM ncrs n
            LEFT JOIN deviations d ON n.deviation_id = d.id
            WHERE d.po_id IN (SELECT id FROM purchase_orders WHERE project_id = ?)
            OR n.po_id IN (SELECT id FROM purchase_orders WHERE project_id = ?)
        """, (project_id, project_id)).fetchall()

        # Fetch Schedule Risk Tasks
        schedule = db.execute("""
            SELECT task_code, description, risk_score, total_float_days, delay_probability 
            FROM schedule_tasks 
            WHERE project_id = ? AND risk_score > 0.3
            ORDER BY risk_score DESC
        """, (project_id,)).fetchall()

        # Fetch RFIs
        rfis = db.execute("""
            SELECT rfi_code, title, status, rfi_type
            FROM rfis 
            WHERE project_id = ?
        """, (project_id,)).fetchall()

        # Fetch Purchase Orders
        pos = db.execute("""
            SELECT po_number, vendor_name, compliance_status, deviation_count 
            FROM purchase_orders 
            WHERE project_id = ?
        """, (project_id,)).fetchall()

        # Build Markdown Report
        report = []
        report.append(f"# DataForge Intelligence Report")
        report.append(f"**Generated on:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Project:** {project['name']}")
        report.append(f"**Status:** {project['status'].upper()}")
        report.append(f"**Deadline:** {project['deadline']}")
        report.append(f"**Size:** {project['size_mw']} MW")
        report.append("---\n")

        # Schedule Section
        report.append(f"## Schedule Risk Analysis")
        if schedule:
            report.append(f"Found {len(schedule)} task(s) at risk.")
            for s in schedule:
                report.append(f"- **[{s['task_code']}]** {s['description']}")
                report.append(f"  Risk Score: {s['risk_score']} | Float Days: {s['total_float_days']} | Delay Prob: {s['delay_probability']}")
        else:
            report.append("No critical schedule risks detected.")
        report.append("\n")

        # Compliance / NCRs Section
        report.append(f"## Compliance & Deviations (NCRs)")
        if ncrs:
            report.append(f"Found {len(ncrs)} NCR(s).")
            for n in ncrs:
                report.append(f"- **{n['severity']}**: {n['title']} (Status: {n['status']})")
                if n['attribute_name']:
                    report.append(f"  *Deviation*: {n['attribute_name']} - Required: {n['specified_value']} vs Submitted: {n['submitted_value']}")
        else:
            report.append("No open NCRs found.")
        report.append("\n")

        # Supply Chain / POs Section
        report.append(f"## Supply Chain")
        if pos:
            report.append(f"Found {len(pos)} Purchase Order(s).")
            for p in pos:
                report.append(f"- **{p['po_number']}** ({p['vendor_name']}) - Status: {p['compliance_status']} - Deviations: {p['deviation_count']}")
        else:
            report.append("No supply chain data available.")
        report.append("\n")

        # RFIs Section
        report.append(f"## Requests For Information (RFIs)")
        if rfis:
            report.append(f"Found {len(rfis)} RFI(s).")
            for r in rfis:
                report.append(f"- **[{r['rfi_code']}]** {r['title']} ({r['rfi_type']} - {r['status']})")
        else:
            report.append("No RFIs found.")

        return PlainTextResponse(content="\n".join(report))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
