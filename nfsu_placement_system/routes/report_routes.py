"""
Dashboard, Analytics, and Course-Wise Placement Reporting Routes
Produces institutional metrics, separate FTE CTC vs Internship stipend figures,
unique placed students vs total offers, and switching-eligibility rosters.
"""

import statistics
import csv
import io
from flask import Blueprint, render_template, request, Response, session
from database import query_db
from security import login_required, get_current_user, log_audit_event
from config import COURSES, BATCHES

report_bp = Blueprint("report", __name__)

def compute_placement_metrics():
    """Calculates rigorous university placement metrics adhering to NFSU 2026-27 policy."""
    students = query_db("SELECT * FROM students WHERE is_archived = 0")
    offers = query_db("SELECT * FROM offers")
    accepted_offers = [o for o in offers if o["offer_acceptance"] == "Accepted"]

    # Overall Student Counts
    total_students = len(students)
    total_registered = sum(1 for s in students if s["registration_status"] == "Registered")
    total_eligible = sum(1 for s in students if s["eligibility_status"] == "Eligible")
    total_ineligible = sum(1 for s in students if s["eligibility_status"] == "Ineligible")
    
    # Placed counts by canonical placement status
    internship_only_count = sum(1 for s in students if s["placement_status"] == "Internship Only")
    fte_only_count = sum(1 for s in students if s["placement_status"] == "FTE Only")
    internship_ppo_fte_count = sum(1 for s in students if s["placement_status"] == "Internship + PPO/FTE")
    
    unique_placed_students = internship_only_count + fte_only_count + internship_ppo_fte_count
    total_unplaced = sum(1 for s in students if s["placement_status"] == "Unplaced")
    total_offers_received = len(offers)

    # Separate Compensation Metrics: FTE CTC (in LPA)
    accepted_ctcs = [float(o["fte_package_ctc"]) for o in accepted_offers if float(o["fte_package_ctc"]) > 0]
    highest_fte_ctc = max(accepted_ctcs) if accepted_ctcs else 0.0
    avg_fte_ctc = round(statistics.mean(accepted_ctcs), 2) if accepted_ctcs else 0.0
    median_fte_ctc = round(statistics.median(accepted_ctcs), 2) if accepted_ctcs else 0.0

    # Separate Compensation Metrics: Internship Stipends (INR / Month)
    accepted_stipends = [float(o["stipend_amount"]) for o in accepted_offers if float(o["stipend_amount"]) > 0]
    highest_stipend = max(accepted_stipends) if accepted_stipends else 0.0
    avg_stipend = round(statistics.mean(accepted_stipends), 2) if accepted_stipends else 0.0

    # Course-Wise Placement Breakdown for all 5 Programmes
    course_stats = []
    for c in COURSES:
        c_students = [s for s in students if s["course"] == c]
        c_total = len(c_students)
        c_registered = sum(1 for s in c_students if s["registration_status"] == "Registered")
        c_placed = sum(1 for s in c_students if s["placement_status"] != "Unplaced")
        c_unplaced = c_total - c_placed
        c_rate = round((c_placed / c_total * 100), 1) if c_total > 0 else 0.0

        c_student_ids = {s["id"] for s in c_students}
        c_accepted_offers = [o for o in accepted_offers if o["student_id"] in c_student_ids]
        c_ctcs = [float(o["fte_package_ctc"]) for o in c_accepted_offers if float(o["fte_package_ctc"]) > 0]
        c_highest = max(c_ctcs) if c_ctcs else 0.0
        c_avg = round(statistics.mean(c_ctcs), 2) if c_ctcs else 0.0

        course_stats.append({
            "course": c,
            "total": c_total,
            "registered": c_registered,
            "placed": c_placed,
            "unplaced": c_unplaced,
            "rate": c_rate,
            "highest_ctc": c_highest,
            "avg_ctc": c_avg,
            "internship_only": sum(1 for s in c_students if s["placement_status"] == "Internship Only"),
            "fte_only": sum(1 for s in c_students if s["placement_status"] == "FTE Only"),
            "internship_ppo": sum(1 for s in c_students if s["placement_status"] == "Internship + PPO/FTE")
        })

    # Company-Wise Breakdown
    company_rows = query_db(
        """
        SELECT company_name, category, offer_type, COUNT(*) as offer_count,
               MAX(fte_package_ctc) as max_ctc, AVG(fte_package_ctc) as avg_ctc,
               MAX(stipend_amount) as max_stipend
        FROM offers
        GROUP BY company_name, category, offer_type
        ORDER BY max_ctc DESC
        """
    )

    # Switching Eligible Students List
    switching_eligible = []
    for s in students:
        s_offers = [o for o in accepted_offers if o["student_id"] == s["id"]]
        if not s_offers:
            continue
        
        status = s["placement_status"]
        if status == "Internship Only":
            switching_eligible.append({
                "student": s,
                "reason": "Internship Secured: Eligible for FTE (F) and I+F opportunities across all categories."
            })
        elif status == "FTE Only":
            highest_offer = max(s_offers, key=lambda x: float(x["fte_package_ctc"]))
            cat = highest_offer["category"]
            ctc = float(highest_offer["fte_package_ctc"])
            if cat == "A":
                switching_eligible.append({
                    "student": s,
                    "reason": f"Category A Holder (₹{ctc} LPA): Eligible to switch exclusively to Category A+ companies (≥ ₹16 LPA)."
                })
            elif cat == "B":
                switching_eligible.append({
                    "student": s,
                    "reason": f"Category B Holder (₹{ctc} LPA): Eligible for subsequent drives offering ≥ ₹{ctc * 1.5:.2f} LPA (1.5x rule)."
                })
            elif cat == "C":
                switching_eligible.append({
                    "student": s,
                    "reason": f"Category C Holder (₹{ctc} LPA): Eligible for higher category opportunities (B, A, A+)."
                })

    # Pending Compliance & Deadlines
    pending_offers = query_db(
        """
        SELECT o.*, s.student_name, s.placement_id, s.course
        FROM offers o
        JOIN students s ON o.student_id = s.id
        WHERE o.offer_acceptance = 'Pending'
        """
    )
    disciplinary_cases = [s for s in students if s["absenteeism_penalty_drives_remaining"] > 0]

    return {
        "total_students": total_students,
        "total_registered": total_registered,
        "total_eligible": total_eligible,
        "total_ineligible": total_ineligible,
        "unique_placed_students": unique_placed_students,
        "total_unplaced": total_unplaced,
        "total_offers_received": total_offers_received,
        "internship_only_count": internship_only_count,
        "fte_only_count": fte_only_count,
        "internship_ppo_fte_count": internship_ppo_fte_count,
        "highest_fte_ctc": highest_fte_ctc,
        "avg_fte_ctc": avg_fte_ctc,
        "median_fte_ctc": median_fte_ctc,
        "highest_stipend": highest_stipend,
        "avg_stipend": avg_stipend,
        "course_stats": course_stats,
        "company_rows": company_rows,
        "switching_eligible": switching_eligible,
        "pending_offers": pending_offers,
        "disciplinary_cases": disciplinary_cases
    }

