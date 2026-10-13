"""
Forensic Audit Log & Database Backup/Recovery Routes
Provides tamper-evident blockchain log inspection, live cryptographic verification,
and encrypted snapshot backup/restore management.
"""

from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from database import query_db, backup_database, restore_database
from security import (
    login_required, role_required, get_current_user,
    log_audit_event, verify_audit_log_integrity
)
from config import BACKUP_DIR

audit_bp = Blueprint("audit", __name__)

@audit_bp.route("/audit")
@login_required
@role_required("Placement Administrator")
def view_audit_logs():
    current_user = get_current_user()
    action_filter = request.args.get("action", "all")
    actor_filter = request.args.get("actor", "").strip()

    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []

    if action_filter != "all":
        query += " AND action = ?"
        params.append(action_filter)

    if actor_filter:
        query += " AND actor_username LIKE ?"
        params.append(f"%{actor_filter}%")

    query += " ORDER BY id DESC LIMIT 100"
    logs = query_db(query, tuple(params))

    # Available distinct actions for dropdown
    actions = query_db("SELECT DISTINCT action FROM audit_logs ORDER BY action")

    return render_template(
        "audit_logs.html",
        logs=logs,
        actions=[a["action"] for a in actions],
        action_filter=action_filter,
        actor_filter=actor_filter,
        current_user=current_user
    )

@audit_bp.route("/audit/verify", methods=["GET", "POST"])
@login_required
@role_required("Placement Administrator")
def verify_audit():
    result = verify_audit_log_integrity()
    if result["is_valid"]:
        flash(f"Verification Succeeded: {result['message']}", "success")
    else:
        flash(f"CRITICAL FORENSIC ALERT: {result['message']}", "danger")
    return redirect(url_for("audit.view_audit_logs"))

@audit_bp.route("/backup")
@login_required
@role_required("Placement Administrator")
def backup_management():
    current_user = get_current_user()
    
    # List backups on disk
    backup_files = []
    if BACKUP_DIR.exists():
        for f in BACKUP_DIR.glob("*.db"):
            backup_files.append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 2),
                "modified": f.stat().st_mtime,
                "path": str(f)
            })
    backup_files.sort(key=lambda x: x["modified"], reverse=True)

    return render_template("backup.html", backups=backup_files, current_user=current_user)

@audit_bp.route("/backup/create", methods=["POST"])
@login_required
@role_required("Placement Administrator")
def trigger_backup():
    try:
        backup_path = backup_database()
        fname = Path(backup_path).name
        log_audit_event(
            actor_username=session["username"],
            actor_role=session["role"],
            action="DATABASE_BACKUP_CREATED",
            entity_type="Backup",
            entity_id=fname,
            details=f"Created online database backup snapshot '{fname}'."
        )
        flash(f"Database backup created: {fname}", "success")
    except Exception as e:
        flash(f"Backup failed: {str(e)}", "danger")

    return redirect(url_for("audit.backup_management"))

@audit_bp.route("/backup/download/<filename>")
@login_required
@role_required("Placement Administrator")
def download_backup(filename):
    file_path = BACKUP_DIR / filename
    if not file_path.exists():
        flash("Backup file not found.", "danger")
        return redirect(url_for("audit.backup_management"))

    log_audit_event(
        actor_username=session["username"],
        actor_role=session["role"],
        action="BACKUP_DOWNLOADED",
        entity_type="Backup",
        entity_id=filename,
        details=f"Downloaded backup snapshot '{filename}'."
    )
    return send_file(file_path, as_attachment=True)
