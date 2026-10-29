import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hospital-secret-key-12345')

# Database URI configuration: supports SQLite default and MySQL via env DB_URI
# Example MySQL URI: mysql+pymysql://root:password@localhost:3306/hospital_db
db_uri = os.environ.get('DB_URI')
if not db_uri:
    db_path = os.path.join(app.root_path, 'hospital.db')
    db_uri = f"sqlite:///{db_path}"

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='patient', cascade='all, delete-orphan', lazy=True)
    admissions = db.relationship('Admission', backref='patient', cascade='all, delete-orphan', lazy=True)
    bills = db.relationship('Bill', backref='patient', cascade='all, delete-orphan', lazy=True)

class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=False)  # General, Semi-Private, Deluxe, ICU
    charge_per_day = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Available')  # Available, Occupied, Maintenance

    admissions = db.relationship('Admission', backref='room', lazy=True)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_name = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(20), nullable=False)
    appointment_time = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Scheduled')  # Scheduled, Completed, Cancelled
    reason = db.Column(db.Text, nullable=True)

class Admission(db.Model):
    __tablename__ = 'admissions'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    admission_date = db.Column(db.String(20), nullable=False)
    discharge_date = db.Column(db.String(20), nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Admitted')  # Admitted, Discharged

class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id'), nullable=True)
    doctor_fee = db.Column(db.Float, default=0.0)
    room_charges = db.Column(db.Float, default=0.0)
    medicine_charges = db.Column(db.Float, default=0.0)
    other_charges = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    payment_status = db.Column(db.String(20), default='Unpaid')  # Unpaid, Paid, Partial
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admission = db.relationship('Admission', backref='bills', lazy=True)

# Helper function to compute bill total
def calculate_bill_total(bill):
    return (bill.doctor_fee or 0.0) + (bill.room_charges or 0.0) + (bill.medicine_charges or 0.0) + (bill.other_charges or 0.0)

# Routes

@app.route('/')
def dashboard():
    stats = {
        'total_patients': Patient.query.count(),
        'total_appointments': Appointment.query.filter_by(status='Scheduled').count(),
        'total_admissions': Admission.query.filter_by(status='Admitted').count(),
        'available_rooms': Room.query.filter_by(status='Available').count(),
        'total_revenue': sum(b.total_amount for b in Bill.query.filter_by(payment_status='Paid').all()) or 0.0
    }
    recent_patients = Patient.query.order_by(Patient.id.desc()).limit(5).all()
    recent_appointments = Appointment.query.order_by(Appointment.id.desc()).limit(5).all()
    return render_template('dashboard.html', stats=stats, recent_patients=recent_patients, recent_appointments=recent_appointments)

# --- PATIENTS CRUD ---
@app.route('/patients')
def list_patients():
    query = request.args.get('q', '')
    if query:
        patients = Patient.query.filter(Patient.name.ilike(f'%{query}%') | Patient.phone.ilike(f'%{query}%')).all()
    else:
        patients = Patient.query.order_by(Patient.id.desc()).all()
    return render_template('patients/index.html', patients=patients, query=query)

@app.route('/patients/add', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        patient = Patient(name=name, age=int(age), gender=gender, phone=phone, address=address)
        db.session.add(patient)
        db.session.commit()
        flash('Patient registered successfully!', 'success')
        return redirect(url_for('list_patients'))
    return render_template('patients/add.html')

@app.route('/patients/edit/<int:id>', methods=['GET', 'POST'])
def edit_patient(id):
    patient = Patient.query.get_or_404(id)
    if request.method == 'POST':
        patient.name = request.form.get('name')
        patient.age = int(request.form.get('age'))
        patient.gender = request.form.get('gender')
        patient.phone = request.form.get('phone')
        patient.address = request.form.get('address')
        db.session.commit()
        flash('Patient details updated successfully!', 'success')
        return redirect(url_for('list_patients'))
    return render_template('patients/edit.html', patient=patient)

@app.route('/patients/delete/<int:id>', methods=['POST'])
def delete_patient(id):
    patient = Patient.query.get_or_404(id)
    db.session.delete(patient)
    db.session.commit()
    flash('Patient record deleted!', 'danger')
    return redirect(url_for('list_patients'))

# --- APPOINTMENTS CRUD ---
@app.route('/appointments')
def list_appointments():
    appointments = Appointment.query.order_by(Appointment.id.desc()).all()
    return render_template('appointments/index.html', appointments=appointments)

@app.route('/appointments/add', methods=['GET', 'POST'])
def add_appointment():
    patients = Patient.query.all()
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        doctor_name = request.form.get('doctor_name')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        reason = request.form.get('reason')
        
        appt = Appointment(patient_id=patient_id, doctor_name=doctor_name, appointment_date=appointment_date, appointment_time=appointment_time, reason=reason)
        db.session.add(appt)
        db.session.commit()
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('list_appointments'))
    return render_template('appointments/add.html', patients=patients)

@app.route('/appointments/edit/<int:id>', methods=['GET', 'POST'])
def edit_appointment(id):
    appt = Appointment.query.get_or_404(id)
    patients = Patient.query.all()
    if request.method == 'POST':
        appt.patient_id = request.form.get('patient_id')
        appt.doctor_name = request.form.get('doctor_name')
        appt.appointment_date = request.form.get('appointment_date')
        appt.appointment_time = request.form.get('appointment_time')
        appt.status = request.form.get('status')
        appt.reason = request.form.get('reason')
        db.session.commit()
        flash('Appointment updated successfully!', 'success')
        return redirect(url_for('list_appointments'))
    return render_template('appointments/edit.html', appointment=appt, patients=patients)

@app.route('/appointments/delete/<int:id>', methods=['POST'])
def delete_appointment(id):
    appt = Appointment.query.get_or_404(id)
    db.session.delete(appt)
    db.session.commit()
    flash('Appointment deleted!', 'danger')
    return redirect(url_for('list_appointments'))

# --- ROOM ALLOCATION & MANAGEMENT CRUD ---
@app.route('/rooms')
def list_rooms():
    rooms = Room.query.order_by(Room.room_number).all()
    return render_template('rooms/index.html', rooms=rooms)

@app.route('/rooms/add', methods=['GET', 'POST'])
def add_room():
    if request.method == 'POST':
        room_number = request.form.get('room_number')
        room_type = request.form.get('room_type')
        charge_per_day = float(request.form.get('charge_per_day'))
        
        room = Room(room_number=room_number, room_type=room_type, charge_per_day=charge_per_day)
        db.session.add(room)
        db.session.commit()
        flash('Room added successfully!', 'success')
        return redirect(url_for('list_rooms'))
    return render_template('rooms/add.html')

@app.route('/rooms/edit/<int:id>', methods=['GET', 'POST'])
def edit_room(id):
    room = Room.query.get_or_404(id)
    if request.method == 'POST':
        room.room_number = request.form.get('room_number')
        room.room_type = request.form.get('room_type')
        room.charge_per_day = float(request.form.get('charge_per_day'))
        room.status = request.form.get('status')
        db.session.commit()
        flash('Room updated successfully!', 'success')
        return redirect(url_for('list_rooms'))
    return render_template('rooms/edit.html', room=room)

@app.route('/rooms/delete/<int:id>', methods=['POST'])
def delete_room(id):
    room = Room.query.get_or_404(id)
    db.session.delete(room)
    db.session.commit()
    flash('Room removed!', 'danger')
    return redirect(url_for('list_rooms'))

# --- ADMISSION & DISCHARGE CRUD ---
@app.route('/admissions')
def list_admissions():
    admissions = Admission.query.order_by(Admission.id.desc()).all()
    return render_template('admissions/index.html', admissions=admissions)

@app.route('/admissions/add', methods=['GET', 'POST'])
def add_admission():
    patients = Patient.query.all()
    available_rooms = Room.query.filter_by(status='Available').all()
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        room_id = request.form.get('room_id')
        admission_date = request.form.get('admission_date')
        diagnosis = request.form.get('diagnosis')
        
        room = Room.query.get_or_404(room_id)
        room.status = 'Occupied'
        
        admission = Admission(patient_id=patient_id, room_id=room_id, admission_date=admission_date, diagnosis=diagnosis, status='Admitted')
        db.session.add(admission)
        db.session.commit()
        flash('Patient admitted & room allocated!', 'success')
        return redirect(url_for('list_admissions'))
    return render_template('admissions/add.html', patients=patients, rooms=available_rooms)

@app.route('/admissions/discharge/<int:id>', methods=['GET', 'POST'])
def discharge_patient(id):
    admission = Admission.query.get_or_404(id)
    if request.method == 'POST':
        discharge_date = request.form.get('discharge_date')
        doctor_fee = float(request.form.get('doctor_fee', 0.0))
        medicine_charges = float(request.form.get('medicine_charges', 0.0))
        other_charges = float(request.form.get('other_charges', 0.0))
        
        admission.discharge_date = discharge_date
        admission.status = 'Discharged'
        
        # Free up room
        if admission.room:
            admission.room.status = 'Available'
            
        # Calculate room charges based on days
        try:
            d1 = datetime.strptime(admission.admission_date, '%Y-%m-%d')
            d2 = datetime.strptime(discharge_date, '%Y-%m-%d')
            days = max(1, (d2 - d1).days)
        except Exception:
            days = 1
            
        room_charges = days * (admission.room.charge_per_day if admission.room else 0.0)
        total_amount = doctor_fee + room_charges + medicine_charges + other_charges
        
        bill = Bill(
            patient_id=admission.patient_id,
            admission_id=admission.id,
            doctor_fee=doctor_fee,
            room_charges=room_charges,
            medicine_charges=medicine_charges,
            other_charges=other_charges,
            total_amount=total_amount,
            payment_status='Unpaid'
        )
        
        db.session.add(bill)
        db.session.commit()
        flash('Patient discharged and invoice generated!', 'info')
        return redirect(url_for('list_bills'))
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('admissions/discharge.html', admission=admission, today=today)

@app.route('/admissions/delete/<int:id>', methods=['POST'])
def delete_admission(id):
    admission = Admission.query.get_or_404(id)
    if admission.status == 'Admitted' and admission.room:
        admission.room.status = 'Available'
    db.session.delete(admission)
    db.session.commit()
    flash('Admission record deleted!', 'danger')
    return redirect(url_for('list_admissions'))

# --- BILLING CRUD ---
@app.route('/bills')
def list_bills():
    bills = Bill.query.order_by(Bill.id.desc()).all()
    return render_template('bills/index.html', bills=bills)

@app.route('/bills/add', methods=['GET', 'POST'])
def add_bill():
    patients = Patient.query.all()
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        doctor_fee = float(request.form.get('doctor_fee', 0.0))
        room_charges = float(request.form.get('room_charges', 0.0))
        medicine_charges = float(request.form.get('medicine_charges', 0.0))
        other_charges = float(request.form.get('other_charges', 0.0))
        payment_status = request.form.get('payment_status', 'Unpaid')
        
        total_amount = doctor_fee + room_charges + medicine_charges + other_charges
        
        bill = Bill(
            patient_id=patient_id,
            doctor_fee=doctor_fee,
            room_charges=room_charges,
            medicine_charges=medicine_charges,
            other_charges=other_charges,
            total_amount=total_amount,
            payment_status=payment_status
        )
        db.session.add(bill)
        db.session.commit()
        flash('Bill created successfully!', 'success')
        return redirect(url_for('list_bills'))
    return render_template('bills/add.html', patients=patients)

@app.route('/bills/edit/<int:id>', methods=['GET', 'POST'])
def edit_bill(id):
    bill = Bill.query.get_or_404(id)
    patients = Patient.query.all()
    if request.method == 'POST':
        bill.doctor_fee = float(request.form.get('doctor_fee', 0.0))
        bill.room_charges = float(request.form.get('room_charges', 0.0))
        bill.medicine_charges = float(request.form.get('medicine_charges', 0.0))
        bill.other_charges = float(request.form.get('other_charges', 0.0))
        bill.payment_status = request.form.get('payment_status')
        bill.total_amount = calculate_bill_total(bill)
        db.session.commit()
        flash('Bill updated successfully!', 'success')
        return redirect(url_for('list_bills'))
    return render_template('bills/edit.html', bill=bill, patients=patients)

@app.route('/bills/view/<int:id>')
def view_bill(id):
    bill = Bill.query.get_or_404(id)
    return render_template('bills/view.html', bill=bill)

@app.route('/bills/delete/<int:id>', methods=['POST'])
def delete_bill(id):
    bill = Bill.query.get_or_404(id)
    db.session.delete(bill)
    db.session.commit()
    flash('Bill record deleted!', 'danger')
    return redirect(url_for('list_bills'))

# CLI command / Init function for sample seed data
def init_sample_data():
    with app.app_context():
        db.create_all()
        if Patient.query.count() == 0:
            # Seed Rooms
            r1 = Room(room_number='101', room_type='General', charge_per_day=50.0, status='Occupied')
            r2 = Room(room_number='102', room_type='Semi-Private', charge_per_day=100.0, status='Available')
            r3 = Room(room_number='201-ICU', room_type='ICU', charge_per_day=300.0, status='Available')
            r4 = Room(room_number='301', room_type='Deluxe', charge_per_day=200.0, status='Available')
            db.session.add_all([r1, r2, r3, r4])
            db.session.commit()

            # Seed Patients
            p1 = Patient(name='John Doe', age=45, gender='Male', phone='555-0192', address='123 Maple St, Springfield')
            p2 = Patient(name='Jane Smith', age=32, gender='Female', phone='555-0184', address='456 Oak Ave, Metropolis')
            p3 = Patient(name='Robert Johnson', age=61, gender='Male', phone='555-0391', address='789 Pine Rd, Gotham')
            db.session.add_all([p1, p2, p3])
            db.session.commit()

            # Seed Appointment
            apt1 = Appointment(patient_id=p1.id, doctor_name='Dr. Sarah Connor (Cardiology)', appointment_date='2026-09-25', appointment_time='10:30 AM', status='Scheduled', reason='Routine checkup & ECG')
            apt2 = Appointment(patient_id=p2.id, doctor_name='Dr. Gregory House (Diagnostics)', appointment_date='2026-09-26', appointment_time='02:00 PM', status='Scheduled', reason='Persistent fever')
            db.session.add_all([apt1, apt2])

            # Seed Admission
            adm1 = Admission(patient_id=p1.id, room_id=r1.id, admission_date='2026-09-20', diagnosis='Chest pain monitoring', status='Admitted')
            db.session.add(adm1)
            db.session.commit()

            # Seed Bill
            b1 = Bill(patient_id=p2.id, doctor_fee=150.0, room_charges=0.0, medicine_charges=45.5, other_charges=20.0, total_amount=215.5, payment_status='Paid')
            db.session.add(b1)
            db.session.commit()

if __name__ == '__main__':
    init_sample_data()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
