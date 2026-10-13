"""
REST API: Offer Lifecycle Endpoints (/api/v1/offers)
"""

from flask import Blueprint, request, jsonify
from backend.services.offer_service import OfferService
from backend.repositories.offer_repository import OfferRepository
from backend.middleware.auth_middleware import api_auth_required, api_role_required
from backend.core.exceptions import (
    NotFoundError, AuthorizationError, PolicyConflictError, ValidationError
)

offer_api_bp = Blueprint("offer_api", __name__, url_prefix="/api/v1/offers")

@offer_api_bp.route("", methods=["GET"])
@api_auth_required
def list_offers(user):
    status = request.args.get("status")
    offer_type = request.args.get("offer_type")
    student_id = user.get("student_id") if user["role"] == "Student" else request.args.get("student_id")
    company = user.get("recruiter_company") if user["role"] == "Recruiter" else None

    offers = OfferRepository.list_offers(
        status=status,
        offer_type=offer_type,
        company_name=company,
        student_id=student_id
    )
    return jsonify({"count": len(offers), "offers": offers}), 200

@offer_api_bp.route("/<int:id>", methods=["GET"])
@api_auth_required
def get_offer(user, id):
    offer = OfferRepository.get_by_id(id)
    if not offer:
        return jsonify({"error": "Offer not found"}), 404
    if user["role"] == "Student" and user.get("student_id") != offer["student_id"]:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(offer), 200

@offer_api_bp.route("", methods=["POST"])
@api_auth_required
def record_offer(user):
    data = request.get_json() or {}
    try:
        offer_id = OfferService.record_offer(data, user)
        return jsonify({"status": "success", "id": offer_id, "message": "Offer recorded."}), 201
    except PolicyConflictError as e:
        return jsonify({"error": "Policy Conflict", "message": str(e)}), 422
    except AuthorizationError as e:
        return jsonify({"error": "Forbidden", "message": str(e)}), 403
    except (ValidationError, NotFoundError) as e:
        return jsonify({"error": "Bad Request", "message": str(e)}), 400

@offer_api_bp.route("/<int:id>/status", methods=["POST"])
@api_auth_required
def update_status(user, id):
    data = request.get_json() or {}
    new_status = data.get("status", "")
    try:
        OfferService.update_acceptance(id, new_status, user)
        return jsonify({"status": "success", "message": f"Offer marked as {new_status}."}), 200
    except AuthorizationError as e:
        return jsonify({"error": "Forbidden", "message": str(e)}), 403
    except (NotFoundError, ValidationError) as e:
        return jsonify({"error": str(e)}), 400

@offer_api_bp.route("/<int:id>/ppo", methods=["POST"])
@api_role_required("Placement Administrator", "Placement Officer")
def convert_ppo(user, id):
    data = request.get_json() or {}
    ppo_status = data.get("ppo_status", "Offered")
    ctc = float(data.get("fte_package_ctc", 0.0))
    try:
        OfferService.convert_to_ppo(id, ppo_status, ctc, user)
        return jsonify({"status": "success", "message": "PPO status updated."}), 200
    except NotFoundError as e:
        return jsonify({"error": "Not Found", "message": str(e)}), 404
