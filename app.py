from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'chave_secreta_demo')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agenda.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ================= MODELOS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'patient' ou 'doctor'

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos para evitar queries N+1 nos templates
    patient = db.relationship('User', foreign_keys=[patient_id], backref='patient_appointments')
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_appointments')

# ================= DECORATORS =================
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login primeiro.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def role_required(role):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if session.get('role') != role:
                flash('Acesso negado.')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ================= ROTAS =================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('patient_dashboard' if session['role'] == 'patient' else 'doctor_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe.')
            return redirect(url_for('register'))
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role=role))
        db.session.commit()
        flash('Conta criada com sucesso. Faça login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.id
            session['role'] = user.role
            flash('Login realizado!')
            return redirect(url_for('index'))
        flash('Credenciais inválidas.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado.')
    return redirect(url_for('login'))

@app.route('/patient', methods=['GET', 'POST'])
@login_required
@role_required('patient')
def patient_dashboard():
    doctors = User.query.filter_by(role='doctor').all()
    my_appointments = Appointment.query.filter_by(patient_id=session['user_id']).order_by(Appointment.date.desc()).all()

    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        date_str = request.form['date']
        reason = request.form['reason']
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            db.session.add(Appointment(patient_id=session['user_id'], doctor_id=doctor_id, date=date, reason=reason))
            db.session.commit()
            flash('Consulta solicitada com sucesso!')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao solicitar: {e}')
        return redirect(url_for('patient_dashboard'))

    return render_template('patient_dashboard.html', doctors=doctors, appointments=my_appointments)

@app.route('/doctor')
@login_required
@role_required('doctor')
def doctor_dashboard():
    doctor_id = session['user_id']
    pending = Appointment.query.filter_by(doctor_id=doctor_id, status='pending').order_by(Appointment.date).all()
    approved = Appointment.query.filter_by(doctor_id=doctor_id, status='approved').all()
    rejected = Appointment.query.filter_by(doctor_id=doctor_id, status='rejected').all()
    return render_template('doctor_dashboard.html', pending=pending, approved=approved, rejected=rejected)

@app.route('/appointment/<int:appt_id>/approve', methods=['POST'])
@login_required
@role_required('doctor')
def approve_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.status != 'pending':
        flash('Esta consulta já foi processada.')
    else:
        appt.status = 'approved'
        db.session.commit()
        flash('Consulta aprovada!')
    return redirect(url_for('doctor_dashboard'))

@app.route('/appointment/<int:appt_id>/reject', methods=['POST'])
@login_required
@role_required('doctor')
def reject_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.status != 'pending':
        flash('Esta consulta já foi processada.')
    else:
        appt.status = 'rejected'
        db.session.commit()
        flash('Consulta rejeitada.')
    return redirect(url_for('doctor_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)