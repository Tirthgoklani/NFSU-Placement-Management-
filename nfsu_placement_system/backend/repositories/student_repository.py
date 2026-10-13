"""
Student Repository Layer
Handles parameterized database operations for candidate master records.
"""

from typing import List, Dict, Any, Optional
from backend.repositories.base_repository import BaseRepository

class StudentRepository(BaseRepository):

    @classmethod
    def get_by_id(cls, student_id: int) -> Optional[Dict[str, Any]]:
        return cls.fetch_one("SELECT * FROM students WHERE id = ?", (student_id,))

    @classmethod
    def get_by_placement_id(cls, placement_id: str) -> Optional[Dict[str, Any]]:
        return cls.fetch_one("SELECT * FROM students WHERE placement_id = ?", (placement_id,))

    @classmethod
    def exists_placement_id(cls, placement_id: str, exclude_id: int = None) -> bool:
        if exclude_id:
            row = cls.fetch_one(
                "SELECT id FROM students WHERE placement_id = ? AND id != ?",
                (placement_id, exclude_id)
            )
        else:
            row = cls.fetch_one("SELECT id FROM students WHERE placement_id = ?", (placement_id,))
        return row is not None

    @classmethod
    def list_students(cls, course: str = None, placement_status: str = None,
                      registration_status: str = None, search: str = None,
                      include_archived: bool = False) -> List[Dict[str, Any]]:
        conditions = []
        params = []

        if not include_archived:
            conditions.append("is_archived = 0")

        if course and course != "all":
            conditions.append("course = ?")
            params.append(course)

        if placement_status and placement_status != "all":
            conditions.append("placement_status = ?")
            params.append(placement_status)

        if registration_status and registration_status != "all":
            conditions.append("registration_status = ?")
            params.append(registration_status)

        if search:
            conditions.append("(student_name LIKE ? OR placement_id LIKE ? OR email_id LIKE ?)")
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard, wildcard])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM students {where_clause} ORDER BY course, placement_id ASC"
        return cls.fetch_all(query, tuple(params))

    @classmethod
    def create(cls, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO students 
            (placement_id, student_name, mobile_number, email_id, course, batch, cgpa,
             active_backlogs, registration_status, eligibility_status, placement_status,
             absenteeism_count, absenteeism_penalty_drives_remaining)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data["placement_id"], data["student_name"], data["mobile_number"], data["email_id"],
            data["course"], data["batch"], data.get("cgpa", 0.0), data.get("active_backlogs", 0),
            data.get("registration_status", "Registered"), data.get("eligibility_status", "Eligible"),
            data.get("placement_status", "Unplaced"), data.get("absenteeism_count", 0),
            data.get("absenteeism_penalty_drives_remaining", 0)
        )
        return cls.insert(query, params)

    @classmethod
    def update(cls, student_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = []
        for key in ("student_name", "mobile_number", "email_id", "cgpa", "active_backlogs",
                    "registration_status", "eligibility_status", "placement_status",
                    "absenteeism_count", "absenteeism_penalty_drives_remaining", "batch"):
            if key in data:
                fields.append(f"{key} = ?")
                params.append(data[key])
        
        if not fields:
            return 0
        
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(student_id)
        query = f"UPDATE students SET {', '.join(fields)} WHERE id = ?"
        return cls.execute(query, tuple(params))

    @classmethod
    def archive(cls, student_id: int) -> int:
        return cls.execute("UPDATE students SET is_archived = 1 WHERE id = ?", (student_id,))
