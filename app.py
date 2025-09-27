import my
import pdfkit
import pandas as pd
import os
import my
from flask import Flask, render_template, request, url_for, session, redirect, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import  LoginManager,UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
from sqlalchemy.orm import aliased  # Add this import at the top
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import case, func, Integer

db = SQLAlchemy()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.config["SECRET_KEY"]="macxx"
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# User Model (For Students, Faculty, and HODs)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('Student', 'Faculty', 'HOD'), nullable=False)
    department = db.Column(db.String(100), nullable=False)

    # Student-specific
    student_id = db.Column(db.String(50), unique=True, nullable=True)
    batch = db.Column(db.String(10), nullable=True)  # Example: '2022-2026'

    # Faculty-specific
    faculty_id = db.Column(db.String(50), unique=True, nullable=True)
    incharge_batch = db.Column(db.String(10), nullable=True)  # Faculty batch in charge

    # HOD-specific
    hod_id = db.Column(db.String(50), unique=True, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)  # Add this new field

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Activity Model (List of predefined activities)
class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)  # e.g., Technical, Sports, Cultural
    max_points = db.Column(db.Integer, nullable=False)  # Faculty can set max points
    description = db.Column(db.Text, nullable=True)

# Submission Model (Tracks student submissions)
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('user.student_id'), nullable=False)  # Ensure Foreign Key
    activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=False)  # Ensure Foreign Key
    proof = db.Column(db.String(255), nullable=False)  # File path for proof document
    points_requested = db.Column(db.Integer, nullable=False)
    activity_date = db.Column(db.Date, nullable=False)  # Add this
    duration = db.Column(db.Integer, nullable=False)  # Add this
    status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending')
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Faculty who approved/rejected
    comments = db.Column(db.Text, nullable=True)

    student = db.relationship('User', foreign_keys=[student_id])
    faculty = db.relationship('User', foreign_keys=[faculty_id])
    activity = db.relationship('Activity')

