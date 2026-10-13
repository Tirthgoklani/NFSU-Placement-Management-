"""
Policy Rule Service Layer
Evaluates candidate eligibility under NFSU 2026-27 placement guidelines and manages waivers.
"""

from typing import Dict, Any, List
from backend.repositories.student_repository import StudentRepository
from backend.repositories.offer_repository import OfferRepository
from backend.repositories.base_repository import BaseRepository
from backend.services.audit_service import AuditService
from backend.core.exceptions import NotFoundError, AuthorizationError
from policy_engine import evaluate_eligibility, classify_category

class PolicyService:

    @staticmethod
    def evaluate_candidate(student_id: int, target_drive: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the NFSU 2026-27 policy rule engine against a candidate and target drive."""
        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student", str(student_id))

        existing_offers = OfferRepository.list_by_student(student_id)
        exceptions = BaseRepository.fetch_all(
            "SELECT * FROM policy_exceptions WHERE student_id = ? AND status = 'Approved'",
            (student_id,)
        )

        evaluation = evaluate_eligibility(
            student=student,
            drive=target_drive,
            existing_offers=existing_offers,
            exceptions=exceptions
        )

        # Cache evaluation in database for audit trace
        drive_id = target_drive.get("id") if target_drive.get("id") != 0 else None
        BaseRepository.execute(
            """
            INSERT INTO policy_evaluations (student_id, drive_id, decision, reasons, evaluated_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, drive_id, evaluation["decision"], evaluation["summary"], current_user["username"])
        )

        return evaluation

    @staticmethod
    def grant_waiver(student_id: int, exception_type: str, justification: str, current_user: Dict[str, Any]) -> int:
        """Grants an authorized administrative policy waiver or absenteeism penalty reset."""
        if current_user["role"] != "Placement Administrator":
            raise AuthorizationError("Only Placement Administrators can grant institutional policy waivers.")

        student = StudentRepository.get_by_id(student_id)
        if not student:
            raise NotFoundError("Student", str(student_id))

        with BaseRepository.transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO policy_exceptions (student_id, exception_type, justification, status, approved_by)
                VALUES (?, ?, ?, 'Approved', ?)
                """,
                (student_id, exception_type, justification, current_user["username"])
            )
            exc_id = cur.lastrowid

            # If Absenteeism Waiver, immediately unblock the student
            if exception_type == "Absenteeism Waiver":
                cur.execute(
                    "UPDATE students SET absenteeism_penalty_drives_remaining = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (student_id,)
                )

        AuditService.log_event(
            actor_username=current_user["username"],
            actor_role=current_user["role"],
            action="POLICY_EXCEPTION_GRANTED",
            entity_type="PolicyException",
            entity_id=student["placement_id"],
            details=f"Approved '{exception_type}' for {student['student_name']} ({student['placement_id']}). Justification: {justification}"
        )
        return exc_id
