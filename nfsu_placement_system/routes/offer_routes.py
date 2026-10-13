"""
Recruitment & Offer Management Routes
Handles offer recording (I, F, I+F), 24h deadline tracking, PPO workflows,
NOC status, and dynamic updates to student placement status while preserving full event history.
"""

from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from database import query_db, execute_db, execute_insert
from security import (
    login_required, role_required, get_current_user, log_audit_event
)
from policy_engine import (
    classify_category, evaluate_eligibility, calculate_placement_status
)
from config import COURSES, DEFAULT_OFFER_DEADLINE_HOURS

offer_bp = Blueprint("offer", __name__)

@offer_bp.route("/offers")
@login_required
def list_offers():
    current_user = get_current_user()
    role = current_user["role"]

    selected_status = request.args.get("status", "all")
    selected_type = request.args.get("type", "all")

    query = """
        SELECT o.*, s.student_name, s.placement_id, s.course, s.cgpa
        FROM offers o
        JOIN students s ON o.student_id = s.id
        WHERE 1=1
    """
    params = []

    if role == "Recruiter":
        query += " AND o.company_name = ?"
        params.append(current_user["recruiter_company"])

    if role == "Course Coordinator":
        query += " AND s.course = ?"
        params.append(current_user["assigned_course"])

    if role == "Student":
        query += " AND o.student_id = ?"
        params.append(current_user["student_id"])

    if selected_status != "all":
        query += " AND o.offer_acceptance = ?"
        params.append(selected_status)

    if selected_type != "all":
        query += " AND o.offer_type = ?"
        params.append(selected_type)

    query += " ORDER BY o.offer_date DESC, o.id DESC"
    offers = query_db(query, tuple(params))

    # Evaluate deadline status for each offer
    processed_offers = []
    now = datetime.now()
    for o in offers:
        o_dict = dict(o)
        try:
            deadline = datetime.fromisoformat(o["deadline_at"])
            remaining = (deadline - now).total_seconds() / 3600.0
            o_dict["hours_remaining"] = round(remaining, 1)
            o_dict["is_expired"] = (remaining < 0 and o["offer_acceptance"] == "Pending")
        except Exception:
            o_dict["hours_remaining"] = 0
            o_dict["is_expired"] = False
        processed_offers.append(o_dict)

    # For modal dropdowns
    students = query_db("SELECT id, placement_id, student_name, course FROM students WHERE is_archived = 0 ORDER BY student_name")
    drives = query_db("SELECT id, drive_code, company_name, category, offer_type, fte_package_ctc, stipend_amount FROM drives WHERE status = 'Active'")

    return render_template(
        "offers.html",
        offers=processed_offers,
        students=students,
        drives=drives,
        selected_status=selected_status,
        selected_type=selected_type,
        current_user=current_user
    )

@offer_bp.route("/offers/record", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer", "Recruiter")
def record_offer():
    current_user = get_current_user()
    student_id = int(request.form.get("student_id"))
    drive_id = request.form.get("drive_id")
    drive_id = int(drive_id) if drive_id and drive_id != "" else None
    
    company_name = request.form.get("company_name", "").strip()
    offer_type = request.form.get("offer_type", "F")
    fte_ctc = float(request.form.get("fte_package_ctc", 0.0))
    stipend_amount = float(request.form.get("stipend_amount", 0.0))
    stipend_period = request.form.get("stipend_period", "")
    offer_date = request.form.get("offer_date", datetime.now().date().isoformat())
    deadline_hours = int(request.form.get("deadline_hours", DEFAULT_OFFER_DEADLINE_HOURS))
    is_ppo = int(request.form.get("is_ppo", 0))
    ppo_status = request.form.get("ppo_status", "Not Applicable")
    is_off_campus = int(request.form.get("is_off_campus", 0))
    remarks = request.form.get("remarks", "")
    force_override = request.form.get("force_override") == "1"

    student = query_db("SELECT * FROM students WHERE id = ?", (student_id,), one=True)
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("offer.list_offers"))

    category = classify_category(fte_ctc)

    # Check Policy Engine Rules before recording offer
    existing_offers = query_db("SELECT * FROM offers WHERE student_id = ?", (student_id,))
    exceptions = query_db("SELECT * FROM policy_exceptions WHERE student_id = ? AND status = 'Approved'", (student_id,))

    target_mock_drive = {
        "company_name": company_name,
        "category": category,
        "offer_type": offer_type,
        "fte_package_ctc": fte_ctc,
        "min_cgpa": 0.0,
        "max_backlogs": 99,
        "eligible_courses": student["course"]
    }

    eval_result = evaluate_eligibility(
        student=dict(student),
        drive=target_mock_drive,
        existing_offers=[dict(o) for o in existing_offers],
        exceptions=[dict(e) for e in exceptions]
    )

    if eval_result["decision"] == "Blocked" and not force_override:
        flash(f"Policy Conflict Blocked: {eval_result['summary']}", "danger")
        return redirect(url_for("offer.list_offers"))

    deadline_at = (datetime.now() + timedelta(hours=deadline_hours)).isoformat()

    offer_id = execute_insert(
        """
        INSERT INTO offers
        (student_id, drive_id, company_name, category, offer_type, stipend_amount, stipend_period, fte_package_ctc, is_ppo, ppo_status, offer_acceptance, deadline_at, joining_status, offer_date, is_off_campus, noc_status, remarks, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, 'Pending', ?, ?, 'Not Required', ?, ?)
        """,
        (student_id, drive_id, company_name, category, offer_type, stipend_amount, stipend_period, fte_ctc, is_ppo, ppo_status, deadline_at, offer_date, is_off_campus, remarks, session["username"])
    )

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="OFFER_RECORDED",
        entity_type="Offer",
        entity_id=str(offer_id),
        details=f"Recorded {offer_type} offer for {student['student_name']} ({student['placement_id']}) from {company_name} (₹{fte_ctc} LPA / Category {category})."
    )

    flash(f"Offer recorded successfully for {student['student_name']}.", "success")
    return redirect(url_for("offer.list_offers"))