# Approval Model (Faculty's actions on submissions)
class Approval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.Enum('approved', 'rejected'), nullable=False)
    points_awarded = db.Column(db.Integer, nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    date_approved = db.Column(db.DateTime, default=datetime.utcnow)

    submission = db.relationship('Submission', backref='approvals')
    faculty = db.relationship('User')

# Report Model (For generating reports)
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_points = db.Column(db.Integer, nullable=False)
    report_file = db.Column(db.String(255), nullable=True)  # PDF file path if needed
    date_generated = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User')


def seed_activities():
    if Activity.query.count() == 0:  # Check if activities exist
        activities = [
            Activity(id=1, name="Hackathons", category="Technical", max_points=10),
            Activity(id=2, name="Coding Competitions", category="Technical", max_points=8),
            Activity(id=3, name="Workshops & Seminars", category="Technical", max_points=6),
            Activity(id=4, name="Research Paper Presentation", category="Technical", max_points=12),
            Activity(id=5, name="Technical Project Submission", category="Technical", max_points=10),

            Activity(id=6, name="Intercollege Sports Meet", category="Sports", max_points=8),
            Activity(id=7, name="University Level Sports", category="Sports", max_points=10),
            Activity(id=8, name="Intramural Competitions", category="Sports", max_points=6),
            Activity(id=9, name="Marathon / Cycling Events", category="Sports", max_points=5),

            Activity(id=10, name="Dance Competitions", category="Cultural", max_points=6),
            Activity(id=11, name="Music & Singing Events", category="Cultural", max_points=6),
            Activity(id=12, name="Drama & Theatre Performances", category="Cultural", max_points=8),
            Activity(id=13, name="Photography & Short Film Contests", category="Cultural", max_points=5),

            Activity(id=14, name="Social Service / NSS Activities", category="Other", max_points=8),
            Activity(id=15, name="Entrepreneurship / Startups", category="Other", max_points=12),
            Activity(id=16, name="Public Speaking / Debate", category="Other", max_points=7),
            Activity(id=17, name="Volunteering & Leadership Activities", category="Other", max_points=6)
        ]

        db.session.bulk_save_objects(activities)
        db.session.commit()
        print("Activities Seeded Successfully!")

with app.app_context():
    db.create_all()  # Create tables first
    seed_activities()  # Now seed data


def get_current_semester(batch, activity_date=None):
    if not activity_date:
        activity_date = datetime.now().date()
    if not batch or "-" not in batch:
        return "Unknown"

    try:
        batch_start = int(batch.split("-")[0])
        activity_year = activity_date.year
        year_diff = activity_year - batch_start

        if year_diff < 0 or year_diff >= 4:
            return "Completed"

        semester = (year_diff * 2) + (1 if activity_date.month >= 7 else 0)
        return f"S{semester}"

    except ValueError:
        return "Unknown"

def get_current_semester_type():
    # Odd semesters: July-Dec (S1, S3, S5, S7)
    # Even semesters: Jan-Jun (S2, S4, S6, S8)
    current_month = datetime.now().month
    return 'odd' if 7 <= current_month <= 12 else 'even'

def get_semester_range(semester_type):
    return [1, 3, 5, 7] if semester_type == 'odd' else [2, 4, 6, 8]

def get_academic_year(semester_str):
    try:
        # Extract semester number (e.g., "S3" → 3)
        semester = int(semester_str[1:])
        # Year = ceil(semester / 2)
        return (semester + 1) // 2
    except:
        return "Unknown"

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/guidelines')
def guidelines():
    return render_template('guidelines.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            user.last_login = datetime.utcnow()  # Add this line
            db.session.commit()  # Add this line
            login_user(user)

            if user.role == "Student":
                return redirect(url_for('student_dashboard'))
            elif user.role == "Faculty":
                return redirect(url_for('faculty_dashboard'))
            elif user.role == "HOD":
                return redirect(url_for('hod_dashboard'))
        else:
            flash("Invalid credentials. Try again.", "danger")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        department = request.form.get('dept')
        student_id = request.form.get('stdid') if role == "Student" else None  # Get Student ID only for Students
        batch = request.form.get('batch') if role == "Student" else None
        faculty_id = request.form.get('faculty_id') if role == "Faculty" else None
        incharge_batch = request.form.get('incharge_batch') if role == "Faculty" else None
        hod_id = request.form.get('hod_id') if role == "HOD" else None

        if role not in ['Student', 'Faculty', 'HOD']:
            return "Invalid role selected", 400

        if not name or not email or not password or not role:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for('signup'))

        if role == "Faculty" and (not department or not incharge_batch):
            flash("Faculty must select a department and incharge batch.", "danger")
            return redirect(url_for('signup'))
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered!", 400

        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            email=email,
            password_hash=hashed_password,
            role=role,
            department=department,
            student_id=student_id,
            batch=batch,
            faculty_id=faculty_id,
            incharge_batch=incharge_batch,
            hod_id=hod_id
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Signup successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/student_dashboard')
@login_required
def student_dashboard():
    submissions = Submission.query.filter_by(student_id=current_user.student_id).all()
    recent_activities = (
        Submission.query
        .filter_by(student_id=current_user.student_id)
        .order_by(Submission.date_submitted.desc())  # Sort by most recent
        .limit(5)  # Show last 5 activities
        .all()
    )
    # Calculate approved points from Approval table
    approved_points = db.session.query(db.func.sum(Approval.points_awarded)) \
                          .join(Submission, Approval.submission_id == Submission.id) \
                          .filter(Submission.student_id == current_user.student_id) \
                          .scalar() or 0

    # Define the required points threshold
    required_points = 100  # Adjust if needed
    remaining_points = max(0, required_points - approved_points)
    progress_percentage = min(100, (approved_points / required_points) * 100)  # Ensure max is 100%


    # Count submitted activities (all statuses)
    total_submitted = Submission.query.filter_by(student_id=current_user.student_id).count()

    # Count approved activities
    total_approved = Submission.query.filter_by(student_id=current_user.student_id, status='approved').count()
    current_semester = get_current_semester(current_user.batch)


    return render_template(
        'studentdash.html',
        current_semester=current_semester,
        submissions=recent_activities,
        approved_points=approved_points,
        remaining_points=remaining_points,
        progress_percentage=progress_percentage,
        total_submitted=total_submitted,
        total_approved=total_approved
    )


@app.route('/activity_submission', methods=['GET', 'POST'])
@login_required
def activity_submission():
    if request.method == 'POST':
        student_id = current_user.student_id
        activity_id = request.form['activity_id']
        activity_date = request.form.get('activity_date')  # Store for future tracking
        activity_duration = request.form.get('activity_duration')
        certificate_link = request.form.get('certificate_link')
        activity_date = datetime.strptime(request.form['activity_date'], '%Y-%m-%d').date()
        duration = request.form['activity_duration']

        new_submission = Submission(
            student_id=student_id,
            activity_id=activity_id,
            proof=certificate_link,  # Saving certificate link as proof
            points_requested=5,  # Default points, can be set dynamically later
            activity_date=activity_date,
            duration=duration,
            status='pending'
        )

        db.session.add(new_submission)
        db.session.commit()

        flash("Activity submitted successfully!", "success")
        return redirect(url_for('student_dashboard'))

    activities = Activity.query.all()
    return render_template('actsubmission.html', activities=activities)


@app.route('/faculty_dashboard')
@login_required
def faculty_dashboard():
    return render_template('facultydash.html')


@app.route('/faculty_activities')
@login_required
def faculty_activities():
    if current_user.role != "Faculty":
        return "Unauthorized", 403
    activities = Activity.query.all()



    return render_template('facactivity.html',activities=activities)


@app.route('/api/faculty/activities', methods=['GET'])
def get_activities():
    batch = request.args.get('batch')
    semester = request.args.get('semester')
    activity_type = request.args.get('activity_type')

    # Joining submission with student and activity tables
    query = (
        db.session.query(
            Submission.id,
            User.name.label("student_name"),
            User.batch,
            User.department,
            Activity.name.label("activity_name"),
            Submission.points_requested,
            Submission.status
        )
        .join(User, Submission.student_id == User.student_id)  # Join User, not Student
        .join(Activity, Submission.activity_id == Activity.id)
        .filter(User.department == current_user.department)
        .filter(Submission.status == "pending")
    )

    # Apply filters if provided
    if batch:
        query = query.filter(Student.batch == batch)
    if semester:
        query = query.filter(Student.semester == semester)
    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)

    activities = query.all()

    # Convert the result to JSON format
    activity_list = [{
        "student_name": activity.student_name,
        "batch": activity.batch,
        "semester": activity.semester,
        "activity_type": activity.activity_type,
        "approved_points": activity.approved_points
    } for activity in activities]

    return jsonify(activity_list)


@app.route('/api/faculty/filters', methods=['GET'])
def get_filter_options():
    batches = db.session.query(Student.batch).distinct().all()
    semesters = db.session.query(Student.semester).distinct().all()
    activity_types = db.session.query(Activity.activity_type).distinct().all()

    return jsonify({
        "batches": [batch[0] for batch in batches],
        "semesters": [semester[0] for semester in semesters],
        "activity_types": [activity[0] for activity in activity_types]
    })

@app.route('/faculty_reports')
@login_required
def faculty_reports():
    activities = Activity.query.all()  # Fetch all activities again for reports
    return render_template('facreport.html', activities=activities)


@app.route('/students')
@login_required
def students():
    student_list = User.query.filter_by(role='Student').all()
    return render_template('studentsfac.html', students=student_list)


# HOD Dashboard Route (Real-Time Updates)
@app.route('/hod_dashboard')
@login_required
def hod_dashboard():
    if current_user.role != "HOD":
        return redirect(url_for('login'))

    # Corrected indentation: This part runs only for HOD
    semester_type = get_current_semester_type()
    active_semesters = get_semester_range(semester_type)

    semester_data = []
    for sem in active_semesters:
        # Get students in this semester
        students_in_semester = User.query.filter(
            User.role == 'Student',
            User.department == current_user.department
        ).all()

        total_activities = 0
        approved_activities = 0

        for student in students_in_semester:
            if get_current_semester(student.batch) == f"S{sem}":
                # Count submissions
                total = Submission.query.filter_by(
                    student_id=student.student_id
                ).count()

                # Count approved
                approved = Submission.query.filter_by(
                    student_id=student.student_id,
                    status='approved'
                ).count()

                total_activities += total
                approved_activities += approved

        semester_data.append({
            'semester': sem,
            'total': total_activities,
            'approved': approved_activities
        })

    # Fetch approved activities with faculty details
    approved_activities = (
        db.session.query(Approval, Submission, User, Activity)
        .join(Submission, Approval.submission_id == Submission.id)
        .join(User, Submission.student_id == User.student_id)
        .join(Activity, Submission.activity_id == Activity.id)
        .filter(User.department == current_user.department)
        .all()
    )

    activity_list = []
    for approval, submission, user, activity in approved_activities:
        semester = get_current_semester(user.batch, submission.activity_date)
        year = get_academic_year(semester) if semester != "Unknown" else "Unknown"

        activity_list.append({
            "student_name": user.name,
            "batch": user.batch,
            "semester": semester,
            "year": year,
            "activity_name": activity.name,
            "category": activity.category,
            "points": approval.points_awarded,
            "faculty": approval.faculty.name
        })

    return render_template(
        'hod.html',
        semester_data=semester_data,  # Pass semester_data to template
        activity_list=activity_list
    )

    # Fetch all unique batch years from the database
    batches = (
        db.session.query(User.batch)
        .join(Submission, Submission.student_id == User.id)
        .filter(User.department == current_user.department)
        .distinct()
        .all()
    )
    batches = [batch[0] for batch in batches]  # Extracting batch values from tuples

    for batch in batches:
        semester = get_current_semester(batch)
        if semester != "Completed" and semester != "Unknown":  # Ignore completed/unknown students
            count = (
                db.session.query(db.func.sum(Submission.activities_count))
                .join(User, Submission.student_id == User.id)
                .filter(User.batch == batch)  # Fetch based on User's batch
                .scalar()
            )
            semester_activity_counts[semester] = semester_activity_counts.get(semester, 0) + (count if count else 0)


    return render_template(
        'hod.html',
        hod_name=session['hod_name'],
        hod_department=session['hod_department'],
        hod_email=session['hod_email'],
        activity_list=activity_list,
        semester_activity_counts=semester_activity_counts
    )




