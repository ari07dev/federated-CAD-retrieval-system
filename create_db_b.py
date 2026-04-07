import sqlite3
import os

BASE = r"C:\Users\scs83\PhysicalProbe"
CAD_DIR = os.path.join(BASE, "cad_files_b")
DB = os.path.join(BASE, "cad_b.db")

conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS cad_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    file_path TEXT
)
""")

for f in os.listdir(CAD_DIR):
    if f.endswith(".pdf"):
        name = f.replace("_", " ").replace(".pdf", "")
        desc = f"{name} CAD drawing"
        path = f"cad_files_b/{f}"

        c.execute(
            "INSERT INTO cad_assets (name, description, file_path) VALUES (?,?,?)",
            (name, desc, path)
        )

conn.commit()
conn.close()

print("NODE B DB rebuilt")