import sqlite3
from datetime import datetime, timedelta

DB_PATH = "hospital.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = 1")
    return conn

def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients(
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            contact TEXT,
            diagnosis TEXT,
            anonymized_name TEXT,
            anonymized_contact TEXT,
            encrypted_name TEXT,
            encrypted_contact TEXT,
            date_added TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            action TEXT,
            timestamp TEXT,
            details TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    # default users if none exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO users(username, password, role) VALUES(?,?,?)",
                           [('admin','admin123','admin'),
                            ('bob','doc123','doctor'),
                            ('alice','rec123','receptionist')])
    conn.commit()
    conn.close()

def log_action(user_id, role, action, details=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs(user_id, role, action, timestamp, details) VALUES(?,?,?,?,?)",
                   (user_id, role, action, datetime.utcnow().isoformat(), details))
    conn.commit()
    conn.close()

def purge_old_records(days):
    """Delete patients older than `days` days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE date_added < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted
