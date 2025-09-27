
Activity Point Management System
This is a Flask-based web application designed to manage and track student activity points. The system provides different dashboards for students, faculty, and the Head of Department (HOD) to streamline the process of submitting, approving, and reporting on student activities.

Features
User Authentication: Secure login and signup for three roles: Student, Faculty, and HOD.

Student Dashboard:

Submit activities with proof (e.g., certificate links).

View recent submissions and their status (pending, approved, rejected).

Track total approved points and progress towards a required points goal.

Faculty Dashboard:

View and manage pending activity submissions for their assigned department and batch.

Approve or reject submissions and award points.

View and generate student reports with filtering options.

HOD Dashboard:

Get a high-level overview of activity points for the entire department.

View real-time statistics on total and approved activities per semester.

Access detailed reports on approved activities, including student, activity, points, and approving faculty.

Reporting:

Generate downloadable reports in PDF and Excel formats.

Filter reports by student, activity type, and date range.

Database: Uses SQLite for data storage, managed with SQLAlchemy.
