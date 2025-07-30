from app import app, db, User

with app.app_context():
    db.create_all()

    users = [
        User(username='employee@dewsoftware.com', password='employee@dew25', role='employee'),
        User(username='manager@dewsoftware.com', password='manager@dew26', role='manager'),
    ]

    for u in users:
        if not User.query.filter_by(username=u.username).first():
            db.session.add(u)
    db.session.commit()

    print("Database and tables created. Users added.")
