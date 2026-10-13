"""
Student Management Routes
Handles searchable student directory, course-wise filtering, CRUD operations,
placement history preservation, data masking, and controlled CSV import/export.
"""

import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, abort
from database import query_db, execute_db, execute_insert
from security import (
    login_required, role_required, get_current_user,
    mask_mobile_number, mask_email_address, log_audit_event,
    check_course_coordinator_scope, check_student_self_access
)
from config import COURSES, BATCHES

student_bp = Blueprint("student", __name__)

@student_bp.route("/students")
@login_required
def list_students():
    current_user = get_current_user()
    role = current_user["role"]

    # Security: A student cannot browse the global directory - redirect to own profile
    if role == "Student":
        if current_user["student_id"]:
            return redirect(url_for("student.view_student", id=current_user["student_id"]))
        else:
            flash("No student record linked to your user account.", "warning")
            return redirect(url_for("report.dashboard"))

    # Security: Recruiters cannot view the master university student directory
    if role == "Recruiter":
        flash("Recruiters can only access applicants within their company drives.", "warning")
        return redirect(url_for("drive.list_drives"))

    selected_course = request.args.get("course", "all")
    selected_status = request.args.get("status", "all")
    selected_reg = request.args.get("reg", "all")
    search_q = request.args.get("q", "").strip()

    # Scope enforcement for Course Coordinator
    if role == "Course Coordinator":
        selected_course = current_user["assigned_course"]

    # Build parameterized query
    conditions = ["is_archived = 0"]
    params = []

    if selected_course != "all":
        conditions.append("course = ?")
        params.append(selected_course)

    if selected_status != "all":
        conditions.append("placement_status = ?")
        params.append(selected_status)

    if selected_reg != "all":
        conditions.append("registration_status = ?")
        params.append(selected_reg)

    if search_q:
        conditions.append("(student_name LIKE ? OR placement_id LIKE ? OR email_id LIKE ?)")
        wildcard = f"%{search_q}%"
        params.extend([wildcard, wildcard, wildcard])

    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM students WHERE {where_clause} ORDER BY placement_id ASC"
    students = query_db(query, tuple(params))

    # Mask sensitive contact details according to role
    masked_students = []
    for s in students:
        s_dict = dict(s)
        s_dict["display_mobile"] = mask_mobile_number(s["mobile_number"], role)
        s_dict["display_email"] = mask_email_address(s["email_id"], role)
        masked_students.append(s_dict)

    return render_template(
        "students.html",
        students=masked_students,
        courses=COURSES,
        selected_course=selected_course,
        selected_status=selected_status,
        selected_reg=selected_reg,
        search_q=search_q,
        current_user=current_user
    )

@student_bp.route("/students/new", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer")
def create_student():
    p_id = request.form.get("placement_id", "").strip().upper()
    name = request.form.get("student_name", "").strip()
    mobile = request.form.get("mobile_number", "").strip()
    email = request.form.get("email_id", "").strip().lower()
    course = request.form.get("course", "").strip()
    batch = request.form.get("batch", "").strip()
    cgpa = float(request.form.get("cgpa", 0.0))
    backlogs = int(request.form.get("active_backlogs", 0))
    reg_status = request.form.get("registration_status", "Registered")
    elig_status = request.form.get("eligibility_status", "Eligible")

    # Validate duplicate Placement ID
    existing = query_db("SELECT id FROM students WHERE placement_id = ?", (p_id,), one=True)
    if existing:
        flash(f"Error: Placement ID '{p_id}' already exists in database.", "danger")
        return redirect(url_for("student.list_students"))

    # Validate course
    if course not in COURSES:
        flash("Invalid course programme selected.", "danger")
        return redirect(url_for("student.list_students"))

    s_id = execute_insert(
        """
        INSERT INTO students 
        (placement_id, student_name, mobile_number, email_id, course, batch, cgpa, active_backlogs, registration_status, eligibility_status, placement_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Unplaced')
        """,
        (p_id, name, mobile, email, course, batch, cgpa, backlogs, reg_status, elig_status)
    )

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="STUDENT_CREATE",
        entity_type="Student",
        entity_id=p_id,
        details=f"Created student record for {name} ({p_id}) in {course}."
    )
    flash(f"Student record created for {name} ({p_id}).", "success")
    return redirect(url_for("student.view_student", id=s_id))

