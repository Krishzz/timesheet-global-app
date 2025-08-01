from flask import send_file, Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import csv
from io import BytesIO, StringIO
from functools import wraps
from datetime import datetime, timedelta, date
from math import ceil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timesheet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'user'  # explicitly set table name to lowercase
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'employee' or 'manager'

class Timesheet(db.Model):
    __tablename__ = 'timesheet'  # explicitly set table name to lowercase
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # must match 'user' table name
    week_start = db.Column(db.String(10), nullable=False)
    week_end = db.Column(db.String(10), nullable=False)
    regular_hours = db.Column(db.Float, nullable=False)
    overtime_hours = db.Column(db.Float, nullable=False)
    doubletime_hours = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='draft')
    submitted_by = db.Column(db.String(120), nullable=False)
    rejection_comments = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('timesheets', lazy=True))

# Decorators
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login', 'Success')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def manager_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login', 'Success')
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

    today = date.today()
    today_str = today.isoformat()

    # New default date filters: last 30 days from today
    default_end_date = today
    default_start_date = today - timedelta(days=60)  # last 60 days includes today + 59 days before

    # Get start_date and end_date from query params or use defaults
    start_date_str = request.args.get('start_date', default_start_date.isoformat())
    end_date_str = request.args.get('end_date', default_end_date.isoformat())

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_date = default_start_date

    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        end_date = default_end_date

    # Pagination params for employee timesheets
    try:
        current_page = int(request.args.get('page', 1))
        if current_page < 1:
            current_page = 1
    except ValueError:
        current_page = 1

    per_page = 10

    query = Timesheet.query.filter(
        Timesheet.submitted_by == user.username,
        Timesheet.week_start >= start_date.isoformat(),
        Timesheet.week_end <= end_date.isoformat()
    ).order_by(Timesheet.week_start.desc())

    total = query.count()
    total_pages = ceil(total / per_page)

    timesheets = query.offset((current_page - 1) * per_page).limit(per_page).all()

    return render_template(
        'index.html',
        timesheets=timesheets,
        default_start_date=start_date.isoformat(),
        default_end_date=end_date.isoformat(),
        current_page=current_page,
        total_pages=total_pages,
        today=today_str  # for max date in inputs
    )

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
        user_id=user.id,
        week_start=week_start,
        week_end=week_end,
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
        doubletime_hours=doubletime_hours,
        status='draft',
        submitted_by=user.username,
        rejection_comments=''
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
        ts.rejection_comments = None  # Clear rejection comments on edit
        db.session.commit()
        flash('Timesheet updated', 'success')
        return redirect(url_for('index'))

    return render_template('edit_timesheet.html', ts=ts)

@app.route('/submit_timesheet/<int:ts_id>', methods=['POST'])
@login_required
def submit_timesheet(ts_id):
    print(f"Submitting timesheet {ts_id}")
    user = User.query.get(session['user_id'])
    ts = Timesheet.query.get_or_404(ts_id)
    if ts.submitted_by != user.username:
        flash('Not allowed to submit this timesheet', 'danger')
        return redirect(url_for('index'))
    if ts.status == 'submitted':
        flash('Timesheet already submitted', 'warning')
        return redirect(url_for('index'))
    ts.status = 'submitted'
    ts.rejection_comments = None  # Clear rejection comments on submit
    db.session.commit()
    flash('Timesheet submitted for approval', 'success')
    return redirect(url_for('index'))

@app.route('/delete_timesheet/<int:ts_id>', methods=['POST'])
@login_required
def delete_timesheet(ts_id):
    user = User.query.get(session['user_id'])
    ts = Timesheet.query.get_or_404(ts_id)
    timesheet = Timesheet.query.get(ts_id)
    # Prevent editing if not owner or status is submitted or approved
    if ts.submitted_by != user.username or ts.status in ['approved', 'submitted']:
        flash('Not allowed to delete this timesheet since it has been submitted for review', 'danger')
        return redirect(url_for('index'))
    if not timesheet:
        flash("Timesheet record not found.", "danger")
        return redirect(url_for('index'))

    db.session.delete(timesheet)  # delete the actual mapped object
    db.session.commit()
    flash("Timesheet deleted successfully.", "success")
    return redirect(url_for('index'))

