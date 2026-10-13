"""
Policy Rule Engine Interactive Simulator & Exception Management Routes
Provides interactive policy conflict checks, transparency traces ("Why allowed/blocked?"),
and administrative exception/waiver workflows.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import query_db, execute_db, execute_insert
from security import (
    login_required, role_required, get_current_user, log_audit_event
)
from policy_engine import (
    classify_category, evaluate_eligibility
)
from config import COURSES

policy_bp = Blueprint("policy", __name__)

@policy_bp.route("/policy/simulator", methods=["GET", "POST"])
@login_required
def simulator():
    current_user = get_current_user()
    students = query_db("SELECT id, placement_id, student_name, course, cgpa, active_backlogs, registration_status, eligibility_status, placement_status FROM students WHERE is_archived = 0 ORDER BY student_name")
    drives = query_db("SELECT id, drive_code, company_name, category, offer_type, fte_package_ctc, stipend_amount, min_cgpa, max_backlogs FROM drives WHERE status = 'Active'")

    selected_student_id = request.values.get("student_id")
    selected_drive_id = request.values.get("drive_id")
    
    evaluation = None
    target_student = None
    target_drive = None

    if selected_student_id:
        target_student = query_db("SELECT * FROM students WHERE id = ?", (selected_student_id,), one=True)
        
        # Build target drive object either from selected drive or custom simulation inputs
        if selected_drive_id and selected_drive_id != "custom":
            db_drive = query_db("SELECT * FROM drives WHERE id = ?", (selected_drive_id,), one=True)
            if db_drive:
                target_drive = dict(db_drive)
        else:
            # Custom simulation inputs
            c_name = request.values.get("sim_company", "Hypothetical Recruiter")
            c_ctc = float(request.values.get("sim_ctc", 10.0))
            c_type = request.values.get("sim_offer_type", "F")
            c_min_cgpa = float(request.values.get("sim_min_cgpa", 6.5))
            c_max_backlogs = int(request.values.get("sim_max_backlogs", 0))
            c_category = classify_category(c_ctc)

            target_drive = {
                "id": 0,
                "drive_code": "SIM-TEST",
                "company_name": c_name,
                "category": c_category,
                "offer_type": c_type,
                "fte_package_ctc": c_ctc,
                "stipend_amount": 0.0,
                "min_cgpa": c_min_cgpa,
                "max_backlogs": c_max_backlogs,
                "eligible_courses": ",".join(COURSES)
            }

        if target_student and target_drive:
            existing_offers = query_db("SELECT * FROM offers WHERE student_id = ?", (selected_student_id,))
            exceptions = query_db("SELECT * FROM policy_exceptions WHERE student_id = ? AND status = 'Approved'", (selected_student_id,))

            evaluation = evaluate_eligibility(
                student=dict(target_student),
                drive=target_drive,
                existing_offers=[dict(o) for o in existing_offers],
                exceptions=[dict(e) for e in exceptions]
            )

    return render_template(
        "policy_checker.html",
        students=students,
        drives=drives,
        selected_student_id=int(selected_student_id) if selected_student_id else None,
        selected_drive_id=selected_drive_id,
        target_student=target_student,
        target_drive=target_drive,
        evaluation=evaluation,
        current_user=current_user
    )

@policy_bp.route("/api/policy/check", methods=["POST"])
@login_required
def api_policy_check():
    data = request.get_json() or {}
    student_id = data.get("student_id")
    drive_id = data.get("drive_id")

    student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)
    drive = query_db("SELECT * FROM drives WHERE id = ?", (drive_id,), one=True)

    if not student or not drive:
        return jsonify({"error": "Student or Drive not found"}), 404

    existing_offers = query_db("SELECT * FROM offers WHERE student_id = ?", (student_id,))
    exceptions = query_db("SELECT * FROM policy_exceptions WHERE student_id = ? AND status = 'Approved'", (student_id,))

    res = evaluate_eligibility(
        student=dict(student),
        drive=dict(drive),
        existing_offers=[dict(o) for o in existing_offers],
        exceptions=[dict(e) for e in exceptions]
    )
    return jsonify(res)

@policy_bp.route("/policy/exceptions", methods=["GET", "POST"])
@login_required
@role_required("Placement Administrator")
def manage_exceptions():
    """Administrative override manager for absenteeism waivers, switching waivers, etc."""
    if request.method == "POST":
        student_id = int(request.form.get("student_id"))
        exception_type = request.form.get("exception_type")
        justification = request.form.get("justification", "").strip()

        student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)

        execute_insert(
            """
            INSERT INTO policy_exceptions 
            (student_id, exception_type, justification, status, approved_by)
            VALUES (?, ?, ?, 'Approved', ?)
            """,
            (student_id, exception_type, justification, session["username"])
        )

        # If Absenteeism Waiver, clear or reset penalty drives
        if exception_type == "Absenteeism Waiver":
            execute_db("UPDATE students SET absenteeism_penalty_drives_remaining = 0 WHERE id = ?", (student_id,))

        log_audit_event(
            actor_username=session["username"],
            actor_role=session["role"],
            action="POLICY_EXCEPTION_GRANTED",
            entity_type="PolicyException",
            entity_id=student["placement_id"],
            details=f"Granted '{exception_type}' to {student['student_name']} ({student['placement_id']}). Justification: {justification}"
        )

        flash(f"Policy exception '{exception_type}' approved for {student['student_name']}.", "success")
        return redirect(url_for("policy.manage_exceptions"))

    exceptions = query_db(
        """
        SELECT e.*, s.student_name, s.placement_id, s.course 
        FROM policy_exceptions e
        JOIN students s ON e.student_id = s.id
        ORDER BY e.approved_at DESC
        """
    )
    students = query_db("SELECT id, placement_id, student_name, course FROM students WHERE is_archived = 0 ORDER BY student_name")
    current_user = get_current_user()

    return render_template("policy_exceptions.html", exceptions=exceptions, students=students, current_user=current_user)
