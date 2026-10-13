"""
Student Management Service
Encapsulates candidate business logic, IDOR protection, privacy masking, and validation.
"""

from typing import List, Dict, Any, Optional
from backend.repositories.student_repository import StudentRepository
from backend.core.validators import (
    validate_placement_id, validate_email, validate_mobile,
    validate_course, validate_cgpa, validate_backlogs, sanitize_text
)
from backend.core.crypto import encrypt_pii, decrypt_pii
from backend.core.exceptions import (
    NotFoundError, DuplicateResourceError, AuthorizationError, IDORViolationError
)
from backend.services.audit_service import AuditService
from security import mask_mobile_number, mask_email_address

class StudentService:

    @staticmethod
    def get_student(student_id: int, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieves candidate record with strict IDOR and departmental scope verification."""
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student", str(student_id))

        role = current_user["role"]

        # Security Challenge Defense: Student IDOR Check
        if role == "Student" and current_user.get("student_id") != student_id:
            AuditService.log_event(
                actor_username=current_user["username"],
                actor_role=role,
                action="IDOR_VIOLATION_ATTEMPT",
                entity_type="Student",
                entity_id=str(student_id),
                details=f"Unauthorized access attempt to student record #{student_id} by {current_user['username']}."
            )
            raise IDORViolationError(f"Student #{student_id}")

        # Course Coordinator Scoping Check
        if role == "Course Coordinator" and current_user.get("assigned_course") != student["course"]:
            raise AuthorizationError(f"Access restricted to assigned programme: {current_user.get('assigned_course')}")

        # Apply privacy masking
        s_dict = dict(student)
        s_dict["display_mobile"] = mask_mobile_number(student["mobile_number"], role)
        s_dict["display_email"] = mask_email_address(student["email_id"], role)
        return s_dict

    @staticmethod
    def list_students(current_user: Dict[str, Any], course: str = None,
                      placement_status: str = None, registration_status: str = None,
                      search: str = None) -> List[Dict[str, Any]]:
        """Lists candidate directory with privacy masking and role-based scope isolation."""
        role = current_user["role"]

        if role == "Student":
            raise AuthorizationError("Students cannot browse the global placement directory.")
        if role == "Recruiter":
            raise AuthorizationError("Recruiters can only access candidates within their affiliated recruitment drives.")
        if role == "Course Coordinator":
            course = current_user.get("assigned_course")

        students = StudentRepository.list_students(
            course=course,
            placement_status=placement_status,
            registration_status=registration_status,
            search=search
        )

        masked_list = []
        for s in students:
            s_dict = dict(s)
            s_dict["display_mobile"] = mask_mobile_number(s["mobile_number"], role)
            s_dict["display_email"] = mask_email_address(s["email_id"], role)
            masked_list.append(s_dict)

        return masked_list

    @staticmethod
    def create_student(data: Dict[str, Any], current_user: Dict[str, Any]) -> int:
        """Validates, sanitizes, and creates a new candidate record."""
        if current_user["role"] not in ("Placement Administrator", "Placement Officer"):
            raise AuthorizationError("Only Placement Administrators and Officers can register students.")

        p_id = validate_placement_id(data.get("placement_id", ""))
        email = validate_email(data.get("email_id", ""))
        mobile = validate_mobile(data.get("mobile_number", ""))
        course = validate_course(data.get("course", ""))
        cgpa = validate_cgpa(data.get("cgpa", 0.0))
        backlogs = validate_backlogs(data.get("active_backlogs", 0))

        # Check Placement ID uniqueness
        if StudentRepository.exists_placement_id(p_id):
            raise DuplicateResourceError("Student", "placement_id", p_id)

        clean_data = {
            "placement_id": p_id,
            "student_name": sanitize_text(data.get("student_name", "")),
            "mobile_number": mobile,
            "email_id": email,
            "course": course,
            "batch": sanitize_text(data.get("batch", "2025–2027")),
            "cgpa": cgpa,
            "active_backlogs": backlogs,
            "registration_status": data.get("registration_status", "Registered"),
            "eligibility_status": data.get("eligibility_status", "Eligible"),
            "placement_status": "Unplaced"
        }

        student_id = StudentRepository.create(clean_data)

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            action="STUDENT_CREATE",
            entity_type="Student",
            entity_id=p_id,
            details=f"Created candidate profile for {clean_data['student_name']} ({p_id}) in {course}."
        )
        return student_id

    @staticmethod
    def update_student(student_id: int, data: Dict[str, Any], current_user: Dict[str, Any]) -> None:
        """Modifies candidate details with RBAC checks and audit state diffs."""
        role = current_user["role"]
        if role == "Student":
            # Security Challenge Defense: Prevent candidate self-tampering
            AuditService.log_event(
                actor_username=current_user["username"],
                actor_role=role,
                action="TAMPER_ATTEMPT_BLOCKED",
                entity_type="Student",
                entity_id=str(student_id),
                details=f"Candidate {current_user['username']} attempted unauthorized modification of student record #{student_id}."
            )
            raise AuthorizationError("Security Policy: Candidates cannot modify their own placement records or status.")

        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student", str(student_id))

        if role == "Course Coordinator" and current_user.get("assigned_course") != student["course"]:
            raise AuthorizationError("Course Coordinators cannot modify students outside their assigned programme.")

        before_state = dict(student)
        update_dict = {}

        if "student_name" in data:
            update_dict["student_name"] = sanitize_text(data["student_name"])
        if "mobile_number" in data:
            update_dict["mobile_number"] = validate_mobile(data["mobile_number"])
        if "email_id" in data:
            update_dict["email_id"] = validate_email(data["email_id"])
        if "cgpa" in data:
            update_dict["cgpa"] = validate_cgpa(data["cgpa"])
        if "active_backlogs" in data:
            update_dict["active_backlogs"] = validate_backlogs(data["active_backlogs"])
        if "registration_status" in data:
            update_dict["registration_status"] = data["registration_status"]
        if "eligibility_status" in data:
            update_dict["eligibility_status"] = data["eligibility_status"]
        if "absenteeism_penalty_drives_remaining" in data:
            update_dict["absenteeism_penalty_drives_remaining"] = int(data["absenteeism_penalty_drives_remaining"])

        StudentRepository.update(student_id, update_dict)
        after_student = StudentRepository.get_by_id(student_id)

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=role,
            action="STUDENT_UPDATE",
            entity_type="Student",
            entity_id=student["placement_id"],
            details=f"Updated candidate records for {student['student_name']} ({student['placement_id']}).",
            before_state=before_state,
            after_state=dict(after_student)
        )

    @staticmethod
    def archive_student(student_id: int, current_user: Dict[str, Any]) -> None:
        """Soft-deletes/archives a student record."""
        if current_user["role"] != "Placement Administrator":
            raise AuthorizationError("Only Placement Administrators can archive candidate records.")

        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student", str(student_id))

        StudentRepository.archive(student_id)
        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            action="STUDENT_ARCHIVE",
            entity_type="Student",
            entity_id=student["placement_id"],
            details=f"Archived candidate profile for {student['student_name']} ({student['placement_id']})."
        )
