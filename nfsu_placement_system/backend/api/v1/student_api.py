"""
REST API: Student Management Endpoints (/api/v1/students)
"""

from flask import Blueprint, request, jsonify
from backend.services.student_service import StudentService
from backend.middleware.auth_middleware import api_auth_required, api_role_required
from backend.core.exceptions import (
    NotFoundError, DuplicateResourceError, AuthorizationError,
    IDORViolationError, ValidationError
)

student_api_bp = Blueprint("student_api", __name__, url_prefix="/api/v1/students")

@student_api_bp.route("", methods=["GET"])
@api_auth_required
def list_students(user):
    course = request.args.get("course")
    placement_status = request.args.get("placement_status")
    reg_status = request.args.get("registration_status")
    search = request.args.get("q")

    try:
        students = StudentService.list_students(
            current_user=user,
            course=course,
            placement_status=placement_status,
            registration_status=reg_status,
            search=search
        )
        return jsonify({"count": len(students), "students": students}), 200
    except AuthorizationError as e:
        return jsonify({"error": "Forbidden", "message": str(e)}), 403

@student_api_bp.route("/<int:id>", methods=["GET"])
@api_auth_required
def get_student(user, id):
    try:
        student = StudentService.get_student(id, user)
        return jsonify(student), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
    except (AuthorizationError, IDORViolationError) as e:
        return jsonify({"error": "Forbidden", "message": str(e)}), 403

@student_api_bp.route("", methods=["POST"])
@api_role_required("Placement Administrator", "Placement Officer")
def create_student(user):
    data = request.get_json() or {}
    try:
        s_id = StudentService.create_student(data, user)
        return jsonify({"status": "success", "id": s_id, "message": "Student created successfully."}), 201
    except DuplicateResourceError as e:
        return jsonify({"error": "Conflict", "message": str(e)}), 409
    except ValidationError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

@student_api_bp.route("/<int:id>", methods=["PUT"])
@api_auth_required
def update_student(user, id):
    data = request.get_json() or {}
    try:
        StudentService.update_student(id, data, user)
        return jsonify({"status": "success", "message": "Student record updated."}), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
    except AuthorizationError as e:
        return jsonify({"error": "Forbidden", "message": str(e)}), 403
    except ValidationError as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

@student_api_bp.route("/<int:id>", methods=["DELETE"])
@api_role_required("Placement Administrator")
def archive_student(user, id):
    try:
        StudentService.archive_student(id, user)
        return jsonify({"status": "success", "message": "Student record archived."}), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
