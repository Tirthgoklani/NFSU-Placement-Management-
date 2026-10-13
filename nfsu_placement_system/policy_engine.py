"""
NFSU Placement Guidelines 2026-27 Policy Rule Engine
Automates institutional policy checks, switching criteria, offer-type constraints,
absenteeism penalties, and deadline compliance with transparent audit explanations.
"""

from datetime import datetime, timezone
import json
from config import CTC_THRESHOLDS, CATEGORY_B_MULTIPLIER, ABSENTEEISM_PENALTY_DRIVES

def classify_category(fte_ctc):
    """
    Classify company category based on FTE package / CTC:
    A+: >= 16.0 LPA
    A : 10.0 to 16.0 LPA
    B : 6.0 to 10.0 LPA
    C : Below 6.0 LPA
    """
    try:
        ctc = float(fte_ctc or 0.0)
    except (ValueError, TypeError):
        ctc = 0.0

    if ctc >= CTC_THRESHOLDS["A+"]:
        return "A+"
    elif ctc >= CTC_THRESHOLDS["A"]:
        return "A"
    elif ctc >= CTC_THRESHOLDS["B"]:
        return "B"
    else:
        return "C"

def calculate_placement_status(accepted_offers):
    """
    Computes canonical placement status from active/accepted offers:
    - 'Unplaced'
    - 'Internship Only'
    - 'FTE Only'
    - 'Internship + PPO/FTE'
    """
    if not accepted_offers:
        return "Unplaced"
    
    types = set(o.get("offer_type") for o in accepted_offers)
    has_ppo_accepted = any(o.get("ppo_status") == "Accepted" for o in accepted_offers)
    
    if "I+F" in types or has_ppo_accepted or ("I" in types and "F" in types):
        return "Internship + PPO/FTE"
    elif "F" in types:
        return "FTE Only"
    elif "I" in types:
        return "Internship Only"
    
    return "Unplaced"

