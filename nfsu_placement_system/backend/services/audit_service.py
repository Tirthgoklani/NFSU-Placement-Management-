"""
Forensic Audit Blockchain Service
Implements immutable tamper-evident logging and blockchain verification for NFSU.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from backend.repositories.audit_repository import AuditRepository
from backend.core.crypto import sign_audit_payload

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

class AuditService:

    @staticmethod
    def log_event(actor_username: str, actor_role: str, action: str,
                  entity_type: str, entity_id: str = None, details: str = "",
                  before_state=None, after_state=None, ip_address: str = "127.0.0.1") -> str:
        """Appends a new cryptographically chained audit block."""
        timestamp = datetime.now(timezone.utc).isoformat()
        before_json = json.dumps(before_state, default=str) if before_state is not None else ""
        after_json = json.dumps(after_state, default=str) if after_state is not None else ""

        latest_hash = AuditRepository.get_latest_hash()
        prev_hash = latest_hash if latest_hash else GENESIS_HASH

        # Compute SHA-256 block hash
        payload = f"{timestamp}|{actor_username}|{actor_role}|{action}|{entity_type}|{entity_id or ''}|{details}|{before_json}|{after_json}|{prev_hash}"
        hasher = hashlib.sha256()
        hasher.update(payload.encode("utf-8"))
        record_hash = hasher.hexdigest()

        AuditRepository.append_log({
            "timestamp": timestamp,
            "actor_username": actor_username,
            "actor_role": actor_role,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else "",
            "details": details,
            "before_state": before_json,
            "after_state": after_json,
            "ip_address": ip_address,
            "previous_hash": prev_hash,
            "record_hash": record_hash
        })
        return record_hash

    @staticmethod
    def verify_chain_integrity() -> Dict[str, Any]:
        """Validates cryptographic integrity across all records in the audit ledger."""
        records = AuditRepository.get_all_ordered()
        if not records:
            return {
                "is_valid": True,
                "total_records": 0,
                "message": "Audit ledger is empty. Genesis integrity intact.",
                "tampered_record_id": None
            }

        expected_prev = GENESIS_HASH
        for r in records:
            # Verify previous hash link
            if r["previous_hash"] != expected_prev:
                return {
                    "is_valid": False,
                    "total_records": len(records),
                    "tampered_record_id": r["id"],
                    "message": f"Integrity break at block #{r['id']}: previous_hash mismatch."
                }

            # Recompute hash
            payload = f"{r['timestamp']}|{r['actor_username']}|{r['actor_role']}|{r['action']}|{r['entity_type']}|{r['entity_id'] or ''}|{r['details']}|{r['before_state'] or ''}|{r['after_state'] or ''}|{r['previous_hash']}"
            hasher = hashlib.sha256()
            hasher.update(payload.encode("utf-8"))
            computed_hash = hasher.hexdigest()

            if computed_hash != r["record_hash"]:
                return {
                    "is_valid": False,
                    "total_records": len(records),
                    "tampered_record_id": r["id"],
                    "message": f"Cryptographic tampering detected at block #{r['id']}: block payload modified."
                }

            expected_prev = r["record_hash"]

        return {
            "is_valid": True,
            "total_records": len(records),
            "latest_hash": expected_prev,
            "message": f"Cryptographic audit log verification successful. All {len(records)} blocks intact."
        }
