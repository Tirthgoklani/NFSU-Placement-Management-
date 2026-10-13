"""
NFSU Placement Management System 2026-27
Main Application Entrypoint
"""

from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session
from config import SECRET_KEY
from database import init_db
from routes.auth_routes import auth_bp
from routes.student_routes import student_bp
from routes.drive_routes import drive_bp
from routes.offer_routes import offer_bp
from routes.policy_routes import policy_bp
from routes.report_routes import report_bp
from routes.audit_routes import audit_bp

# Enterprise Secure REST API v1 Blueprints
from backend.api.v1.auth_api import auth_api_bp
from backend.api.v1.student_api import student_api_bp
from backend.api.v1.drive_api import drive_api_bp
from backend.api.v1.offer_api import offer_api_bp
from backend.api.v1.policy_api import policy_api_bp
from backend.api.v1.audit_api import audit_api_bp

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Register Web Portal Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(drive_bp)
    app.register_blueprint(offer_bp)
    app.register_blueprint(policy_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(audit_bp)

    # Register Enterprise REST API v1 Blueprints
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(student_api_bp)
    app.register_blueprint(drive_api_bp)
    app.register_blueprint(offer_api_bp)
    app.register_blueprint(policy_api_bp)
    app.register_blueprint(audit_api_bp)

    # Initialize Database Schema if not exists
    with app.app_context():
        init_db()

    # Template Filters
    @app.template_filter("currency_inr")
    def currency_inr(val):
        try:
            return f"₹{float(val):,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    @app.template_filter("format_lpa")
    def format_lpa(val):
        try:
            return f"₹{float(val):.2f} LPA"
        except (ValueError, TypeError):
            return "₹0.00 LPA"

    @app.template_filter("datetime_fmt")
    def datetime_fmt(val):
        if not val:
            return "N/A"
        try:
            dt = datetime.fromisoformat(str(val))
            return dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            return str(val)[:19]

    # Context Processor for Global Template Variables
    @app.context_processor
    def inject_globals():
        return {
            "current_year": "2026-27",
            "system_name": "NFSU Placement Portal",
            "session_user": session.get("username"),
            "session_role": session.get("role")
        }

    # Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", error_code=403, error_message="Forbidden: You do not have permission to access this resource under NFSU placement policies."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", error_code=404, error_message="The requested resource was not found on this server."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", error_code=500, error_message="An internal server error occurred. This event has been noted for forensic review."), 500

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("report.dashboard"))
        return redirect(url_for("auth.login"))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