@offer_bp.route("/offers/<int:id>/status", methods=["POST"])
@login_required
def update_offer_status():
    """Accept, Decline, or mark Expired. Updates student placement status dynamically."""
    current_user = get_current_user()
    role = current_user["role"]

    offer = query_db("SELECT * FROM offers WHERE id = ?", (id,), one=True)
    if not offer:
        flash("Offer record not found.", "danger")
        return redirect(url_for("offer.list_offers"))

    # Security check: If role is Student, they can only accept/decline their own offer
    if role == "Student" and current_user["student_id"] != offer["student_id"]:
        flash("Unauthorized action.", "danger")
        return abort(403)

    new_status = request.form.get("offer_acceptance")
    if new_status not in ("Accepted", "Declined", "Expired"):
        flash("Invalid acceptance status.", "danger")
        return redirect(url_for("offer.list_offers"))

    before_state = dict(offer)

    execute_db(
        "UPDATE offers SET offer_acceptance = ? WHERE id = ?",
        (new_status, id)
    )

    # Recompute student placement status
    all_accepted = query_db(
        "SELECT * FROM offers WHERE student_id = ? AND offer_acceptance = 'Accepted'",
        (offer["student_id"],)
    )
    new_placement_status = calculate_placement_status([dict(o) for o in all_accepted])

    execute_db(
        "UPDATE students SET placement_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_placement_status, offer["student_id"])
    )

    log_audit_event(
        actor_username=current_user["username"],
        actor_role=role,
        action="OFFER_STATUS_UPDATE",
        entity_type="Offer",
        entity_id=str(id),
        details=f"Offer #{id} ({offer['company_name']}) status updated to '{new_status}'. Placement status -> '{new_placement_status}'.",
        before_state=before_state,
        after_state={"offer_acceptance": new_status, "new_placement_status": new_placement_status}
    )

    flash(f"Offer marked as '{new_status}'. Student status updated to '{new_placement_status}'.", "success")
    return redirect(url_for("offer.list_offers"))

@offer_bp.route("/offers/<int:id>/ppo", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer")
def update_ppo_status():
    """Convert Internship offer to Pre-Placement Offer (PPO)."""
    offer = query_db("SELECT * FROM offers WHERE id = ?", (id,), one=True)
    if not offer:
        flash("Offer not found.", "danger")
        return redirect(url_for("offer.list_offers"))

    ppo_status = request.form.get("ppo_status", "Offered")
    fte_ctc = float(request.form.get("fte_package_ctc", offer["fte_package_ctc"]))
    category = classify_category(fte_ctc)

    execute_db(
        """
        UPDATE offers 
        SET is_ppo = 1, ppo_status = ?, fte_package_ctc = ?, category = ?, offer_type = 'I+F'
        WHERE id = ?
        """,
        (ppo_status, fte_ctc, category, id)
    )

    if ppo_status == "Accepted":
        execute_db(
            "UPDATE students SET placement_status = 'Internship + PPO/FTE', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (offer["student_id"],)
        )

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="PPO_STATUS_UPDATE",
        entity_type="Offer",
        entity_id=str(id),
        details=f"Updated PPO status for offer #{id} to '{ppo_status}' with ₹{fte_ctc} LPA."
    )

    flash("PPO status updated successfully.", "success")
    return redirect(url_for("offer.list_offers"))

@offer_bp.route("/offers/<int:id>/noc", methods=["POST"])
@login_required
@role_required("Placement Administrator", "Placement Officer", "Course Coordinator")
def update_noc_status():
    """Update NOC and joining status."""
    noc_status = request.form.get("noc_status")
    joining_status = request.form.get("joining_status")

    execute_db(
        "UPDATE offers SET noc_status = ?, joining_status = ? WHERE id = ?",
        (noc_status, joining_status, id)
    )

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="NOC_JOINING_UPDATE",
        entity_type="Offer",
        entity_id=str(id),
        details=f"Updated NOC status to '{noc_status}' and joining to '{joining_status}'."
    )

    flash("NOC and joining records updated.", "success")
    return redirect(url_for("offer.list_offers"))
