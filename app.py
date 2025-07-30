from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timesheet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'employee' or 'manager'

class Timesheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.String(10), nullable=False)
    week_end = db.Column(db.String(10), nullable=False)  # NEW COLUMN
    regular_hours = db.Column(db.Float, nullable=False)
    overtime_hours = db.Column(db.Float, nullable=False)
    doubletime_hours = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='draft')
    submitted_by = db.Column(db.String(120), nullable=False)

# Decorators
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def manager_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'danger')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if user.role != 'manager':
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapped

# Routes
@app.route('/', methods=['GET'])
@login_required
def index():
    user = User.query.get(session['user_id'])
    if user.role == 'manager':
        return redirect(url_for('manager_dashboard'))
    # employee view: show their timesheets
    timesheets = Timesheet.query.filter_by(submitted_by=user.username).order_by(Timesheet.id.desc()).all()
    return render_template('index.html', timesheets=timesheets)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Logged in successfully', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/new_timesheet', methods=['POST'])
@login_required
def new_timesheet():
    user = User.query.get(session['user_id'])
    week_start = request.form['week_start']
    dt_start = datetime.strptime(week_start, '%Y-%m-%d')
    week_end = (dt_start + timedelta(days=4)).strftime('%Y-%m-%d')  # Friday

    regular_hours = float(request.form['regular_hours'])
    overtime_hours = float(request.form['overtime_hours'])
    doubletime_hours = float(request.form['doubletime_hours'])
    ts = Timesheet(
        week_start=week_start,
        week_end=week_end,
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
        doubletime_hours=doubletime_hours,
        status='draft',
        submitted_by=user.username
    )
    db.session.add(ts)
    db.session.commit()
    flash('Timesheet saved as draft', 'success')
    return redirect(url_for('index'))

@app.route('/edit_timesheet/<int:ts_id>', methods=['GET', 'POST'])
@login_required
def edit_timesheet(ts_id):
    user = User.query.get(session['user_id'])
    ts = Timesheet.query.get_or_404(ts_id)
    # Prevent editing if not owner or status is submitted or approved
    if ts.submitted_by != user.username or ts.status in ['approved', 'submitted']:
        flash('Not allowed to edit this timesheet since it has been submitted for review', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        ts.week_start = request.form['week_start']
        ts.regular_hours = float(request.form['regular_hours'])
        ts.overtime_hours = float(request.form['overtime_hours'])
        ts.doubletime_hours = float(request.form['doubletime_hours'])
        ts.status = 'draft'  # editing moves it back to draft
        db.session.commit()
        flash('Timesheet updated', 'success')
        return redirect(url_for('index'))

    return render_template('edit_timesheet.html', ts=ts)

@app.route('/submit_timesheet/<int:ts_id>', methods=['POST'])
@login_required
def submit_timesheet(ts_id):
    user = User.query.get(session['user_id'])
    ts = Timesheet.query.get_or_404(ts_id)
    if ts.submitted_by != user.username:
        flash('Not allowed to submit this timesheet', 'danger')
        return redirect(url_for('index'))
    if ts.status == 'approved':
        flash('Timesheet already approved, cannot submit', 'warning')
        return redirect(url_for('index'))
    ts.status = 'submitted'
    db.session.commit()
    flash('Timesheet submitted for approval', 'success')
    return redirect(url_for('index'))

# Manager views
@app.route('/manager')
@manager_required
def manager_dashboard():
    timesheets = Timesheet.query.filter_by(status='submitted').order_by(Timesheet.id.desc()).all()
    return render_template('manager_dashboard.html', timesheets=timesheets)

@app.route('/manager/approve/<int:ts_id>', methods=['POST'])
@manager_required
def manager_approve(ts_id):
    ts = Timesheet.query.get_or_404(ts_id)
    ts.status = 'approved'
    db.session.commit()
    flash(f'Timesheet for {ts.submitted_by} approved', 'success')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/reject/<int:ts_id>', methods=['POST'])
@manager_required
def manager_reject(ts_id):
    ts = Timesheet.query.get_or_404(ts_id)
    ts.status = 'rejected'
    db.session.commit()
    flash(f'Timesheet for {ts.submitted_by} rejected', 'danger')
    return redirect(url_for('manager_dashboard'))


if __name__ == "__main__":
    app.run()

