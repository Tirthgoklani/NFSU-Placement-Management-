"""
Forensic Audit Repository
Persists cryptographically chained audit blocks with SHA-256 and HMAC digital signatures.
"""

from typing import List, Dict, Any, Optional
from backend.repositories.base_repository import BaseRepository

class AuditRepository(BaseRepository):

    @classmethod
    def get_latest_hash(cls) -> Optional[str]:
        row = cls.fetch_one("SELECT record_hash FROM audit_logs ORDER BY id DESC LIMIT 1")
        return row["record_hash"] if row else None

    @classmethod
    def append_log(cls, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO audit_logs 
            (timestamp, actor_username, actor_role, action, entity_type, entity_id,
             details, before_state, after_state, ip_address, previous_hash, record_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data["timestamp"], data["actor_username"], data["actor_role"],
            data["action"], data["entity_type"], data.get("entity_id"),
            data["details"], data.get("before_state"), data.get("after_state"),
            data.get("ip_address", "127.0.0.1"), data["previous_hash"], data["record_hash"]
        )
        return cls.insert(query, params)

    @classmethod
    def get_all_ordered(cls) -> List[Dict[str, Any]]:
        return cls.fetch_all("SELECT * FROM audit_logs ORDER BY id ASC")

    @classmethod
    def query_logs(cls, actor: str = None, action: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        conditions = []
        params = []
        if actor:
            conditions.append("actor_username LIKE ?")
            params.append(f"%{actor}%")
        if action and action != "all":
            conditions.append("action = ?")
            params.append(action)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM audit_logs {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return cls.fetch_all(query, tuple(params))
