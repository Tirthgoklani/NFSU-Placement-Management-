"""
Recruitment Drive & Attendance Service
Manages drives, round activity, and automated 3-drive absenteeism penalties.
"""

from typing import Dict, Any, List
from backend.repositories.drive_repository import DriveRepository
from backend.repositories.student_repository import StudentRepository
from backend.core.validators import validate_ctc, validate_cgpa, sanitize_text
from backend.core.exceptions import NotFoundError, AuthorizationError
from backend.services.audit_service import AuditService
from policy_engine import classify_category
from config import ABSENTEEISM_PENALTY_DRIVES

class DriveService:

    @staticmethod
    def create_drive(data: Dict[str, Any], current_user: Dict[str, Any]) -> int:
        if current_user["role"] not in ("Placement Administrator", "Placement Officer"):
            raise AuthorizationError("Only Placement Administrators and Officers can schedule drives.")

        fte_ctc = validate_ctc(data.get("fte_package_ctc", 0.0))
        category = classify_category(fte_ctc)

        clean_data = {
            "drive_code": sanitize_text(data["drive_code"]).upper(),
            "company_name": sanitize_text(data["company_name"]),
            "category": category,
            "offer_type": data.get("offer_type", "F"),
            "stipend_amount": float(data.get("stipend_amount", 0.0)),
            "stipend_period": sanitize_text(data.get("stipend_period", "")),
            "fte_package_ctc": fte_ctc,
            "min_cgpa": validate_cgpa(data.get("min_cgpa", 6.0)),
            "max_backlogs": int(data.get("max_backlogs", 0)),
            "eligible_courses": sanitize_text(data.get("eligible_courses", "")),
            "acceptance_deadline_hours": int(data.get("acceptance_deadline_hours", 24)),
            "drive_date": data["drive_date"],
            "status": data.get("status", "Active"),
            "created_by": current_user["username"]
        }

        drive_id = DriveRepository.create(clean_data)

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            action="DRIVE_CREATE",
            entity_type="Drive",
            entity_id=clean_data["drive_code"],
            details=f"Scheduled recruitment drive for {clean_data['company_name']} (Category {category}, ₹{fte_ctc} LPA)."
        )
        return drive_id

    @staticmethod
    def get_drive(drive_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        drive = DriveRepository.get_by_id(drive_id)
        if not drive:
            raise NotFoundError("Drive", str(drive_id))

        # Recruiter Scoping Check
        if current_user["role"] == "Recruiter" and current_user.get("recruiter_company") != drive["company_name"]:
            raise AuthorizationError("Recruiters can only access recruitment drives for their affiliated organization.")

        return drive

    @staticmethod
    def record_attendance(drive_id: int, student_id: int, activity_type: str,
                          attendance_status: str, remarks: str, current_user: Dict[str, Any]) -> int:
        """Records round attendance and enforces the NFSU 3-drive penalty for unexcused absence."""
        if current_user["role"] not in ("Placement Administrator", "Placement Officer"):
            raise AuthorizationError("Only Placement Administrators and Officers can record round attendance.")

        drive = DriveRepository.get_by_id(drive_id)
        student = StudentRepository.get_by_id(student_id)
        if not drive or not student:
            raise NotFoundError("Drive/Student", f"{drive_id}/{student_id}")

        att_id = DriveRepository.record_attendance({
            "drive_id": drive_id,
            "student_id": student_id,
            "activity_type": activity_type,
            "attendance_status": attendance_status,
            "remarks": sanitize_text(remarks),
            "recorded_by": current_user["username"]
        })

        # Policy Rule: Unexcused absenteeism incurs 3-drive exclusion penalty
        if attendance_status == "Absent":
            new_count = student["absenteeism_count"] + 1
            StudentRepository.update(student_id, {
                "absenteeism_count": new_count,
                "absenteeism_penalty_drives_remaining": ABSENTEEISM_PENALTY_DRIVES
            })
            AuditService.log_event(
                actor_username=current_user["username"],
                actor_role=current_user["role"],
                action="ABSENTEEISM_PENALTY_APPLIED",
                entity_type="Student",
                entity_id=student["placement_id"],
                details=f"Unexcused absenteeism in {drive['company_name']} ({activity_type}). Applied {ABSENTEEISM_PENALTY_DRIVES}-drive exclusion penalty under Section 3.2."
            )
        else:
            AuditService.log_event(
                actor_username=current_user["username"],
                actor_role=current_user["role"],
                action="ATTENDANCE_RECORDED",
                entity_type="Attendance",
                entity_id=student["placement_id"],
                details=f"Recorded attendance '{attendance_status}' for {student['student_name']} in {drive['company_name']} ({activity_type})."
            )

        return att_id
