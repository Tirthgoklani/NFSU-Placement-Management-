"""
REST API: Audit Blockchain & Disaster Recovery Endpoints (/api/v1/audit)
"""

from flask import Blueprint, request, jsonify
from backend.services.audit_service import AuditService
from backend.repositories.audit_repository import AuditRepository
from backend.middleware.auth_middleware import api_role_required
from database import backup_database

audit_api_bp = Blueprint("audit_api", __name__, url_prefix="/api/v1/audit")

@audit_api_bp.route("/logs", methods=["GET"])
@api_role_required("Placement Administrator")
def get_logs(user):
    actor = request.args.get("actor")
    action = request.args.get("action")
    limit = int(request.args.get("limit", 100))
    logs = AuditRepository.query_logs(actor=actor, action=action, limit=limit)
    return jsonify({"count": len(logs), "logs": logs}), 200

@audit_api_bp.route("/verify", methods=["POST"])
@api_role_required("Placement Administrator")
def verify_blockchain(user):
    result = AuditService.verify_chain_integrity()
    return jsonify(result), 200 if result["is_valid"] else 409

@audit_api_bp.route("/backup", methods=["POST"])
@api_role_required("Placement Administrator")
def trigger_backup(user):
    try:
        backup_path = backup_database()
        AuditService.log_event(
            actor_username=user["username"],
            actor_role=user["role"],
            action="API_BACKUP_CREATED",
            entity_type="Backup",
            entity_id=backup_path,
            details="Triggered online database backup via secure API."
        )
        return jsonify({"status": "success", "backup_path": backup_path}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