# Manager views
@app.route('/manager')
@manager_required
def manager_dashboard():
    # Pending approval timesheets: status='submitted'
    pending_timesheets = Timesheet.query.filter_by(status='submitted').order_by(Timesheet.week_start.desc()).all()

    # Default date filters for history: current month start and end
    today = date.today()
    default_end_date = today
    default_start_date = today - timedelta(days=60)  # last 60 days includes today + 59 days before

    # Get start_date and end_date from query params or use defaults
    start_date_str = request.args.get('start_date', default_start_date.isoformat())
    end_date_str = request.args.get('end_date', default_end_date.isoformat())
    print(f"Start date: {start_date_str}, End date: {end_date_str}")

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        start_date = default_start_date

    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        end_date = default_end_date

    # Pagination params for history list
    try:
        current_page = int(request.args.get('page', 1))
        if current_page < 1:
            current_page = 1
    except ValueError:
        current_page = 1

    per_page = 10  # items per page for pagination

    # Query for history timesheets: status in approved, submitted, rejected
    history_query = Timesheet.query.filter(
        Timesheet.status.in_(['approved', 'rejected']),
        Timesheet.week_start >= start_date.isoformat(),
        Timesheet.week_end <= end_date.isoformat()
    ).order_by(Timesheet.week_start.desc())

    total_history = history_query.count()
    total_pages = ceil(total_history / per_page)

    history_timesheets = history_query.offset((current_page - 1) * per_page).limit(per_page).all()

    return render_template(
        'manager_dashboard.html',
        timesheets=pending_timesheets,
        history_timesheets=history_timesheets,
        default_start_date=start_date.isoformat(),
        default_end_date=end_date.isoformat(),
        current_page=current_page,
        total_pages=total_pages
    )

@app.route('/manager/approve/<int:ts_id>', methods=['POST'])
@manager_required
def manager_approve(ts_id):
    ts = Timesheet.query.get_or_404(ts_id)
    ts.status = 'approved'
    ts.rejection_comments = None
    db.session.commit()
    flash(f'Timesheet for {ts.submitted_by} approved', 'success')
    return redirect(url_for('manager_dashboard'))

@app.route('/manager/reject/<int:ts_id>', methods=['POST'])
@manager_required
def manager_reject(ts_id):
    ts = Timesheet.query.get_or_404(ts_id)
    rejection_comments = request.form.get('rejection_comments', '').strip()
    if not rejection_comments:
        flash('Rejection comments are required.', 'danger')
        return redirect(url_for('manager_dashboard'))

    ts.status = 'rejected'
    ts.rejection_comments = rejection_comments
    db.session.commit()
    flash(f'Timesheet for {ts.submitted_by} rejected with comments.', 'danger')
    return redirect(url_for('manager_dashboard'))

@app.route('/export_timesheets')
@login_required
def export_timesheets():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        today = datetime.today()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    user = User.query.get(session['user_id'])
    status_filter = ['approved', 'rejected']
    if user.role == 'employee':
        status_filter.append('submitted')
    timesheets = Timesheet.query.filter(
        Timesheet.status.in_(status_filter),
        Timesheet.week_start >= start_date,
        Timesheet.week_end <= end_date
    ).all()

    proxy = StringIO()
    writer = csv.writer(proxy)
    writer.writerow(['Employee', 'Week Start', 'Week End', 'Regular Hours', 'Overtime Hours', 'Double Time Hours', 'Status', 'Comments', 'Rejection Comments'])
    for ts in timesheets:
        writer.writerow([
            ts.user.username,
            ts.week_start,
            ts.week_end,
            ts.regular_hours,
            ts.overtime_hours,
            ts.doubletime_hours,
            ts.status,
            ts.rejection_comments or ''
        ])

    mem = BytesIO()
    mem.write(proxy.getvalue().encode('utf-8'))
    mem.seek(0)
    proxy.close()

    return send_file(mem,
                     mimetype='text/csv',
                     download_name='timesheet_history.csv',
                     as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
