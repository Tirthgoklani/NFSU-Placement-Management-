"""
REST API: Policy Rule Engine Endpoints (/api/v1/policy)
"""

from flask import Blueprint, request, jsonify
from backend.services.policy_service import PolicyService
from backend.middleware.auth_middleware import api_auth_required, api_role_required
from backend.core.exceptions import NotFoundError, AuthorizationError

policy_api_bp = Blueprint("policy_api", __name__, url_prefix="/api/v1/policy")

@policy_api_bp.route("/evaluate", methods=["POST"])
@api_auth_required
def evaluate(user):
    data = request.get_json() or {}
    student_id = data.get("student_id")
    target_drive = data.get("drive")

    if not student_id or not target_drive:
        return jsonify({"error": "student_id and drive payload are required."}), 400

    try:
        result = PolicyService.evaluate_candidate(int(student_id), target_drive, user)
        return jsonify(result), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404

@policy_api_bp.route("/waivers", methods=["POST"])
@api_role_required("Placement Administrator")
def grant_waiver(user):
    data = request.get_json() or {}
    student_id = data.get("student_id")
    exception_type = data.get("exception_type", "Absenteeism Waiver")
    justification = data.get("justification", "")

    if not student_id or not justification:
        return jsonify({"error": "student_id and justification are required."}), 400

    try:
        exc_id = PolicyService.grant_waiver(int(student_id), exception_type, justification, user)
        return jsonify({
            "status": "success",
            "waiver_id": exc_id,
            "message": f"Waiver '{exception_type}' granted."
        }), 201
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