@report_bp.route("/dashboard")
@login_required
def dashboard():
    metrics = compute_placement_metrics()
    current_user = get_current_user()
    recent_offers = query_db(
        """
        SELECT o.*, s.student_name, s.placement_id, s.course
        FROM offers o
        JOIN students s ON o.student_id = s.id
        ORDER BY o.created_at DESC LIMIT 5
        """
    )
    return render_template(
        "dashboard.html",
        metrics=metrics,
        recent_offers=recent_offers,
        current_user=current_user
    )

@report_bp.route("/reports")
@login_required
def detailed_reports():
    metrics = compute_placement_metrics()
    current_user = get_current_user()
    return render_template("reports.html", metrics=metrics, current_user=current_user)

@report_bp.route("/reports/export")
@login_required
def export_report_csv():
    metrics = compute_placement_metrics()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["NFSU PLACEMENT SESSION 2026-27 - INSTITUTIONAL SUMMARY REPORT"])
    writer.writerow([])
    writer.writerow(["Total Registered Candidates", metrics["total_registered"]])
    writer.writerow(["Unique Placed Students", metrics["unique_placed_students"]])
    writer.writerow(["Total Offers Received", metrics["total_offers_received"]])
    writer.writerow(["Unplaced Students", metrics["total_unplaced"]])
    writer.writerow(["Highest FTE Package (LPA)", metrics["highest_fte_ctc"]])
    writer.writerow(["Average FTE Package (LPA)", metrics["avg_fte_ctc"]])
    writer.writerow(["Median FTE Package (LPA)", metrics["median_fte_ctc"]])
    writer.writerow(["Highest Monthly Stipend (INR)", metrics["highest_stipend"]])
    writer.writerow([])
    writer.writerow(["COURSE-WISE PLACEMENT SUMMARY"])
    writer.writerow(["Course Programme", "Total Students", "Placed", "Unplaced", "Placement %", "Highest CTC (LPA)", "Average CTC (LPA)", "Internship Only", "FTE Only", "I+F"])

    for c in metrics["course_stats"]:
        writer.writerow([
            c["course"], c["total"], c["placed"], c["unplaced"], f"{c['rate']}%",
            c["highest_ctc"], c["avg_ctc"], c["internship_only"], c["fte_only"], c["internship_ppo"]
        ])

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="DATA_EXPORT",
        entity_type="Report",
        entity_id="ANNUAL_SUMMARY",
        details="Exported annual institutional placement statistics CSV report."
    )

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=NFSU_Placement_Statistics_2026_27.csv"}
    )

@report_bp.route("/presentation")
def presentation_view():
    """Competition Presentation Showcase Slide Deck"""
    metrics = compute_placement_metrics()
    return render_template("presentation.html", metrics=metrics)

