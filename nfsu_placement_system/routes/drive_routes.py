"""
Recruitment Drive & Attendance Management Routes
Tracks company recruitment drives, category classification, round attendance,
and absenteeism penalties (exclusion from subsequent 3 drives).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from database import query_db, execute_db, execute_insert
from security import (
    login_required, role_required, get_current_user,
    log_audit_event, check_recruiter_scope
)
from policy_engine import classify_category, evaluate_eligibility
from config import COURSES, ABSENTEEISM_PENALTY_DRIVES

drive_bp = Blueprint("drive", __name__)

@drive_bp.route("/drives")
@login_required
def list_drives():
    current_user = get_current_user()
    role = current_user["role"]

    if role == "Recruiter":
        drives = query_db(
            "SELECT * FROM drives WHERE company_name = ? ORDER BY drive_date DESC",
            (current_user["recruiter_company"],)
        )
    else:
        drives = query_db("SELECT * FROM drives ORDER BY drive_date DESC")

    return render_template("drives.html", drives=drives, courses=COURSES, current_user=current_user)

@drive_bp.route("/drives/new", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer")
def create_drive():
    drive_code = request.form.get("drive_code", "").strip().upper()
    company_name = request.form.get("company_name", "").strip()
    offer_type = request.form.get("offer_type", "F")
    fte_ctc = float(request.form.get("fte_package_ctc", 0.0))
    stipend = float(request.form.get("stipend_amount", 0.0))
    stipend_period = request.form.get("stipend_period", "")
    min_cgpa = float(request.form.get("min_cgpa", 6.0))
    max_backlogs = int(request.form.get("max_backlogs", 0))
    drive_date = request.form.get("drive_date", "")
    deadline_hours = int(request.form.get("acceptance_deadline_hours", 24))
    selected_courses = request.form.getlist("eligible_courses")

    # Auto-classify Category based on NFSU CTC thresholds
    category = classify_category(fte_ctc)

    courses_str = ",".join(selected_courses) if selected_courses else ",".join(COURSES)

    drive_id = execute_insert(
        """
        INSERT INTO drives
        (drive_code, company_name, category, offer_type, stipend_amount, stipend_period, fte_package_ctc, min_cgpa, max_backlogs, eligible_courses, acceptance_deadline_hours, drive_date, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)
        """,
        (drive_code, company_name, category, offer_type, stipend, stipend_period, fte_ctc, min_cgpa, max_backlogs, courses_str, deadline_hours, drive_date, session["username"])
    )

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="DRIVE_CREATE",
        entity_type="Drive",
        entity_id=drive_code,
        details=f"Created recruitment drive {drive_code} for {company_name} (Category {category}, {offer_type}, ₹{fte_ctc} LPA)."
    )

    flash(f"Recruitment drive created: {company_name} classified as Category {category}.", "success")
    return redirect(url_for("drive.view_drive", id=drive_id))

@drive_bp.route("/drives/<int:id>")
@login_required
def view_drive(id):
    current_user = get_current_user()
    role = current_user["role"]

    drive = query_db("SELECT * FROM drives WHERE id = ?", (id,), one=True)
    if not drive:
        flash("Recruitment drive not found.", "danger")
        return redirect(url_for("drive.list_drives"))

    # Recruiter scope check
    if role == "Recruiter" and not check_recruiter_scope(current_user, drive["company_name"]):
        flash("Access Denied: You cannot view recruitment drives of another company.", "danger")
        return abort(403)

    # Attendance logs
    attendance = query_db(
        """
        SELECT a.*, s.student_name, s.placement_id, s.course
        FROM drive_attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.drive_id = ?
        ORDER BY a.recorded_at DESC
        """,
        (id,)
    )

    # Evaluate candidate roster eligibility
    students = query_db("SELECT * FROM students WHERE is_archived = 0 ORDER BY course, placement_id")
    candidates_with_status = []

    for s in students:
        s_offers = query_db("SELECT * FROM offers WHERE student_id = ?", (s["id"],))
        s_exceptions = query_db("SELECT * FROM policy_exceptions WHERE student_id = ? AND status = 'Approved'", (s["id"],))
        
        evaluation = evaluate_eligibility(
            student=dict(s),
            drive=dict(drive),
            existing_offers=[dict(o) for o in s_offers],
            exceptions=[dict(e) for e in s_exceptions]
        )
        
        candidates_with_status.append({
            "student": s,
            "evaluation": evaluation
        })

    # Offers issued in this drive
    drive_offers = query_db(
        """
        SELECT o.*, s.student_name, s.placement_id, s.course
        FROM offers o
        JOIN students s ON o.student_id = s.id
        WHERE o.drive_id = ?
        ORDER BY o.offer_date DESC
        """,
        (id,)
    )

    return render_template(
        "drive_detail.html",
        drive=drive,
        attendance=attendance,
        candidates=candidates_with_status,
        drive_offers=drive_offers,
        current_user=current_user
    )

@drive_bp.route("/drives/<int:id>/attendance", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer")
def record_attendance(id):
    student_id = int(request.form.get("student_id"))
    activity = request.form.get("activity_type")
    att_status = request.form.get("attendance_status")
    remarks = request.form.get("remarks", "").strip()

    student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)
    drive = query_db("SELECT * FROM drives WHERE id = ?", (id,), one=True)

    execute_insert(
        """
        INSERT INTO drive_attendance 
        (drive_id, student_id, activity_type, attendance_status, remarks, recorded_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (id, student_id, activity, att_status, remarks, session["username"])
    )

    # Policy Enforcement: If unexcused absence, apply 3-drive penalty exclusion
    if att_status == "Absent":
        new_count = student["absenteeism_count"] + 1
        execute_db(
            """
            UPDATE students 
            SET absenteeism_count = ?, absenteeism_penalty_drives_remaining = ?
            WHERE id = ?
            """,
            (new_count, ABSENTEEISM_PENALTY_DRIVES, student_id)
        )
        log_audit_event(
            actor_username=session["username"],
            actor_role=session["role"],
            action="ABSENTEEISM_PENALTY_APPLIED",
            entity_type="Student",
            entity_id=student["placement_id"],
            details=f"Unexcused absenteeism recorded in {drive['company_name']} ({activity}). Applied 3-drive exclusion penalty."
        )
        flash(f"Absenteeism recorded for {student['student_name']}. Penalized with exclusion from next 3 drives under Section 3.2.", "warning")
    else:
        log_audit_event(
            actor_username=session["username"],
            actor_role=session["role"],
            action="ATTENDANCE_RECORDED",
            entity_type="Attendance",
            entity_id=student["placement_id"],
            details=f"Recorded attendance '{att_status}' for {student['student_name']} in {drive['company_name']} ({activity})."
        )
        flash("Attendance record updated.", "success")

    return redirect(url_for("drive.view_drive", id=id))