@app.route('/get_semester_activities/<int:semester>')
@login_required
def get_semester_activities(semester):
    if current_user.role != "HOD":
        return jsonify({"error": "Unauthorized"}), 403

    try:
        Faculty = aliased(User)  # Create alias for faculty user

        activities = (
            db.session.query(
                User.name.label("student_name"),
                Activity.name.label("activity_name"),
                Approval.points_awarded,
                Faculty.name.label("faculty_name"),  # Get faculty name from aliased User
                Submission.activity_date
            )
            .join(Submission, User.student_id == Submission.student_id)
            .join(Approval, Approval.submission_id == Submission.id)
            .join(Activity, Submission.activity_id == Activity.id)
            .join(Faculty, Approval.faculty_id == Faculty.id)  # Join with faculty alias
            .filter(
                User.department == current_user.department,
                (datetime.now().year - func.substr(User.batch, 1, 4).cast(Integer)) * 2 + 0 <= semester,
                (datetime.now().year - func.substr(User.batch, 1, 4).cast(Integer)) * 2 + 1 >= semester
            )
            .all()
        )

        return jsonify([{
            "student_name": a.student_name,
            "activity_name": a.activity_name,
            "points_awarded": a.points_awarded,
            "faculty_name": a.faculty_name,
            "activity_date": a.activity_date.strftime('%Y-%m-%d') if a.activity_date else ""
        } for a in activities])
    except Exception as e:
        app.logger.error(f"Error fetching semester activities: {str(e)}")
        return jsonify({"error": "Failed to fetch semester details."}), 500

@app.route('/reports')
@login_required
def reports():
    activities = Activity.query.all()
    return render_template('studreports.html',activities=activities)


@app.route('/view_activities')
@login_required
def view_activities():
    return render_template('viewactivity.html')





@app.route('/generate_pdf', methods=['GET'])
@login_required
def generate_pdf():
    semester = request.args.get('semester')
    activity_id = request.args.get('activity_id')  # Fetch selected activity

    query = Submission.query.filter_by(student_id=current_user.student_id)

    if semester:
        query = query.filter(Submission.date_submitted.between(f"{semester}-01-01", f"{semester}-12-31"))

    if activity_id:
        query = query.filter_by(activity_id=activity_id)

    submissions = Submission.query \
        .join(Approval, Submission.id == Approval.submission_id) \
        .filter(Submission.student_id == current_user.student_id) \
        .all()

    # Generate PDF (Example Using HTML Template Rendering)
    rendered_html = render_template('report_template.html', submissions=submissions)
    pdf_path = "reports/activity_report.pdf"
    pdfkit.from_string(rendered_html, pdf_path)

    return send_file(pdf_path, as_attachment=True)


