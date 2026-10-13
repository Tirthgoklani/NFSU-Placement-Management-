"""
Authentication & Session Management Routes
Implements secure login, brute-force lockout, role switching for testing, and profile view.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import query_db, execute_db
from security import (
    verify_password, check_account_locked, record_failed_login, reset_failed_logins,
    log_audit_event, login_required
)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if not user:
            flash("Invalid credentials provided.", "danger")
            log_audit_event("ANONYMOUS", "UNAUTHENTICATED", "LOGIN_FAILED", "Auth", username, "Username not found.")
            return render_template("login.html")

        # Check account lockout
        is_locked, minutes = check_account_locked(user)
        if is_locked:
            flash(f"Account locked due to excessive failed attempts. Try again in {minutes} minute(s).", "danger")
            return render_template("login.html")

        # Verify password
        if not verify_password(password, user["password_hash"]):
            record_failed_login(username)
            flash("Invalid credentials provided.", "danger")
            return render_template("login.html")

        # Success - reset failed logins
        reset_failed_logins(user["id"])
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["assigned_course"] = user["assigned_course"]
        session["recruiter_company"] = user["recruiter_company"]
        session["student_id"] = user["student_id"]

        log_audit_event(
            actor_username=user["username"],
            actor_role=user["role"],
            action="LOGIN_SUCCESS",
            entity_type="Auth",
            entity_id=str(user["id"]),
            details=f"User {user['username']} logged in successfully with role '{user['role']}'."
        )

        flash(f"Welcome, {user['username']} ({user['role']})!", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("report.dashboard"))

    return render_template("login.html")

@auth_bp.route("/quick_switch/<role_name>", methods=["POST"])
def quick_switch(role_name):
    """
    Demo/Evaluation utility: Immediately switches active session to a designated role
    account to allow full multi-role testing of RBAC policies.
    """
    role_map = {
        "admin": "admin",
        "officer": "officer",
        "coord_dfis": "coord_dfis",
        "coord_cs": "coord_cs",
        "recruiter": "recruiter_crowdstrike",
        "student_rohit": "student_rohit",
        "student_ananya": "student_ananya",
        "student_vikram": "student_vikram",
        "student_sneha": "student_sneha",
        "student_arjun": "student_arjun"
    }

    target_user = role_map.get(role_name, "admin")
    user = query_db("SELECT * FROM users WHERE username = ?", (target_user,), one=True)
    if user:
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["assigned_course"] = user["assigned_course"]
        session["recruiter_company"] = user["recruiter_company"]
        session["student_id"] = user["student_id"]

        log_audit_event(
            actor_username=user["username"],
            actor_role=user["role"],
            action="ROLE_QUICK_SWITCH",
            entity_type="Auth",
            entity_id=str(user["id"]),
            details=f"Quick switched active session to '{user['username']}' ({user['role']})."
        )
        flash(f"Switched session to {user['username']} ({user['role']}).", "info")
    
    return redirect(request.referrer or url_for("report.dashboard"))

@auth_bp.route("/logout")
def logout():
    uname = session.get("username", "ANONYMOUS")
    role = session.get("role", "UNKNOWN")
    log_audit_event(uname, role, "LOGOUT", "Auth", session.get("user_id"), f"User {uname} logged out.")
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/profile")
@login_required
def profile():
    user = query_db("SELECT * FROM users WHERE id = ?", (session["user_id"],), one=True)
    student_record = None
    if user["student_id"]:
        student_record = query_db("SELECT * FROM students WHERE id = ?", (user["student_id"],), one=True)
    return render_template("profile.html", user=user, student=student_record)
