from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timesheet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'manager' or 'employee'

class Timesheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    week_start = db.Column(db.String(10))
    regular_hours = db.Column(db.Float)
    overtime_hours = db.Column(db.Float)
    doubletime_hours = db.Column(db.Float)
    status = db.Column(db.String(10))  # draft, submitted, approved, rejected
    submitted_on = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'manager':
        timesheets = Timesheet.query.all()
        return render_template('manager_dashboard.html', timesheets=timesheets)
    else:
        my_sheets = Timesheet.query.filter_by(user_id=current_user.id).all()
        return render_template('employee_dashboard.html', timesheets=my_sheets)

@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_timesheet():
    if request.method == 'POST':
        ts = Timesheet(
            user_id=current_user.id,
            week_start=request.form['week_start'],
            regular_hours=request.form['regular_hours'],
            overtime_hours=request.form['overtime_hours'],
            doubletime_hours=request.form['doubletime_hours'],
            status='submitted'
        )
        db.session.add(ts)
        db.session.commit()
        flash('Timesheet submitted!')
        return redirect(url_for('dashboard'))
    return render_template('submit_timesheet.html')

@app.route('/edit/<int:ts_id>', methods=['GET', 'POST'])
@login_required
def edit_timesheet(ts_id):
    ts = Timesheet.query.get_or_404(ts_id)
    if request.method == 'POST':
        ts.week_start = request.form['week_start']
        ts.regular_hours = request.form['regular_hours']
        ts.overtime_hours = request.form['overtime_hours']
        ts.doubletime_hours = request.form['doubletime_hours']
        ts.status = 'submitted'
        db.session.commit()
        flash('Timesheet resubmitted!')
        return redirect(url_for('dashboard'))
    return render_template('submit_timesheet.html', timesheet=ts)

@app.route('/review/<int:ts_id>', methods=['GET', 'POST'])
@login_required
def review_timesheet(ts_id):
    ts = Timesheet.query.get_or_404(ts_id)
    if request.method == 'POST':
        action = request.form['action']
        ts.status = 'approved' if action == 'approve' else 'rejected'
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('review_timesheet.html', timesheet=ts)

def seed_users():
    if not User.query.filter_by(username='manager').first():
        db.session.add(User(username='manager', password='manager', role='manager'))
    if not User.query.filter_by(username='employee').first():
        db.session.add(User(username='employee', password='employee', role='employee'))
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_users()
    app.run(debug=True)