# Generate Excel Report with Filtering
@app.route('/generate_excel', methods=['GET'])
@login_required
def generate_excel():
    student_id = request.args.get('student_id')
    activity_type = request.args.get('activity_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Submission.query
    if student_id:
        query = query.filter_by(student_id=student_id)
    if activity_type:
        query = query.filter_by(activity_type=activity_type)
    if start_date and end_date:
        query = query.filter(Submission.date_submitted.between(start_date, end_date))

    submissions = Submission.query \
        .join(Approval, Submission.id == Approval.submission_id) \
        .filter(Submission.student_id == current_user.student_id) \
        .all()

    data = [{
        "Student Name": s.student.name,
        "Activity Type": s.activity_type,
        "Points Awarded": s.points_awarded,
        "Status": s.status,
        "Date Submitted": s.date_submitted.strftime('%Y-%m-%d')
    } for s in submissions]
    df = pd.DataFrame(data)
    excel_path = "reports/activity_report.xlsx"
    df.to_excel(excel_path, index=False)
    return send_file(excel_path, as_attachment=True)



@app.route('/get_faculty_activities', methods=['GET'])
@login_required
def get_faculty_activities():
    if current_user.role != "Faculty":
        return jsonify({"error": "Unauthorized"}), 403

    submissions = (
        Submission.query
        .join(User, Submission.student_id == User.student_id)
        .join(Activity, Submission.activity_id == Activity.id)
        .add_columns(
            User.name.label("student_name"),
            User.department.label("department"),
            User.batch.label("batch"),
            Submission.status.label("status"),
            Submission.points_requested.label("points"),
            Activity.name.label("activity_name"),
            Submission.id.label("submission_id")
        )
        .filter(User.department == current_user.department)
        .filter(User.batch == current_user.incharge_batch)
        .filter(Submission.status == "pending")
        .all()
    )

    submission_list = [
        {
            "submission_id": sub.submission_id,
            "student_name": sub.student_name,
            "department": sub.department,
            "batch": sub.batch,
            "activity_name": sub.activity_name,
            "points": sub.points,
            "status": sub.status
        }
        for sub in submissions
    ]

    return jsonify(submission_list)

@app.route('/approve_activity', methods=['POST'])
@login_required
def approve_activity():
    if current_user.role != "Faculty":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    submission_id = data.get("submission_id")
    action = data.get("action")  # 'approve' or 'reject'
    points_awarded = data.get("points_awarded")
    remarks = data.get("remarks", "")


    submission = Submission.query.get(submission_id)
    activity = Activity.query.get(submission.activity_id)

    if not submission:
        return jsonify({"error": "Submission not found"}), 404

    if action == "approve" and (not points_awarded or int(points_awarded) > activity.max_points):
        return jsonify({"error": "Invalid points"}), 400

    try:
        if action == "approve":
            # Create approval record
            approval = Approval(
                submission_id=submission.id,
                faculty_id=current_user.id,
                status='approved',
                points_awarded=points_awarded,
                remarks=remarks
            )
            db.session.add(approval)
            submission.status = 'approved'

        elif action == "reject":
            submission.status = 'rejected'

        db.session.commit()
        return jsonify({"message": "Action processed successfully!"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/get_students', methods=['GET'])
@login_required
def get_students():
    if current_user.role != "Faculty":
        return jsonify({"error": "Unauthorized"}), 403

    students = User.query.filter_by(
        role="Student",
        department=current_user.department,
        batch=current_user.incharge_batch
    ).all()

    student_list = [
        {
            "name": student.name,
            "student_id": student.student_id,
            "department": student.department,
            "batch": student.batch
        }
        for student in students
    ]

    return jsonify(student_list)

@app.route('/get_filter_data', methods=['GET'])
@login_required
def get_filter_data():
    if current_user.role != "Faculty":
        return jsonify({"error": "Unauthorized"}), 403

    # Get unique batches of students
    batches = db.session.query(User.batch).filter(User.role == "Student").distinct().all()
    batches = [b[0] for b in batches if b[0]]

    # Get unique activity categories
    activity_types = db.session.query(Activity.category).distinct().all()
    activity_types = [a[0] for a in activity_types if a[0]]

    # Generate semesters dynamically based on the current date
    current_year = datetime.now().year
    semesters = [f"S{(year - 2020) * 2 + (1 if datetime.now().month >= 7 else 0)}" for year in range(2021, current_year + 1)]

    return jsonify({
        "batches": batches,
        "semesters": semesters,
        "activity_types": activity_types
    })



@app.route('/get_reports', methods=['GET'])
@login_required
def get_reports():
    if current_user.role != "Faculty":
        return jsonify({"error": "Unauthorized"}), 403

    reports = (
        db.session.query(
            User.name.label("student_name"),
            User.department.label("department"),
            Activity.name.label("activity_name"),
            db.func.sum(Submission.points_requested).label("total_points")
        )
        .join(Submission, User.student_id == Submission.student_id)
        .join(Activity, Submission.activity_id == Activity.id)
        .filter(Submission.status == "approved")
        .group_by(User.name, User.department, Activity.name)
        .all()
    )

    report_list = [
        {
            "student_name": report.student_name,
            "department": report.department,
            "activity_name": report.activity_name,
            "total_points": report.total_points
        }
        for report in reports
    ]

    return jsonify(report_list)


with app.app_context():
    db.create_all()  # Create tables
    seed_activities()  # Populate data

if __name__ == '__main__':
    app.run(debug=True)
