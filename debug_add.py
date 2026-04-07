
import requests
import sqlite3
import os

BASE = r"C:\Users\scs83\PhysicalProbe"
DB = os.path.join(BASE, "cad_a.db")
URL = "http://127.0.0.1:6001/add"

def check_db():
    print(f"Checking DB: {DB}")
    if not os.path.exists(DB):
        print("DB file does NOT exist!")
        return
    
    try:
        conn = sqlite3.connect(DB)
        rows = list(conn.execute("SELECT name, description, file_path FROM cad_assets").fetchall())
        with open("db_dump.txt", "w") as f:
            f.write(f"DB Row Count: {len(rows)}\n")
            for r in rows:
                f.write(f" - Added: {r[0]} | File: {r[2]}\n")
        conn.close()
    except Exception as e:
        with open("db_dump.txt", "w") as f:
            f.write(f"DB Error: {e}")

def test_add():
    print("\n--- Attempting to ADD ---")
    # Create a dummy PDF
    with open("dummy.pdf", "wb") as f:
        f.write(b"%PDF-1.4 dummy content")
    
    files = {'file': ('dummy.pdf', open('dummy.pdf', 'rb'), 'application/pdf')}
    data = {'name': 'DebugAsset', 'description': 'Test asset for debugging'}
    
    try:
        r = requests.post(URL, data=data, files=files)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Request Error: {e}")

if __name__ == "__main__":
    check_db()
    test_add()
    check_db()