def evaluate_eligibility(student, drive, existing_offers=None, exceptions=None):
    """
    Core NFSU 2026-27 Policy Evaluator.
    Evaluates whether a student is Allowed, Blocked, or Referred for Manual Review
    for a target recruitment drive or offer.
    
    Returns structured dict with decision, pass/fail status per check, and detailed narrative.
    """
    if existing_offers is None:
        existing_offers = []
    if exceptions is None:
        exceptions = []

    steps = []
    decision = "Allowed"
    summary = "Student satisfies all NFSU 2026-27 placement guidelines for this drive."

    # Parse student fields safely
    s_id = student.get("placement_id", "Unknown")
    s_course = student.get("course", "")
    s_reg = student.get("registration_status", "Not Registered")
    s_elig = student.get("eligibility_status", "Pending Verification")
    s_cgpa = float(student.get("cgpa", 0.0))
    s_backlogs = int(student.get("active_backlogs", 0))
    s_penalty_drives = int(student.get("absenteeism_penalty_drives_remaining", 0))

    # Parse drive fields
    d_company = drive.get("company_name", "Target Company")
    d_cat = drive.get("category") or classify_category(drive.get("fte_package_ctc", 0.0))
    d_type = drive.get("offer_type", "F")
    d_ctc = float(drive.get("fte_package_ctc", 0.0))
    d_min_cgpa = float(drive.get("min_cgpa", 0.0))
    d_max_backlogs = int(drive.get("max_backlogs", 0))
    d_eligible_courses = drive.get("eligible_courses", "")

    # Approved exception waivers
    approved_exceptions = [e for e in exceptions if e.get("status") == "Approved"]
    waiver_types = {e.get("exception_type") for e in approved_exceptions}

    # -------------------------------------------------------------
    # 1. Registration Status Check
    # -------------------------------------------------------------
    if s_reg != "Registered":
        steps.append({
            "step": "Registration Verification",
            "passed": False,
            "rule": "Only actively registered students can participate in campus placements.",
            "detail": f"Registration status is '{s_reg}'. Must be 'Registered'."
        })
        return {
            "decision": "Blocked",
            "can_apply": False,
            "needs_review": False,
            "summary": f"Registration check failed: Student is '{s_reg}'.",
            "steps": steps
        }
    else:
        steps.append({
            "step": "Registration Verification",
            "passed": True,
            "rule": "Actively registered in 2026-27 Placement Session.",
            "detail": "Verified: Student is actively registered."
        })

    # -------------------------------------------------------------
    # 2. Institutional Eligibility Verification
    # -------------------------------------------------------------
    if s_elig == "Ineligible":
        steps.append({
            "step": "Institutional Eligibility",
            "passed": False,
            "rule": "Student must not be flagged Ineligible by Academic/Placement Cell.",
            "detail": "Student is marked as Ineligible by institutional administration."
        })
        return {
            "decision": "Blocked",
            "can_apply": False,
            "needs_review": False,
            "summary": "Institutional check failed: Student is marked Ineligible.",
            "steps": steps
        }
    elif s_elig == "Pending Verification":
        steps.append({
            "step": "Institutional Eligibility",
            "passed": False,
            "rule": "Student credentials must be verified before participation.",
            "detail": "Eligibility status is 'Pending Verification'. Requires Course Coordinator review."
        })
        decision = "Referred for Manual Review"
        summary = "Eligibility is 'Pending Verification' - referred to Course Coordinator."
    else:
        steps.append({
            "step": "Institutional Eligibility",
            "passed": True,
            "rule": "Institutional verification cleared.",
            "detail": "Verified: Student status is Eligible."
        })

    # -------------------------------------------------------------
    # 3. Absenteeism & Disciplinary Penalty Check
    # -------------------------------------------------------------
    if s_penalty_drives > 0:
        if "Absenteeism Waiver" in waiver_types:
            steps.append({
                "step": "Attendance & Absenteeism",
                "passed": True,
                "rule": "Absenteeism penalty waived under authorized emergency exception.",
                "detail": f"Penalty of {s_penalty_drives} drive(s) was waived by Placement Cell authority."
            })
        else:
            steps.append({
                "step": "Attendance & Absenteeism",
                "passed": False,
                "rule": "Unexcused absenteeism penalty excludes student from 3 consecutive drives.",
                "detail": f"Student has {s_penalty_drives} penalized drive(s) remaining due to prior unexcused absenteeism."
            })
            return {
                "decision": "Blocked",
                "can_apply": False,
                "needs_review": False,
                "summary": f"Blocked: Disciplinary penalty active ({s_penalty_drives} exclusion drives remaining).",
                "steps": steps
            }
    else:
        steps.append({
            "step": "Attendance & Absenteeism",
            "passed": True,
            "rule": "No active absenteeism exclusion penalties.",
            "detail": "Verified: No disciplinary exclusions."
        })

    # -------------------------------------------------------------
    # 4. Academic Criteria (Programme, CGPA, Backlogs)
    # -------------------------------------------------------------
    # Check course eligibility
    if d_eligible_courses:
        # Check if course string is present in comma/JSON list
        if s_course not in d_eligible_courses:
            steps.append({
                "step": "Programme Eligibility",
                "passed": False,
                "rule": f"Drive is restricted to specific NFSU programmes.",
                "detail": f"Student course '{s_course}' is not eligible for this drive."
            })
            return {
                "decision": "Blocked",
                "can_apply": False,
                "needs_review": False,
                "summary": f"Programme mismatch: '{s_course}' is not eligible for this drive.",
                "steps": steps
            }
        else:
            steps.append({
                "step": "Programme Eligibility",
                "passed": True,
                "rule": "Student enrolled in an eligible academic programme.",
                "detail": f"Verified: '{s_course}' is eligible."
            })

    # Check CGPA
    if s_cgpa < d_min_cgpa:
        if "Eligibility Waiver" in waiver_types:
            steps.append({
                "step": "Academic Criteria (CGPA)",
                "passed": True,
                "rule": "CGPA requirement waived under approved administrative exception.",
                "detail": f"CGPA {s_cgpa:.2f} is below {d_min_cgpa:.2f}, but authorized waiver exists."
            })
        else:
            steps.append({
                "step": "Academic Criteria (CGPA)",
                "passed": False,
                "rule": f"Minimum CGPA required is {d_min_cgpa:.2f}.",
                "detail": f"Student CGPA ({s_cgpa:.2f}) is below minimum requirement ({d_min_cgpa:.2f})."
            })
            return {
                "decision": "Blocked",
                "can_apply": False,
                "needs_review": False,
                "summary": f"CGPA requirement not met ({s_cgpa:.2f} < {d_min_cgpa:.2f}).",
                "steps": steps
            }
    else:
        steps.append({
            "step": "Academic Criteria (CGPA)",
            "passed": True,
            "rule": f"Minimum CGPA requirement {d_min_cgpa:.2f} met.",
            "detail": f"Verified: CGPA is {s_cgpa:.2f}."
        })

    # Check Backlogs
    if s_backlogs > d_max_backlogs:
        steps.append({
            "step": "Academic Criteria (Backlogs)",
            "passed": False,
            "rule": f"Maximum permissible active backlogs: {d_max_backlogs}.",
            "detail": f"Student has {s_backlogs} active backlog(s), exceeding drive threshold of {d_max_backlogs}."
        })
        return {
            "decision": "Blocked",
            "can_apply": False,
            "needs_review": False,
            "summary": f"Backlog limit exceeded ({s_backlogs} > {d_max_backlogs}).",
            "steps": steps
        }
    else:
        steps.append({
            "step": "Academic Criteria (Backlogs)",
            "passed": True,
            "rule": f"Permissible active backlogs: <= {d_max_backlogs}.",
            "detail": f"Verified: {s_backlogs} active backlogs."
        })

    # -------------------------------------------------------------
    # 5. Policy Switching Rules & Offer-Type Restrictions
    # -------------------------------------------------------------
    # Filter active accepted offers (ignore declined/expired offers)
    active_accepted = [o for o in existing_offers if o.get("offer_acceptance") in ("Accepted", "Pending")]

    if not active_accepted:
        steps.append({
            "step": "Switching & Category Policy",
            "passed": True,
            "rule": "Unplaced students are eligible for all categories (A+, A, B, C) and offer types.",
            "detail": "Verified: Student holds no prior offers; fully eligible."
        })
        return {
            "decision": decision,
            "can_apply": (decision == "Allowed"),
            "needs_review": (decision == "Referred for Manual Review"),
            "summary": summary,
            "steps": steps
        }

    # If student has prior accepted offers, evaluate NFSU Switching Rules
    has_switch_override = "Switching Rule Override" in waiver_types

    for offer in active_accepted:
        o_company = offer.get("company_name", "Existing Company")
        o_cat = offer.get("category") or classify_category(offer.get("fte_package_ctc", 0.0))
        o_type = offer.get("offer_type", "F")
        o_ctc = float(offer.get("fte_package_ctc", 0.0))
        o_status = offer.get("offer_acceptance", "Pending")

        # 5a. Offer-Type Restriction: I+F Lockout
        if o_type == "I+F":
            if has_switch_override:
                steps.append({
                    "step": "Offer-Type Constraint (I+F)",
                    "passed": True,
                    "rule": "I+F restriction waived via Placement Cell authorization.",
                    "detail": f"Held I+F offer from {o_company}, but exception was granted."
                })
            else:
                steps.append({
                    "step": "Offer-Type Constraint (I+F)",
                    "passed": False,
                    "rule": "Selection in an 'Internship + PPO/FTE (I+F)' role precludes participating in any other I, F, or I+F roles at another organization.",
                    "detail": f"Student has accepted/pending I+F offer from {o_company}. Locked from all further recruitment drives."
                })
                return {
                    "decision": "Blocked",
                    "can_apply": False,
                    "needs_review": False,
                    "summary": f"Blocked: Already secured I+F offer with {o_company}; out of placement process.",
                    "steps": steps
                }

        # 5b. Offer-Type Restriction: Internship Only (I)
        if o_type == "I" and d_type == "I":
            steps.append({
                "step": "Offer-Type Constraint (Internship)",
                "passed": False,
                "rule": "After selection for an internship, the student cannot apply for another internship-only role.",
                "detail": f"Student already accepted Internship offer from {o_company}. Cannot apply for another internship-only role. May apply for FTE or I+F."
            })
            return {
                "decision": "Blocked",
                "can_apply": False,
                "needs_review": False,
                "summary": f"Blocked: Cannot apply for another internship-only role after securing internship with {o_company}.",
                "steps": steps
            }

        # 5c. Offer-Type Restriction: FTE Only (F)
        if o_type == "F" and d_type == "F":
            # An FTE placed student can only switch if permitted by Category rules (below)
            # If target is Internship ('I'), policy allows it ("may apply for an internship role")
            pass

        # 5d. Company Category Switching Rules (Applies to FTE compensation)
        if o_type in ("F", "I+F") and o_ctc > 0:
            # Rule for A+ (>= 16 LPA)
            if o_cat == "A+":
                if has_switch_override:
                    steps.append({
                        "step": "Category Switching (A+)",
                        "passed": True,
                        "rule": "A+ restriction waived by Placement Cell.",
                        "detail": f"Student holds A+ offer from {o_company} (₹{o_ctc:.2f} LPA), waiver approved."
                    })
                else:
                    steps.append({
                        "step": "Category Switching (A+)",
                        "passed": False,
                        "rule": "Category A+ (≥ ₹16 LPA): No switching policy; students selected in A+ are out of the placement process.",
                        "detail": f"Student secured A+ category offer with {o_company} (₹{o_ctc:.2f} LPA). Out of placement process."
                    })
                    return {
                        "decision": "Blocked",
                        "can_apply": False,
                        "needs_review": False,
                        "summary": f"Blocked: Selected in Category A+ ({o_company}, ₹{o_ctc:.2f} LPA). No switching allowed.",
                        "steps": steps
                    }

            # Rule for A (10 - 16 LPA)
            elif o_cat == "A":
                if d_cat != "A+" or d_ctc < CTC_THRESHOLDS["A+"]:
                    if has_switch_override:
                        steps.append({
                            "step": "Category Switching (A)",
                            "passed": True,
                            "rule": "A switching policy overridden by Placement Cell.",
                            "detail": f"Holds Category A offer ({o_company}, ₹{o_ctc:.2f} LPA); target is {d_cat}."
                        })
                    else:
                        steps.append({
                            "step": "Category Switching (A)",
                            "passed": False,
                            "rule": "Category A (₹10–16 LPA): Switching allowed ONLY to A+ category companies (≥ ₹16 LPA).",
                            "detail": f"Student holds Category A offer from {o_company} (₹{o_ctc:.2f} LPA). Target drive is Category {d_cat} (₹{d_ctc:.2f} LPA). Switching not allowed."
                        })
                        return {
                            "decision": "Blocked",
                            "can_apply": False,
                            "needs_review": False,
                            "summary": f"Blocked: Category A holders can only switch to Category A+ (≥ ₹16 LPA). Target is {d_cat}.",
                            "steps": steps
                        }
                else:
                    steps.append({
                        "step": "Category Switching (A -> A+)",
                        "passed": True,
                        "rule": "Category A to A+ upgrade permitted by NFSU Guidelines.",
                        "detail": f"Valid upgrade: Category A ({o_company}, ₹{o_ctc:.2f} LPA) -> Category A+ ({d_company}, ₹{d_ctc:.2f} LPA)."
                    })

            # Rule for B (6 - 10 LPA)
            elif o_cat == "B":
                min_required_ctc = o_ctc * CATEGORY_B_MULTIPLIER
                if d_ctc < min_required_ctc:
                    if has_switch_override:
                        steps.append({
                            "step": "Category Switching (B 1.5x Multiplier)",
                            "passed": True,
                            "rule": "1.5x switching requirement overridden by Placement Cell.",
                            "detail": f"Target ₹{d_ctc:.2f} LPA is below 1.5x threshold ₹{min_required_ctc:.2f} LPA, but waiver granted."
                        })
                    else:
                        steps.append({
                            "step": "Category Switching (B 1.5x Multiplier)",
                            "passed": False,
                            "rule": f"Category B (₹6–10 LPA): Further placement allowed only where the new package is at least 1.5 times the existing package (≥ ₹{min_required_ctc:.2f} LPA).",
                            "detail": f"Student holds Category B offer from {o_company} (₹{o_ctc:.2f} LPA). Target package is ₹{d_ctc:.2f} LPA, which is below the required 1.5x threshold of ₹{min_required_ctc:.2f} LPA."
                        })
                        return {
                            "decision": "Blocked",
                            "can_apply": False,
                            "needs_review": False,
                            "summary": f"Blocked: New package (₹{d_ctc:.2f} LPA) is less than 1.5x of existing Category B package (requires ≥ ₹{min_required_ctc:.2f} LPA).",
                            "steps": steps
                        }
                else:
                    steps.append({
                        "step": "Category Switching (B -> Higher with >= 1.5x)",
                        "passed": True,
                        "rule": f"New package satisfies 1.5x multiplier requirement (Target ₹{d_ctc:.2f} LPA ≥ Required ₹{min_required_ctc:.2f} LPA).",
                        "detail": f"Eligible switch: {o_company} (₹{o_ctc:.2f} LPA) -> {d_company} (₹{d_ctc:.2f} LPA, {d_ctc/o_ctc:.2f}x existing)."
                    })

            # Rule for C (< 6 LPA)
            elif o_cat == "C":
                # Eligible for higher category opportunities (B, A, A+)
                if d_cat == "C":
                    if has_switch_override:
                        steps.append({
                            "step": "Category Switching (C)",
                            "passed": True,
                            "rule": "Lateral Category C switch permitted under exception.",
                            "detail": "Exception approved for lateral transition."
                        })
                    else:
                        steps.append({
                            "step": "Category Switching (C)",
                            "passed": False,
                            "rule": "Category C (< ₹6 LPA): Eligible for higher-category opportunities (B, A, A+). Lateral switching within Category C is prohibited.",
                            "detail": f"Student holds Category C offer from {o_company} (₹{o_ctc:.2f} LPA). Target drive is also Category C (₹{d_ctc:.2f} LPA). Must apply to Category B or higher."
                        })
                        return {
                            "decision": "Blocked",
                            "can_apply": False,
                            "needs_review": False,
                            "summary": "Blocked: Lateral switching within Category C is prohibited. Must be Category B, A, or A+.",
                            "steps": steps
                        }
                else:
                    steps.append({
                        "step": "Category Switching (C -> Higher)",
                        "passed": True,
                        "rule": "Category C upgrade to higher category is permitted.",
                        "detail": f"Eligible upgrade: Category C ({o_company}, ₹{o_ctc:.2f} LPA) -> Category {d_cat} ({d_company}, ₹{d_ctc:.2f} LPA)."
                    })

    return {
        "decision": decision,
        "can_apply": (decision == "Allowed"),
        "needs_review": (decision == "Referred for Manual Review"),
        "summary": summary,
        "steps": steps
    }
