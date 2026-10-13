"""
Recruitment Drive & Attendance Repository
Handles drives, round attendance logs, and absenteeism records.
"""

from typing import List, Dict, Any, Optional
from backend.repositories.base_repository import BaseRepository

class DriveRepository(BaseRepository):

    @classmethod
    def get_by_id(cls, drive_id: int) -> Optional[Dict[str, Any]]:
        return cls.fetch_one("SELECT * FROM drives WHERE id = ?", (drive_id,))

    @classmethod
    def get_by_code(cls, drive_code: str) -> Optional[Dict[str, Any]]:
        return cls.fetch_one("SELECT * FROM drives WHERE drive_code = ?", (drive_code,))

    @classmethod
    def list_drives(cls, status: str = None, company_name: str = None) -> List[Dict[str, Any]]:
        conditions = []
        params = []
        if status and status != "all":
            conditions.append("status = ?")
            params.append(status)
        if company_name:
            conditions.append("company_name = ?")
            params.append(company_name)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return cls.fetch_all(f"SELECT * FROM drives {where} ORDER BY drive_date DESC", tuple(params))

    @classmethod
    def create(cls, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO drives
            (drive_code, company_name, category, offer_type, stipend_amount, stipend_period,
             fte_package_ctc, min_cgpa, max_backlogs, eligible_courses, acceptance_deadline_hours,
             drive_date, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data["drive_code"], data["company_name"], data["category"], data["offer_type"],
            data.get("stipend_amount", 0.0), data.get("stipend_period", ""),
            data.get("fte_package_ctc", 0.0), data.get("min_cgpa", 6.0), data.get("max_backlogs", 0),
            data.get("eligible_courses", ""), data.get("acceptance_deadline_hours", 24),
            data["drive_date"], data.get("status", "Active"), data["created_by"]
        )
        return cls.insert(query, params)

    @classmethod
    def record_attendance(cls, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO drive_attendance 
            (drive_id, student_id, activity_type, attendance_status, remarks, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            data["drive_id"], data["student_id"], data["activity_type"],
            data["attendance_status"], data.get("remarks"), data["recorded_by"]
        )
        return cls.insert(query, params)

    @classmethod
    def get_drive_attendance(cls, drive_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT a.*, s.student_name, s.placement_id, s.course
            FROM drive_attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.drive_id = ?
            ORDER BY a.recorded_at DESC
        """
        return cls.fetch_all(query, (drive_id,))

    @classmethod
    def get_student_attendance(cls, student_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT a.*, d.company_name, d.drive_code, d.drive_date
            FROM drive_attendance a
            JOIN drives d ON a.drive_id = d.id
            WHERE a.student_id = ?
            ORDER BY a.recorded_at DESC
        """
        return cls.fetch_all(query, (student_id,))
