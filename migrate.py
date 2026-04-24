"""Them cot moi vao database cu (khong mat du lieu)."""
import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "brewmanager.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

migrations = [
    ("categories", "description", "TEXT"),
    ("areas", "description", "TEXT"),
    ("users", "phone", "VARCHAR(20)"),
]

for table, column, col_type in migrations:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        print(f"  + {table}.{column}")
    else:
        print(f"  = {table}.{column} (da co)")

conn.commit()
conn.close()
print("\nMigrate xong!")
