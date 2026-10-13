"""
Offer Lifecycle & Policy Enforcement Service
Automates offer recording, 24h deadlines, PPO conversions, and dynamic placement status calculation.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.repositories.offer_repository import OfferRepository
from backend.repositories.student_repository import StudentRepository
from backend.repositories.drive_repository import DriveRepository
from backend.services.policy_service import PolicyService
from backend.services.audit_service import AuditService
from backend.core.validators import validate_ctc, validate_offer_type, sanitize_text
from backend.core.exceptions import (
    NotFoundError, AuthorizationError, PolicyConflictError, ValidationError
)
from policy_engine import classify_category, calculate_placement_status
from config import DEFAULT_OFFER_DEADLINE_HOURS

class OfferService:

    @staticmethod
    def record_offer(data: Dict[str, Any], current_user: Dict[str, Any]) -> int:
        """Validates policy rules and registers a new recruitment offer."""
        role = current_user["role"]
        if role not in ("Placement Administrator", "Placement Officer", "Recruiter"):
            raise AuthorizationError("Unauthorized to record placement offers.")

        student_id = int(data["student_id"])
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student", str(student_id))

        company_name = sanitize_text(data["company_name"])
        if role == "Recruiter" and current_user.get("recruiter_company") != company_name:
            raise AuthorizationError("Recruiters can only issue offers on behalf of their affiliated organization.")

        offer_type = validate_offer_type(data.get("offer_type", "F"))
        fte_ctc = validate_ctc(data.get("fte_package_ctc", 0.0))
        stipend = float(data.get("stipend_amount", 0.0))
        category = classify_category(fte_ctc)

        # Policy Engine Gate: Verify candidate eligibility prior to recording offer
        mock_drive = {
            "id": data.get("drive_id", 0),
            "company_name": company_name,
            "category": category,
            "offer_type": offer_type,
            "fte_package_ctc": fte_ctc,
            "min_cgpa": 0.0,
            "max_backlogs": 99,
            "eligible_courses": student["course"]
        }

        policy_check = PolicyService.evaluate_candidate(student_id, mock_drive, current_user)
        force_override = data.get("force_override") is True and role == "Placement Administrator"

        if policy_check["decision"] == "Blocked" and not force_override:
            raise PolicyConflictError(
                f"Policy Conflict Blocked under Section 3.2: {policy_check['summary']}"
            )

        deadline_hours = int(data.get("deadline_hours", DEFAULT_OFFER_DEADLINE_HOURS))
        deadline_at = (datetime.now() + timedelta(hours=deadline_hours)).isoformat()
        offer_date = data.get("offer_date", datetime.now().date().isoformat())

        offer_id = OfferRepository.create({
            "student_id": student_id,
            "drive_id": data.get("drive_id"),
            "company_name": company_name,
            "category": category,
            "offer_type": offer_type,
            "stipend_amount": stipend,
            "stipend_period": sanitize_text(data.get("stipend_period", "")),
            "fte_package_ctc": fte_ctc,
            "is_ppo": int(data.get("is_ppo", 0)),
            "ppo_status": data.get("ppo_status", "Not Applicable"),
            "offer_acceptance": "Pending",
            "deadline_at": deadline_at,
            "joining_status": "Pending",
            "offer_date": offer_date,
            "is_off_campus": int(data.get("is_off_campus", 0)),
            "noc_status": data.get("noc_status", "Not Required"),
            "remarks": sanitize_text(data.get("remarks", "")),
            "created_by": current_user["username"]
        })

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=role,
            action="OFFER_RECORDED",
            entity_type="Offer",
            entity_id=str(offer_id),
            details=f"Issued {offer_type} offer to {student['student_name']} ({student['placement_id']}) from {company_name} (Category {category}, ₹{fte_ctc} LPA)."
        )
        return offer_id

    @staticmethod
    def update_acceptance(offer_id: int, new_status: str, current_user: Dict[str, Any]) -> None:
        """Updates offer acceptance status and dynamically computes canonical student placement status."""
        offer = OfferRepository.get_by_id(offer_id)
        if not offer:
            raise NotFoundError("Offer", str(offer_id))

        role = current_user["role"]
        # Candidate self-action: A student can only accept/decline their own offer
        if role == "Student" and current_user.get("student_id") != offer["student_id"]:
            raise AuthorizationError("Candidates can only respond to offers issued to their own account.")

        if new_status not in ("Accepted", "Declined", "Expired"):
            raise ValidationError(f"Invalid offer response status: '{new_status}'.")

        before_state = dict(offer)
        OfferRepository.update_acceptance_status(offer_id, new_status)

        # Dynamic Placement Status Calculation: Preserves history while deriving current status
        accepted_offers = OfferRepository.list_accepted_by_student(offer["student_id"])
        new_placement_status = calculate_placement_status(accepted_offers)

        StudentRepository.update(offer["student_id"], {
            "placement_status": new_placement_status
        })

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=role,
            action="OFFER_STATUS_UPDATE",
            entity_type="Offer",
            entity_id=str(offer_id),
            details=f"Offer #{offer_id} marked as '{new_status}'. Candidate placement status updated to '{new_placement_status}'.",
            before_state=before_state,
            after_state={"offer_acceptance": new_status, "derived_placement_status": new_placement_status}
        )

    @staticmethod
    def convert_to_ppo(offer_id: int, ppo_status: str, ctc: float, current_user: Dict[str, Any]) -> None:
        """Converts an internship offer to Pre-Placement Offer (PPO)."""
        if current_user["role"] not in ("Placement Administrator", "Placement Officer"):
            raise AuthorizationError("Only Placement Administrators and Officers can convert offers to PPO.")

        offer = OfferRepository.get_by_id(offer_id)
        if not offer:
            raise NotFoundError("Offer", str(offer_id))

        category = classify_category(ctc)
        OfferRepository.update_ppo(offer_id, ppo_status, ctc, category)

        if ppo_status == "Accepted":
            StudentRepository.update(offer["student_id"], {
                "placement_status": "Internship + PPO/FTE"
            })

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            action="PPO_CONVERSION",
            entity_type="Offer",
            entity_id=str(offer_id),
            details=f"PPO transition for offer #{offer_id} ({offer['company_name']}): Status '{ppo_status}', ₹{ctc} LPA."
        )
