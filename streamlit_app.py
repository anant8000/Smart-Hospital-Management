import sqlite3
from pathlib import Path
from datetime import date, datetime

import streamlit as st

st.set_page_config(page_title="Smart Hospital Management", page_icon="🏥", layout="wide")

# Streamlit Cloud's local filesystem is temporary. This uses hospital.db beside this file
# when present, otherwise it creates a new local database for the app.
DB_PATH = Path(__file__).with_name("hospital.db")


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            charge_per_day REAL NOT NULL,
            status TEXT DEFAULT 'Available'
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_name TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT DEFAULT 'Scheduled',
            reason TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS admissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            admission_date TEXT NOT NULL,
            discharge_date TEXT,
            diagnosis TEXT,
            status TEXT DEFAULT 'Admitted',
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY(room_id) REFERENCES rooms(id)
        );
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            admission_id INTEGER,
            doctor_fee REAL DEFAULT 0,
            room_charges REAL DEFAULT 0,
            medicine_charges REAL DEFAULT 0,
            other_charges REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Unpaid',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY(admission_id) REFERENCES admissions(id) ON DELETE SET NULL
        );
        """)
        # Seed room options only when the rooms table is empty.
        if con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO rooms (room_number, room_type, charge_per_day, status) VALUES (?, ?, ?, ?)",
                [
                    ("101", "General", 50.0, "Available"),
                    ("102", "Semi-Private", 100.0, "Available"),
                    ("201-ICU", "ICU", 300.0, "Available"),
                    ("301", "Deluxe", 200.0, "Available"),
                ],
            )


def query(sql, params=()):
    with connect() as con:
        return con.execute(sql, params).fetchall()


def execute(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid


def money(value):
    return f"₹{float(value or 0):,.2f}"


init_db()

st.title("🏥 Smart Hospital Management System")
st.caption("Patient records • Appointments • Rooms • Admissions • Billing")

pages = [
    "Dashboard",
    "Patient Management",
    "Appointment Management",
    "Room Management",
    "Admission & Discharge",
    "Billing",
]
page = st.sidebar.radio("Navigation", pages)
st.sidebar.caption("Academic project demo. Avoid entering real patient data on a public demo.")

if page == "Dashboard":
    patients = query("SELECT COUNT(*) AS n FROM patients")[0]["n"]
    appointments = query("SELECT COUNT(*) AS n FROM appointments WHERE status='Scheduled'")[0]["n"]
    admissions = query("SELECT COUNT(*) AS n FROM admissions WHERE status='Admitted'")[0]["n"]
    rooms = query("SELECT COUNT(*) AS n FROM rooms WHERE status='Available'")[0]["n"]
    revenue = query("SELECT COALESCE(SUM(total_amount),0) AS n FROM bills WHERE payment_status='Paid'")[0]["n"]
    cols = st.columns(5)
    for col, label, value in zip(cols, ["Patients", "Scheduled appointments", "Current admissions", "Available rooms", "Paid revenue"], [patients, appointments, admissions, rooms, money(revenue)]):
        col.metric(label, value)
    st.subheader("Recent patients")
    rows = query("SELECT id, name, age, gender, phone, created_at FROM patients ORDER BY id DESC LIMIT 5")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    st.subheader("Recent appointments")
    rows = query("""SELECT a.id, p.name AS patient, a.doctor_name, a.appointment_date,
                    a.appointment_time, a.status FROM appointments a
                    JOIN patients p ON p.id=a.patient_id ORDER BY a.id DESC LIMIT 5""")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)

elif page == "Patient Management":
    st.header("Patient Management")
    with st.expander("Register a patient", expanded=True):
        with st.form("add_patient", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name *")
            age = c2.number_input("Age *", min_value=0, max_value=125, value=18)
            gender = c1.selectbox("Gender *", ["Female", "Male", "Other", "Prefer not to say"])
            phone = c2.text_input("Phone number *")
            address = st.text_area("Address")
            submitted = st.form_submit_button("Register patient", type="primary")
            if submitted:
                if not name.strip() or not phone.strip():
                    st.error("Please enter the patient's name and phone number.")
                else:
                    execute("INSERT INTO patients (name, age, gender, phone, address) VALUES (?, ?, ?, ?, ?)",
                            (name.strip(), int(age), gender, phone.strip(), address.strip()))
                    st.success("Patient registered.")
                    st.rerun()
    search = st.text_input("Search patients by name or phone")
    if search:
        rows = query("SELECT * FROM patients WHERE name LIKE ? OR phone LIKE ? ORDER BY id DESC",
                     (f"%{search}%", f"%{search}%"))
    else:
        rows = query("SELECT * FROM patients ORDER BY id DESC")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    ids = [r["id"] for r in rows]
    if ids:
        with st.expander("Edit or delete a patient"):
            pid = st.selectbox("Select patient ID", ids)
            selected = query("SELECT * FROM patients WHERE id=?", (pid,))[0]
            with st.form("edit_patient"):
                n = st.text_input("Name", selected["name"])
                a = st.number_input("Age", min_value=0, max_value=125, value=int(selected["age"]))
                g_options = ["Female", "Male", "Other", "Prefer not to say"]
                g = st.selectbox("Gender", g_options, index=g_options.index(selected["gender"]) if selected["gender"] in g_options else 0)
                ph = st.text_input("Phone", selected["phone"])
                ad = st.text_area("Address", selected["address"] or "")
                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Save changes")
                delete = c2.form_submit_button("Delete patient")
                if save:
                    execute("UPDATE patients SET name=?, age=?, gender=?, phone=?, address=? WHERE id=?",
                            (n.strip(), int(a), g, ph.strip(), ad.strip(), pid))
                    st.success("Patient updated.")
                    st.rerun()
                if delete:
                    execute("DELETE FROM patients WHERE id=?", (pid,))
                    st.success("Patient deleted.")
                    st.rerun()

elif page == "Appointment Management":
    st.header("Appointment Management")
    patients = query("SELECT id, name FROM patients ORDER BY name")
    if not patients:
        st.info("Register a patient first.")
    else:
        pmap = {f'{r["name"]} (ID {r["id"]})': r["id"] for r in patients}
        with st.form("add_appointment", clear_on_submit=True):
            p_label = st.selectbox("Patient", list(pmap))
            doctor = st.text_input("Doctor name / specialty")
            appt_date = st.date_input("Appointment date", value=date.today())
            appt_time = st.time_input("Appointment time")
            reason = st.text_area("Reason for visit")
            if st.form_submit_button("Book appointment", type="primary"):
                if not doctor.strip():
                    st.error("Enter a doctor name.")
                else:
                    execute("""INSERT INTO appointments
                        (patient_id, doctor_name, appointment_date, appointment_time, status, reason)
                        VALUES (?, ?, ?, ?, 'Scheduled', ?)""",
                        (pmap[p_label], doctor.strip(), appt_date.isoformat(), appt_time.strftime("%I:%M %p"), reason.strip()))
                    st.success("Appointment booked.")
                    st.rerun()
    rows = query("""SELECT a.id, p.name AS patient, a.doctor_name, a.appointment_date,
                    a.appointment_time, a.status, a.reason FROM appointments a
                    JOIN patients p ON p.id=a.patient_id ORDER BY a.id DESC""")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    if rows:
        with st.expander("Update appointment status"):
            aid = st.selectbox("Appointment ID", [r["id"] for r in rows])
            status = st.selectbox("Status", ["Scheduled", "Completed", "Cancelled"])
            if st.button("Update status"):
                execute("UPDATE appointments SET status=? WHERE id=?", (status, aid))
                st.success("Appointment updated.")
                st.rerun()

elif page == "Room Management":
    st.header("Room Management")
    with st.expander("Add a room"):
        with st.form("add_room", clear_on_submit=True):
            number = st.text_input("Room number")
            kind = st.selectbox("Room type", ["General", "Semi-Private", "Deluxe", "ICU"])
            charge = st.number_input("Charge per day (₹)", min_value=0.0, step=50.0)
            if st.form_submit_button("Add room"):
                try:
                    if not number.strip():
                        st.error("Enter a room number.")
                    else:
                        execute("INSERT INTO rooms (room_number, room_type, charge_per_day, status) VALUES (?, ?, ?, 'Available')",
                                (number.strip(), kind, charge))
                        st.success("Room added.")
                        st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That room number already exists.")
    rows = query("SELECT * FROM rooms ORDER BY room_number")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    if rows:
        with st.expander("Update room status"):
            rid = st.selectbox("Room", [r["id"] for r in rows], format_func=lambda i: next(f'{r["room_number"]} — {r["room_type"]}' for r in rows if r["id"] == i))
            status = st.selectbox("Room status", ["Available", "Occupied", "Maintenance"])
            if st.button("Save room status"):
                execute("UPDATE rooms SET status=? WHERE id=?", (status, rid))
                st.success("Room status updated.")
                st.rerun()

elif page == "Admission & Discharge":
    st.header("Admission & Discharge")
    patients = query("SELECT id, name FROM patients ORDER BY name")
    rooms = query("SELECT id, room_number, room_type, charge_per_day FROM rooms WHERE status='Available' ORDER BY room_number")
    with st.expander("Admit a patient", expanded=True):
        if not patients:
            st.info("Register a patient before admission.")
        elif not rooms:
            st.info("No available rooms. Add a room or change a room's status.")
        else:
            pmap = {f'{r["name"]} (ID {r["id"]})': r["id"] for r in patients}
            rmap = {f'{r["room_number"]} — {r["room_type"]} ({money(r["charge_per_day"])}/day)': r["id"] for r in rooms}
            with st.form("admit_patient"):
                p_label = st.selectbox("Patient", list(pmap))
                r_label = st.selectbox("Available room", list(rmap))
                adate = st.date_input("Admission date", value=date.today())
                diagnosis = st.text_area("Diagnosis / notes")
                if st.form_submit_button("Admit patient", type="primary"):
                    room_id = rmap[r_label]
                    with connect() as con:
                        con.execute("INSERT INTO admissions (patient_id, room_id, admission_date, diagnosis, status) VALUES (?, ?, ?, ?, 'Admitted')",
                                    (pmap[p_label], room_id, adate.isoformat(), diagnosis.strip()))
                        con.execute("UPDATE rooms SET status='Occupied' WHERE id=?", (room_id,))
                        con.commit()
                    st.success("Patient admitted and room allocated.")
                    st.rerun()
    rows = query("""SELECT a.id, p.name AS patient, r.room_number, a.admission_date,
                    a.discharge_date, a.diagnosis, a.status FROM admissions a
                    JOIN patients p ON p.id=a.patient_id JOIN rooms r ON r.id=a.room_id
                    ORDER BY a.id DESC""")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    active = [r for r in rows if r["status"] == "Admitted"]
    if active:
        with st.expander("Discharge patient and generate bill"):
            amap = {f'Admission {r["id"]}: {r["patient"]} — room {r["room_number"]}': r["id"] for r in active}
            with st.form("discharge_form"):
                aid_label = st.selectbox("Admission", list(amap))
                ddate = st.date_input("Discharge date", value=date.today())
                doctor_fee = st.number_input("Doctor fee (₹)", min_value=0.0, step=100.0)
                medicine = st.number_input("Medicine charges (₹)", min_value=0.0, step=50.0)
                other = st.number_input("Other charges (₹)", min_value=0.0, step=50.0)
                if st.form_submit_button("Discharge and create bill", type="primary"):
                    aid = amap[aid_label]
                    adm = query("""SELECT a.*, r.charge_per_day FROM admissions a
                                   JOIN rooms r ON r.id=a.room_id WHERE a.id=?""", (aid,))[0]
                    days = max(1, (ddate - date.fromisoformat(adm["admission_date"])).days)
                    room_charge = days * float(adm["charge_per_day"])
                    total = float(doctor_fee) + room_charge + float(medicine) + float(other)
                    with connect() as con:
                        con.execute("UPDATE admissions SET discharge_date=?, status='Discharged' WHERE id=?",
                                    (ddate.isoformat(), aid))
                        con.execute("UPDATE rooms SET status='Available' WHERE id=?", (adm["room_id"],))
                        con.execute("""INSERT INTO bills
                            (patient_id, admission_id, doctor_fee, room_charges, medicine_charges, other_charges, total_amount, payment_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'Unpaid')""",
                            (adm["patient_id"], aid, doctor_fee, room_charge, medicine, other, total))
                        con.commit()
                    st.success(f"Discharged. Bill total: {money(total)}")
                    st.rerun()

elif page == "Billing":
    st.header("Billing")
    patients = query("SELECT id, name FROM patients ORDER BY name")
    if not patients:
        st.info("Register a patient before creating a bill.")
    else:
        pmap = {f'{r["name"]} (ID {r["id"]})': r["id"] for r in patients}
        with st.expander("Create a bill", expanded=True):
            with st.form("create_bill", clear_on_submit=True):
                p_label = st.selectbox("Patient", list(pmap))
                doctor_fee = st.number_input("Doctor fee (₹)", min_value=0.0, step=100.0)
                room_charges = st.number_input("Room charges (₹)", min_value=0.0, step=100.0)
                medicine = st.number_input("Medicine charges (₹)", min_value=0.0, step=50.0)
                other = st.number_input("Other charges (₹)", min_value=0.0, step=50.0)
                status = st.selectbox("Payment status", ["Unpaid", "Paid", "Partial"])
                total = doctor_fee + room_charges + medicine + other
                st.write(f"**Total: {money(total)}**")
                if st.form_submit_button("Create bill", type="primary"):
                    execute("""INSERT INTO bills (patient_id, doctor_fee, room_charges, medicine_charges,
                              other_charges, total_amount, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (pmap[p_label], doctor_fee, room_charges, medicine, other, total, status))
                    st.success("Bill created.")
                    st.rerun()
    rows = query("""SELECT b.id, p.name AS patient, b.doctor_fee, b.room_charges,
                    b.medicine_charges, b.other_charges, b.total_amount, b.payment_status, b.created_at
                    FROM bills b JOIN patients p ON p.id=b.patient_id ORDER BY b.id DESC""")
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    if rows:
        with st.expander("Update payment status"):
            bid = st.selectbox("Bill ID", [r["id"] for r in rows])
            status = st.selectbox("New payment status", ["Unpaid", "Paid", "Partial"])
            if st.button("Update payment"):
                execute("UPDATE bills SET payment_status=? WHERE id=?", (status, bid))
                st.success("Payment status updated.")
                st.rerun()

st.divider()
st.caption("Smart Hospital Management System • Streamlit edition")
