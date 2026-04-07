import sqlite3
import os

def check_db(db_path):
    if not os.path.exists(db_path):
        print(f"{db_path} does not exist.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM cad_assets")
        count = cursor.fetchone()[0]
        print(f"{db_path}: {count} assets")
        
        if count > 0:
            cursor.execute("SELECT name, description, file_path FROM cad_assets LIMIT 5")
            rows = cursor.fetchall()
            for r in rows:
                print(f" - {r}")
        conn.close()
    except Exception as e:
        print(f"Error reading {db_path}: {e}")

if __name__ == "__main__":
    check_db(r"C:\Users\scs83\PhysicalProbe\cad_a.db")
    check_db(r"C:\Users\scs83\PhysicalProbe\cad_b.db")
