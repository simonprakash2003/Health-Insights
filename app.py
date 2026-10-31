import os
import re
import sqlite3
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "Health Insights | Patient Records"
DB_PATH = os.getenv("DATABASE_PATH", "patients.db")
DATE_FORMATS = ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                dob TEXT NOT NULL,
                email TEXT NOT NULL,
                glucose REAL NOT NULL,
                haemoglobin REAL NOT NULL,
                cholesterol REAL NOT NULL,
                remarks TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def parse_dob(value: str):
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt).date()
            return parsed
        except ValueError:
            continue
    raise ValueError("Enter a valid date using DD/MM/YYYY (DD.MM.YYYY is also accepted for the supplied assessment data).")


def validate_patient(full_name, dob_text, email, glucose, haemoglobin, cholesterol):
    errors = []
    if not full_name.strip():
        errors.append("Full name is required.")
    try:
        dob = parse_dob(dob_text)
        if dob > date.today():
            errors.append("Date of birth cannot be in the future.")
    except ValueError as exc:
        dob = None
        errors.append(str(exc))
    if not EMAIL_RE.fullmatch(email.strip()):
        errors.append("Email address is not in a valid format.")
    numeric_values = {}
    for label, value in (
        ("Glucose", glucose),
        ("Haemoglobin", haemoglobin),
        ("Cholesterol", cholesterol),
    ):
        try:
            number = float(value)
            if number < 0:
                errors.append(f"{label} must be zero or greater.")
            numeric_values[label] = number
        except (TypeError, ValueError):
            errors.append(f"{label} must be numeric.")
    return errors, dob, numeric_values



def generate_ai_remarks(patient):
    """Generate non-diagnostic health remarks using local Ollama."""

    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    prompt = f"""
    You are an informational health education assistant.

    Review these patient blood test values:
    Glucose: {patient['glucose']}
    Haemoglobin: {patient['haemoglobin']}
    Cholesterol: {patient['cholesterol']}

    Provide 2-4 sentences describing possible areas
    that may require clinical review.

    Do not diagnose any disease.
    Do not prescribe medication.
    Do not assume measurement units or reference ranges.
    Explain that results must be interpreted by a
    qualified healthcare professional.
    """

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You provide cautious, non-diagnostic health information."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False
        },
        timeout=180
    )

    response.raise_for_status()

    result = response.json()

    return result["message"]["content"].strip()



def add_patient(values):
    remarks = generate_ai_remarks(values)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO patients
            (full_name, dob, email, glucose, haemoglobin, cholesterol, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                values["full_name"], values["dob"].isoformat(), values["email"],
                values["glucose"], values["haemoglobin"], values["cholesterol"], remarks
            ),
        )
        conn.commit()


def fetch_patients():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def update_patient(patient_id, email):
    with get_connection() as conn:
        conn.execute("UPDATE patients SET email = ? WHERE id = ?", (email.strip(), patient_id))
        conn.commit()


def delete_patient(patient_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        conn.commit()

def drop_table():
    with get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS patients")
        conn.commit()
        
def format_date(iso_date):
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")


st.set_page_config(page_title=APP_TITLE, page_icon="🩺", layout="wide")
init_db()

st.title("🩺 Health Insights")
st.caption("Patient record management with AI-assisted, non-diagnostic health remarks")
st.info(
    "Educational assessment prototype only. It does not diagnose disease or replace medical advice. "
    "Use only appropriately authorised test data; avoid entering real patient-identifiable information."
)

menu = st.sidebar.radio("Navigation", ["Dashboard", "Add Patient", "View / Manage Records"])
if menu == "Dashboard":
    records = fetch_patients()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total records", len(records))
    c2.metric("Unique email addresses", len({r["email"].lower() for r in records}) if records else 0)
    c3.metric("AI remarks generated", sum("AI API not configured" not in r["remarks"] for r in records))
    st.subheader("Latest patient records")
    if records:
        display = [{
            "ID": r["id"], "Full Name": r["full_name"], "DOB": format_date(r["dob"]),
            "Email": r["email"], "Glucose": r["glucose"],
            "Haemoglobin": r["haemoglobin"], "Cholesterol": r["cholesterol"]
        } for r in records[-5:]]
        st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
    else:
        st.write("No patient records yet. Use **Add Patient** to create the first record.")
    st.subheader("Workflow")
    st.write("Validate input → request AI-assisted remarks → save record in SQLite → manage records.")

elif menu == "Add Patient":
    st.subheader("Create patient record")
    with st.form("add_patient_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name")
            dob_text = st.text_input("Date of birth (DD/MM/YYYY)", placeholder="28/01/1960")
            email = st.text_input("Email address")
        with col2:
            glucose = st.text_input("Glucose")
            haemoglobin = st.text_input("Haemoglobin")
            cholesterol = st.text_input("Cholesterol")
        submitted = st.form_submit_button("Validate and save", type="primary")
    if submitted:
        errors, dob, nums = validate_patient(full_name, dob_text, email, glucose, haemoglobin, cholesterol)
        if errors:
            st.error("Record was not saved. Please correct the following:")
            for error in errors:
                st.write(f"• {error}")
        else:
            values = {
                "full_name": full_name.strip(), "dob": dob, "email": email.strip(),
                "glucose": nums["Glucose"], "haemoglobin": nums["Haemoglobin"],
                "cholesterol": nums["Cholesterol"]
            }
            try:
                with st.spinner("Generating AI-assisted remarks and saving record..."):
                    add_patient(values)
                st.success("Patient record saved successfully.")
                
            except requests.RequestException as exc:
                st.error(f"AI API request failed; record was not saved. API error: {exc}")
            except (KeyError, IndexError, ValueError) as exc:
                st.error(f"AI API response could not be processed; record was not saved: {exc}")
    
elif menu == "View / Manage Records":
    st.subheader("Read, update and delete patient records")
    records = fetch_patients()
    if not records:
        st.warning("No records available.")
    else:
        table = [{
            "ID": r["id"], "Full Name": r["full_name"], "Date of Birth": format_date(r["dob"]),
            "Email": r["email"], "Glucose": r["glucose"], "Haemoglobin": r["haemoglobin"],
            "Cholesterol": r["cholesterol"], "AI Remarks": r["remarks"]
        } for r in records]
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        st.divider()
        ids = [r["id"] for r in records]
        selected_id = st.selectbox("Select record ID", ids)
        selected = next(r for r in records if r["id"] == selected_id)
        with st.expander("Update email address"):
            with st.form("update_form"):
                new_email = st.text_input("New email", value=selected["email"])
                update_submit = st.form_submit_button("Update email")
            if update_submit:
                if not EMAIL_RE.fullmatch(new_email.strip()):
                    st.error("Please enter a valid email address.")
                else:
                    update_patient(selected_id, new_email)
                    st.success(f"Email updated for record #{selected_id}.")
                    st.rerun()
        with st.expander("Delete record"):
            st.warning(f"This permanently deletes record #{selected_id} ({selected['full_name']}).")
            confirm = st.checkbox("I confirm that I want to delete this record.")
            if st.button("Delete selected record", type="secondary", disabled=not confirm):
                delete_patient(selected_id)
                st.success(f"Record #{selected_id} deleted.")
                st.rerun()
        with st.expander("View AI remarks"):
            st.write(selected["remarks"])
        
        if st.button("Drop the table",type="primary"):
            drop_table()
            st.success("Table has succesfully removed")
            st.rerun()
            

st.sidebar.divider()
st.sidebar.caption("Storage: local SQLite database")
st.sidebar.caption("AI provider: OpenAI-compatible Chat Completions API")
