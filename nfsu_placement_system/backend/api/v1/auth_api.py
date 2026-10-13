"""
REST API: Authentication & MFA Endpoints (/api/v1/auth)
"""

from flask import Blueprint, request, jsonify, session
from backend.services.auth_service import AuthService
from backend.services.audit_service import AuditService
from backend.middleware.auth_middleware import api_auth_required
from backend.core.exceptions import AuthenticationError, AccountLockedError

auth_api_bp = Blueprint("auth_api", __name__, url_prefix="/api/v1/auth")

@auth_api_bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    mfa_code = data.get("mfa_code")

    try:
        user = AuthService.authenticate_user(username, password)
        
        # If user has MFA enabled, require TOTP code
        if user["mfa_secret"]:
            if not mfa_code:
                return jsonify({
                    "mfa_required": True,
                    "message": "Multi-factor authentication code required."
                }), 200
            AuthService.verify_totp_mfa(user["id"], mfa_code)

        # Establish session
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["assigned_course"] = user["assigned_course"]
        session["recruiter_company"] = user["recruiter_company"]
        session["student_id"] = user["student_id"]

        token = f"{user['username']}:{user['role']}"

        AuditService.log_event(
            actor_username=user["username"],
            actor_role=user["role"],
            action="API_LOGIN_SUCCESS",
            entity_type="Auth",
            entity_id=str(user["id"]),
            details=f"API authentication successful for {user['username']} ({user['role']})."
        )

        return jsonify({
            "status": "success",
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "assigned_course": user["assigned_course"],
                "recruiter_company": user["recruiter_company"],
                "student_id": user["student_id"]
            }
        }), 200

    except AccountLockedError as e:
        return jsonify({"error": "Account Locked", "message": str(e)}), 423
    except AuthenticationError as e:
        return jsonify({"error": "Unauthorized", "message": str(e)}), 401

@auth_api_bp.route("/mfa/setup", methods=["POST"])
@api_auth_required
def api_mfa_setup(user):
    secret, uri = AuthService.setup_totp_mfa(user["id"])
    return jsonify({
        "status": "success",
        "secret": secret,
        "otpauth_uri": uri,
        "message": "Enter this secret in Google Authenticator or scan the URI."
    }), 200

@auth_api_bp.route("/mfa/verify", methods=["POST"])
@api_auth_required
def api_mfa_verify(user):
    data = request.get_json() or {}
    code = data.get("code", "")
    try:
        AuthService.verify_totp_mfa(user["id"], code)
        return jsonify({"status": "success", "message": "MFA verified successfully."}), 200
    except AuthenticationError as e:
        return jsonify({"error": str(e)}), 401

@auth_api_bp.route("/me", methods=["GET"])
@api_auth_required
def api_me(user):
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "assigned_course": user["assigned_course"],
        "recruiter_company": user["recruiter_company"],
        "student_id": user["student_id"],
        "mfa_enabled": bool(user["mfa_secret"])
    }), 200