@student_bp.route("/students/<int:id>")
@login_required
def view_student(id):
    current_user = get_current_user()
    role = current_user["role"]

    student = query_db("SELECT * FROM students WHERE id = ?", (id,), one=True)
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("student.list_students"))

    # Security IDOR Check: Students can ONLY view their own profile
    if role == "Student" and current_user["student_id"] != id:
        log_audit_event(
            actor_username=current_user["username"],
            actor_role=role,
            action="IDOR_ATTEMPT_BLOCKED",
            entity_type="Student",
            entity_id=str(id),
            details=f"Student {current_user['username']} attempted unauthorized access to student record #{id}."
        )
        flash("Unauthorized: You do not have permission to view other student records.", "danger")
        return render_template("error.html", error_code=403, error_message="Unauthorized Access Restricted under NFSU Security Policy."), 403

    # Security Scope Check: Course Coordinator can only view students in their assigned programme
    if role == "Course Coordinator" and not check_course_coordinator_scope(current_user, student["course"]):
        flash(f"Access restricted to your assigned programme ({current_user['assigned_course']}).", "danger")
        return render_template("error.html", error_code=403, error_message="Unauthorized Department Access."), 403

    # Preserved historical offers trail
    offers = query_db(
        "SELECT * FROM offers WHERE student_id = ? ORDER BY offer_date DESC, id DESC",
        (id,)
    )

    # Attendance history
    attendance = query_db(
        """
        SELECT a.*, d.company_name, d.drive_code 
        FROM drive_attendance a
        JOIN drives d ON a.drive_id = d.id
        WHERE a.student_id = ?
        ORDER BY a.recorded_at DESC
        """,
        (id,)
    )

    # Policy exceptions history
    exceptions = query_db(
        "SELECT * FROM policy_exceptions WHERE student_id = ? ORDER BY approved_at DESC",
        (id,)
    )

    # Privacy masking
    s_dict = dict(student)
    s_dict["display_mobile"] = mask_mobile_number(student["mobile_number"], role)
    s_dict["display_email"] = mask_email_address(student["email_id"], role)

    return render_template(
        "student_detail.html",
        student=s_dict,
        offers=offers,
        attendance=attendance,
        exceptions=exceptions,
        current_user=current_user,
        courses=COURSES,
        batches=BATCHES
    )

@student_bp.route("/students/<int:id>/edit", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer", "Course Coordinator")
def edit_student(id):
    current_user = get_current_user()
    role = current_user["role"]

    student = query_db("SELECT * FROM students WHERE id = ?", (id,), one=True)
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("student.list_students"))

    # Coordinator can only edit students in their course
    if role == "Course Coordinator" and not check_course_coordinator_scope(current_user, student["course"]):
        flash("Access Denied: You cannot modify students outside your assigned course.", "danger")
        return abort(403)

    before_state = dict(student)

    # Read editable fields
    mobile = request.form.get("mobile_number", student["mobile_number"]).strip()
    email = request.form.get("email_id", student["email_id"]).strip().lower()
    cgpa = float(request.form.get("cgpa", student["cgpa"]))
    backlogs = int(request.form.get("active_backlogs", student["active_backlogs"]))
    reg_status = request.form.get("registration_status", student["registration_status"])
    elig_status = request.form.get("eligibility_status", student["eligibility_status"])
    penalty_drives = int(request.form.get("absenteeism_penalty_drives_remaining", student["absenteeism_penalty_drives_remaining"]))

    execute_db(
        """
        UPDATE students 
        SET mobile_number = ?, email_id = ?, cgpa = ?, active_backlogs = ?,
            registration_status = ?, eligibility_status = ?, absenteeism_penalty_drives_remaining = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (mobile, email, cgpa, backlogs, reg_status, elig_status, penalty_drives, id)
    )

    after_student = query_db("SELECT * FROM students WHERE id = ?", (id,), one=True)
    after_state = dict(after_student)

    log_audit_event(
        actor_username=current_user["username"],
        actor_role=role,
        action="STUDENT_UPDATE",
        entity_type="Student",
        entity_id=student["placement_id"],
        details=f"Updated academic/status records for {student['student_name']}.",
        before_state=before_state,
        after_state=after_state
    )

    flash("Student record updated successfully.", "success")
    return redirect(url_for("student.view_student", id=id))

@student_bp.route("/students/<int:id>/archive", methods=["POST"])
@login_required
@role_required("Placement Administrator")
def archive_student(id):
    student = query_db("SELECT * FROM students WHERE id = ?", (id,), one=True)
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("student.list_students"))

    execute_db("UPDATE students SET is_archived = 1 WHERE id = ?", (id,))
    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="STUDENT_ARCHIVE",
        entity_type="Student",
        entity_id=student["placement_id"],
        details=f"Archived student record for {student['student_name']} ({student['placement_id']})."
    )
    flash(f"Student record {student['placement_id']} archived safely.", "info")
    return redirect(url_for("student.list_students"))

@student_bp.route("/students/export")
@login_required
@role_required("Placement Administrator", "Placement Officer")
def export_students():
    """Generates a secure, controlled CSV export and writes an audit event."""
    students = query_db("SELECT * FROM students WHERE is_archived = 0 ORDER BY course, placement_id")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Placement ID", "Student Name", "Mobile Number", "Email ID", "Course",
        "Batch", "CGPA", "Active Backlogs", "Registration Status", "Eligibility Status",
        "Placement Status", "Absenteeism Penalty Drives"
    ])

    for s in students:
        writer.writerow([
            s["placement_id"], s["student_name"], s["mobile_number"], s["email_id"],
            s["course"], s["batch"], s["cgpa"], s["active_backlogs"],
            s["registration_status"], s["eligibility_status"], s["placement_status"],
            s["absenteeism_penalty_drives_remaining"]
        ])

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="DATA_EXPORT",
        entity_type="Student",
        entity_id="ALL",
        details=f"Exported master student placement roster ({len(students)} records) to CSV."
    )

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=NFSU_Students_Placement_2026_27.csv"}
    )
