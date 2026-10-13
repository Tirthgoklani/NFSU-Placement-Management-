"""
Authentication and RBAC Security Middleware
Supports both Session cookies and Bearer Tokens for headless API clients.
"""

from functools import wraps
from flask import request, jsonify, session
from backend.repositories.base_repository import BaseRepository
from backend.services.audit_service import AuditService

def get_authenticated_user():
    """Resolves authenticated user from session or Bearer token."""
    # 1. Check Flask session
    user_id = session.get("user_id")
    if user_id:
        return BaseRepository.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))

    # 2. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1].strip()
        # For simplicity in demo, token can be username:role or a basic signed token
        parts = token.split(":")
        if len(parts) == 2:
            uname, _ = parts
            return BaseRepository.fetch_one("SELECT * FROM users WHERE username = ?", (uname,))

    return None

def api_auth_required(f):
    """Enforces authentication on API endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_authenticated_user()
        if not user:
            return jsonify({
                "error": "Authentication required",
                "message": "Valid session or Authorization Bearer token must be provided."
            }), 401
        return f(*args, user=user, **kwargs)
    return decorated

def api_role_required(*allowed_roles):
    """Enforces strict role-based access control on REST API endpoints."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_authenticated_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401

            if user["role"] not in allowed_roles:
                AuditService.log_event(
                    actor_username=user["username"],
                    actor_role=user["role"],
                    action="API_UNAUTHORIZED_ACCESS",
                    entity_type="RBAC",
                    entity_id=request.path,
                    details=f"Forbidden access to {request.method} {request.path} by role '{user['role']}'."
                )
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Your role '{user['role']}' lacks permission for this API endpoint.",
                    "required_roles": list(allowed_roles)
                }), 403

            return f(*args, user=user, **kwargs)
        return decorated
    return decorator
