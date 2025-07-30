from datetime import datetime, timedelta
from app import db, Timesheet, app  # Import app here

def get_week_end(week_start_str):
    week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
    week_end = week_start + timedelta(days=4)  # Friday
    return week_end.strftime("%Y-%m-%d")

def create_or_update_timesheet(week_start, regular_hours, overtime_hours, doubletime_hours, submitted_by):
    week_end = get_week_end(week_start)
    ts = Timesheet.query.filter_by(week_start=week_start, submitted_by=submitted_by).first()
    if ts:
        ts.regular_hours = regular_hours
        ts.overtime_hours = overtime_hours
        ts.doubletime_hours = doubletime_hours
        ts.week_end = week_end
        print(f"Updated timesheet for {submitted_by} week starting {week_start}")
    else:
        ts = Timesheet(
            week_start=week_start,
            week_end=week_end,
            regular_hours=regular_hours,
            overtime_hours=overtime_hours,
            doubletime_hours=doubletime_hours,
            status='draft',
            submitted_by=submitted_by
        )
        db.session.add(ts)
        print(f"Created new timesheet for {submitted_by} week starting {week_start}")
    db.session.commit()

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 6:
        print("Usage: python create_timesheet.py <week_start YYYY-MM-DD> <regular_hours> <overtime_hours> <doubletime_hours> <submitted_by>")
        sys.exit(1)

    week_start = sys.argv[1]
    regular_hours = float(sys.argv[2])
    overtime_hours = float(sys.argv[3])
    doubletime_hours = float(sys.argv[4])
    submitted_by = sys.argv[5]

    with app.app_context():
        create_or_update_timesheet(week_start, regular_hours, overtime_hours, doubletime_hours, submitted_by)
