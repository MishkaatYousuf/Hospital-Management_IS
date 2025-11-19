import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db import setup_database, get_connection, log_action, purge_old_records
from security import encrypt_data, decrypt_data, mask_contact, mask_name
import sqlite3
import os

setup_database()
st.set_page_config(page_title="GDPR Hospital Dashboard (Bonus)", layout="wide")

# Session init

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "consent" not in st.session_state:
    st.session_state.consent = False
if "start_time" not in st.session_state:
    st.session_state.start_time = datetime.utcnow()


# Consent banner 

if not st.session_state.consent:
    with st.sidebar:
        st.warning("We use this demo system to process personal data for educational purposes.")
        if st.button("I Consent"):
            st.session_state.consent = True
            st.success("Consent recorded")
            # log anonymous consent (no user_id yet)
            conn = get_connection()
            conn.execute("INSERT INTO logs(user_id, role, action, timestamp, details) VALUES (?,?,?,?,?)",
                         (None, "anon", "consent", datetime.utcnow().isoformat(), "User consented"))
            conn.commit()
            conn.close()

if not st.session_state.logged_in:
    st.title("🔒 GDPR Hospital Dashboard — Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id, role FROM users WHERE username=? AND password=?", (username, password))
        row = cur.fetchone()
        conn.close()
        if row:
            st.session_state.logged_in = True
            st.session_state.user_id = row[0]
            st.session_state.role = row[1]
            log_action(st.session_state.user_id, st.session_state.role, "login", f"{username} logged in")
            st.rerun()

        else:
            st.error("Invalid credentials")
    st.stop()

role = st.session_state.role
st.sidebar.title(f"Hello, {role.capitalize()}")

# Role-based menu
if role == "admin":
    menu = st.sidebar.selectbox("Menu", ["Dashboard", "Add Patient", "View Raw Data", "Anonymize Data",
                                        "Encrypt/Decrypt", "Audit Logs", "Export Data", "Retention"])
elif role == "doctor":
    menu = st.sidebar.selectbox("Menu", ["View Anonymized Data"])
else:
    menu = st.sidebar.selectbox("Menu", ["Add Patient"])

# uptime / last sync
uptime = datetime.utcnow() - st.session_state.start_time
st.sidebar.caption(f"Uptime: {str(uptime).split('.')[0]}")


# Add patient

if menu == "Add Patient":
    st.header("➕ Add Patient")
    name = st.text_input("Name")
    contact = st.text_input("Contact")
    diagnosis = st.text_area("Diagnosis")
    if st.button("Save Patient"):
        if not name or not contact:
            st.error("Name and contact required")
        else:
            conn = get_connection()
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            encrypted_name = encrypt_data(name)
            encrypted_contact = encrypt_data(contact)
            cur.execute("""INSERT INTO patients(name, contact, diagnosis, anonymized_name,
                           anonymized_contact, encrypted_name, encrypted_contact, date_added)
                           VALUES(?,?,?,?,?,?,?,?)""",
                        (name, contact, diagnosis, None, None, encrypted_name, encrypted_contact, now))
            conn.commit()
            conn.close()
            log_action(st.session_state.user_id, role, "add_record", f"Added patient {name}")
            st.success("Saved (encrypted copy stored)")


# View Raw Data (admin)

if menu == "View Raw Data" and role == "admin":
    st.header("📁 Raw Patient Records (Admin)")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM patients", conn)
    st.dataframe(df)
    conn.close()


# Anonymize Data (admin)

if menu == "Anonymize Data" and role == "admin":
    st.header("🔐 Anonymize / Mask Data")
    if st.button("Run Masking for all patients"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT patient_id, name, contact FROM patients")
        rows = cur.fetchall()
        for pid, name, contact in rows:
            anonym_name = mask_name(name)
            anonym_contact = mask_contact(contact)
            cur.execute("UPDATE patients SET anonymized_name=?, anonymized_contact=? WHERE patient_id=?",
                        (anonym_name, anonym_contact, pid))
        conn.commit()
        conn.close()
        log_action(st.session_state.user_id, role, "anonymize", "Masked all patient identifiers")
        st.success("Masking complete")


# Encrypt/Decrypt (admin)

if menu == "Encrypt/Decrypt" and role == "admin":
    st.header("🔁 Encrypt / Decrypt Patient Fields (Fernet reversible)")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT patient_id, name, encrypted_name FROM patients")
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["patient_id", "name", "encrypted_name"])
    st.dataframe(df)
    pid = st.number_input("Patient ID to decrypt (enter ID)", min_value=1, step=1)
    if st.button("Decrypt Selected"):
        cur.execute("SELECT encrypted_name, encrypted_contact FROM patients WHERE patient_id=?", (pid,))
        r = cur.fetchone()
        if r and r[0]:
            try:
                dec_name = decrypt_data(r[0])
                dec_contact = decrypt_data(r[1])
                st.success("Decryption successful")
                st.code(f"Name: {dec_name}\nContact: {dec_contact}")
                log_action(st.session_state.user_id, role, "decrypt", f"Decrypted patient {pid}")
            except Exception as e:
                st.error("Decryption failed: " + str(e))
        else:
            st.info("No encrypted data present for that ID")
    conn.close()


# View Anonymized Data (doctor & admin)

if menu == "View Anonymized Data":
    st.header("🩺 Anonymized Patients")
    conn = get_connection()
    df = pd.read_sql_query("SELECT patient_id, anonymized_name, anonymized_contact, diagnosis, date_added FROM patients", conn)
    st.dataframe(df)
    conn.close()
    log_action(st.session_state.user_id, role, "view", "Viewed anonymized data")


# Audit Logs (admin)

if menu == "Audit Logs" and role == "admin":
    st.header("🧾 Audit Logs")
    conn = get_connection()
    logs_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC", conn)
    conn.close()
    st.dataframe(logs_df)

    # Activity graphs
    if not logs_df.empty:
        logs_df['ts'] = pd.to_datetime(logs_df['timestamp'], utc=True)
        logs_df['date'] = logs_df['ts'].dt.date
        actions_per_day = logs_df.groupby('date').size().reset_index(name='actions')
        st.subheader("Actions per day")
        st.bar_chart(actions_per_day.set_index('date'))

        st.subheader("Actions by role")
        by_role = logs_df.groupby('role').size().reset_index(name='actions')
        st.bar_chart(by_role.set_index('role'))


# Export data (admin)

if menu == "Export Data" and role == "admin":
    st.header("⬇ Export / Backup")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM patients", conn)
    conn.close()
    st.download_button("Download patients CSV", df.to_csv(index=False).encode(), "patients_backup.csv")
    log_action(st.session_state.user_id, role, "export", "Exported patient CSV")


# Retention (admin)

if menu == "Retention" and role == "admin":
    st.header("🗄 Data Retention (GDPR)")
    st.write("Set retention period (days). Records older than this can be purged.")
    retention_days = st.number_input("Retention days", min_value=1, value=365, step=1)
    if st.button("Purge old records now"):
        deleted = purge_old_records(retention_days)
        st.success(f"Deleted {deleted} old records")
        log_action(st.session_state.user_id, role, "purge", f"Purged {deleted} records older than {retention_days} days")


# Simple logout

if st.sidebar.button("Logout"):
    log_action(st.session_state.user_id, role, "logout", "User logged out")
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


st.sidebar.caption("System (demo) | last sync: " + datetime.utcnow().isoformat())
