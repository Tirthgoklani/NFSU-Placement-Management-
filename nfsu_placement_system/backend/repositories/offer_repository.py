"""
Offer Repository Layer
Maintains full historical offer events and status transitions.
"""

from typing import List, Dict, Any, Optional
from backend.repositories.base_repository import BaseRepository

class OfferRepository(BaseRepository):

    @classmethod
    def get_by_id(cls, offer_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT o.*, s.student_name, s.placement_id, s.course, s.cgpa
            FROM offers o
            JOIN students s ON o.student_id = s.id
            WHERE o.id = ?
        """
        return cls.fetch_one(query, (offer_id,))

    @classmethod
    def list_by_student(cls, student_id: int) -> List[Dict[str, Any]]:
        return cls.fetch_all(
            "SELECT * FROM offers WHERE student_id = ? ORDER BY offer_date DESC, id DESC",
            (student_id,)
        )

    @classmethod
    def list_accepted_by_student(cls, student_id: int) -> List[Dict[str, Any]]:
        return cls.fetch_all(
            "SELECT * FROM offers WHERE student_id = ? AND offer_acceptance = 'Accepted'",
            (student_id,)
        )

    @classmethod
    def list_offers(cls, status: str = None, offer_type: str = None,
                    company_name: str = None, student_id: int = None,
                    course: str = None) -> List[Dict[str, Any]]:
        query = """
            SELECT o.*, s.student_name, s.placement_id, s.course, s.cgpa
            FROM offers o
            JOIN students s ON o.student_id = s.id
            WHERE 1=1
        """
        params = []
        if status and status != "all":
            query += " AND o.offer_acceptance = ?"
            params.append(status)
        if offer_type and offer_type != "all":
            query += " AND o.offer_type = ?"
            params.append(offer_type)
        if company_name:
            query += " AND o.company_name = ?"
            params.append(company_name)
        if student_id:
            query += " AND o.student_id = ?"
            params.append(student_id)
        if course:
            query += " AND s.course = ?"
            params.append(course)

        query += " ORDER BY o.offer_date DESC, o.id DESC"
        return cls.fetch_all(query, tuple(params))

    @classmethod
    def create(cls, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO offers
            (student_id, drive_id, company_name, category, offer_type, stipend_amount,
             stipend_period, fte_package_ctc, is_ppo, ppo_status, offer_acceptance,
             deadline_at, joining_status, offer_date, is_off_campus, noc_status, remarks, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data["student_id"], data.get("drive_id"), data["company_name"], data["category"],
            data["offer_type"], data.get("stipend_amount", 0.0), data.get("stipend_period"),
            data.get("fte_package_ctc", 0.0), data.get("is_ppo", 0),
            data.get("ppo_status", "Not Applicable"), data.get("offer_acceptance", "Pending"),
            data["deadline_at"], data.get("joining_status", "Pending"), data["offer_date"],
            data.get("is_off_campus", 0), data.get("noc_status", "Not Required"),
            data.get("remarks"), data["created_by"]
        )
        return cls.insert(query, params)

    @classmethod
    def update_acceptance_status(cls, offer_id: int, new_status: str) -> int:
        return cls.execute("UPDATE offers SET offer_acceptance = ? WHERE id = ?", (new_status, offer_id))

    @classmethod
    def update_ppo(cls, offer_id: int, ppo_status: str, ctc: float, category: str) -> int:
        query = """
            UPDATE offers 
            SET is_ppo = 1, ppo_status = ?, fte_package_ctc = ?, category = ?, offer_type = 'I+F'
            WHERE id = ?
        """
        return cls.execute(query, (ppo_status, ctc, category, offer_id))

    @classmethod
    def update_noc_joining(cls, offer_id: int, noc_status: str, joining_status: str) -> int:
        return cls.execute(
            "UPDATE offers SET noc_status = ?, joining_status = ? WHERE id = ?",
            (noc_status, joining_status, offer_id)
        )
