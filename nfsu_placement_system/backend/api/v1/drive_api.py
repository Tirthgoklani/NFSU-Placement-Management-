"""
REST API: Recruitment Drive Endpoints (/api/v1/drives)
"""

from flask import Blueprint, request, jsonify
from backend.services.drive_service import DriveService
from backend.repositories.drive_repository import DriveRepository
from backend.middleware.auth_middleware import api_auth_required, api_role_required
from backend.core.exceptions import NotFoundError, AuthorizationError, ValidationError

drive_api_bp = Blueprint("drive_api", __name__, url_prefix="/api/v1/drives")

@drive_api_bp.route("", methods=["GET"])
@api_auth_required
def list_drives(user):
    company = user.get("recruiter_company") if user["role"] == "Recruiter" else None
    status = request.args.get("status")
    drives = DriveRepository.list_drives(status=status, company_name=company)
    return jsonify({"count": len(drives), "drives": drives}), 200

@drive_api_bp.route("/<int:id>", methods=["GET"])
@api_auth_required
def get_drive(user, id):
    try:
        drive = DriveService.get_drive(id, user)
        attendance = DriveRepository.get_drive_attendance(id)
        return jsonify({"drive": drive, "attendance": attendance}), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
    except AuthorizationError as e:
        return jsonify({"error": "Forbidden", "message": str(e)}), 403

@drive_api_bp.route("", methods=["POST"])
@api_role_required("Placement Administrator", "Placement Officer")
def create_drive(user):
    data = request.get_json() or {}
    try:
        drive_id = DriveService.create_drive(data, user)
        return jsonify({"status": "success", "id": drive_id, "message": "Drive scheduled."}), 201
    except ValidationError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

@drive_api_bp.route("/<int:id>/attendance", methods=["POST"])
@api_role_required("Placement Administrator", "Placement Officer")
def record_attendance(user, id):
    data = request.get_json() or {}
    student_id = data.get("student_id")
    activity_type = data.get("activity_type", "Pre-Placement Talk")
    attendance_status = data.get("attendance_status", "Present")
    remarks = data.get("remarks", "")

    try:
        att_id = DriveService.record_attendance(
            drive_id=id,
            student_id=int(student_id),
            activity_type=activity_type,
            attendance_status=attendance_status,
            remarks=remarks,
            current_user=user
        )
        return jsonify({
            "status": "success",
            "attendance_id": att_id,
            "penalized": (attendance_status == "Absent"),
            "message": "Round attendance recorded."
        }), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
