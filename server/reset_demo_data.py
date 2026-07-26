import sqlite3
import os
import shutil

def reset_demo_data():
    """
    Cleans up all demonstration data to prepare the workspace for production use.
    This removes all projects, documents, RFIs, Purchase Orders, Schedule Tasks, and Tenders.
    """
    print("=" * 60)
    print("WARNING: This will permanently delete ALL demo data and reset the workspace.")
    print("=" * 60)
    
    confirm = input("Are you sure you want to proceed? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("Aborted.")
        return

    db_path = os.path.join(os.path.dirname(__file__), 'dcpi.db')
    if not os.path.exists(db_path):
        print("Database not found. Nothing to clean.")
        return

    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    # Tables to completely clear for a fresh production start
    tables_to_clear = [
        "ncrs",
        "deviations",
        "purchase_orders",
        "documents",
        "schedule_tasks",
        "tenders",
        "rfis",
        "spec_clauses",
        "commissioning_checklists",
        "shipments",
        "projects"
    ]

    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"Cleared table: {table}")
        except sqlite3.OperationalError as e:
            print(f"Skipping table {table} (Error: {e})")

    db.commit()
    db.close()

    # Clear ChromaDB vector index
    chroma_path = os.path.join(os.path.dirname(__file__), 'chroma_db')
    if os.path.exists(chroma_path):
        try:
            shutil.rmtree(chroma_path)
            print("Cleared vector database (ChromaDB)")
        except Exception as e:
            print(f"Could not delete ChromaDB directory: {e}")

    # Clear uploaded files folder
    uploads_path = os.path.join(os.path.dirname(__file__), 'uploads')
    if os.path.exists(uploads_path):
        for filename in os.listdir(uploads_path):
            file_path = os.path.join(uploads_path, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                pass
        print("Cleared uploaded files")

    print("=" * 60)
    print("SUCCESS: Workspace has been reset and is ready for production.")
    print("=" * 60)

if __name__ == "__main__":
    reset_demo_data()
