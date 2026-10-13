-- NFSU Secure, Policy-Driven Student Placement Management System
-- Database Schema for 2026-27 Placement Session
-- Forensic-Grade Audit-Enabled Relational Schema

PRAGMA foreign_keys = ON;

-- 1. Users & RBAC
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('Placement Administrator', 'Placement Officer', 'Course Coordinator', 'Recruiter', 'Student')),
    assigned_course TEXT NULL, -- Course Coordinator scope
    recruiter_company TEXT NULL, -- Recruiter scope
    student_id INTEGER NULL, -- Student self-service link
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until DATETIME NULL,
    mfa_secret TEXT NULL,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE SET NULL
);

-- 2. Students Master Table
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id TEXT UNIQUE NOT NULL,
    student_name TEXT NOT NULL,
    mobile_number TEXT NOT NULL,
    email_id TEXT UNIQUE NOT NULL,
    course TEXT NOT NULL CHECK(course IN (
        'M.Tech. Computer Science (M.Tech. CS)',
        'M.Tech. Artificial Intelligence and Data Science (M.Tech. AIDS)',
        'B.Tech.–M.Tech. Computer Science and Engineering (CS)',
        'M.Sc. Computer Science (M.Sc. CS)',
        'M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)'
    )),
    batch TEXT NOT NULL,
    cgpa REAL NOT NULL DEFAULT 0.0 CHECK(cgpa >= 0.0 AND cgpa <= 10.0),
    active_backlogs INTEGER NOT NULL DEFAULT 0 CHECK(active_backlogs >= 0),
    registration_status TEXT NOT NULL DEFAULT 'Registered' CHECK(registration_status IN ('Registered', 'Deregistered', 'Not Registered')),
    eligibility_status TEXT NOT NULL DEFAULT 'Eligible' CHECK(eligibility_status IN ('Eligible', 'Ineligible', 'Pending Verification')),
    placement_status TEXT NOT NULL DEFAULT 'Unplaced' CHECK(placement_status IN ('Unplaced', 'Internship Only', 'FTE Only', 'Internship + PPO/FTE')),
    absenteeism_count INTEGER NOT NULL DEFAULT 0 CHECK(absenteeism_count >= 0),
    absenteeism_penalty_drives_remaining INTEGER NOT NULL DEFAULT 0 CHECK(absenteeism_penalty_drives_remaining >= 0),
    is_archived INTEGER NOT NULL DEFAULT 0 CHECK(is_archived IN (0, 1)),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Recruitment Drives
CREATE TABLE IF NOT EXISTS drives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drive_code TEXT UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('A+', 'A', 'B', 'C')),
    offer_type TEXT NOT NULL CHECK(offer_type IN ('I', 'F', 'I+F')),
    stipend_amount REAL DEFAULT 0.0,
    stipend_period TEXT DEFAULT 'Per Month',
    fte_package_ctc REAL DEFAULT 0.0 CHECK(fte_package_ctc >= 0.0), -- Annual LPA
    min_cgpa REAL DEFAULT 6.0,
    max_backlogs INTEGER DEFAULT 0,
    eligible_courses TEXT NOT NULL, -- JSON array or comma separated
    acceptance_deadline_hours INTEGER DEFAULT 24,
    drive_date DATE NOT NULL,
    status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Completed', 'Cancelled')),
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. Drive Attendance & Absenteeism Tracking
CREATE TABLE IF NOT EXISTS drive_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drive_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL CHECK(activity_type IN ('Pre-Placement Talk', 'Aptitude/Tech Test', 'Technical Interview', 'HR Interview')),
    attendance_status TEXT NOT NULL CHECK(attendance_status IN ('Present', 'Absent', 'Excused Emergency')),
    remarks TEXT NULL,
    recorded_by TEXT NOT NULL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(drive_id) REFERENCES drives(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- 5. Offers (Preserving Full Placement History)
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    drive_id INTEGER NULL,
    company_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('A+', 'A', 'B', 'C')),
    offer_type TEXT NOT NULL CHECK(offer_type IN ('I', 'F', 'I+F')),
    stipend_amount REAL DEFAULT 0.0,
    stipend_period TEXT NULL,
    fte_package_ctc REAL DEFAULT 0.0, -- in LPA
    is_ppo INTEGER DEFAULT 0 CHECK(is_ppo IN (0, 1)),
    ppo_status TEXT DEFAULT 'Not Applicable' CHECK(ppo_status IN ('Not Applicable', 'Pending', 'Offered', 'Accepted', 'Declined')),
    offer_acceptance TEXT DEFAULT 'Pending' CHECK(offer_acceptance IN ('Pending', 'Accepted', 'Declined', 'Expired')),
    deadline_at DATETIME NOT NULL,
    joining_status TEXT DEFAULT 'Pending' CHECK(joining_status IN ('Pending', 'Joined', 'Not Joined')),
    offer_date DATE NOT NULL,
    is_off_campus INTEGER DEFAULT 0 CHECK(is_off_campus IN (0, 1)),
    noc_status TEXT DEFAULT 'Not Required' CHECK(noc_status IN ('Not Required', 'Applied', 'Approved', 'Rejected')),
    remarks TEXT NULL,
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(drive_id) REFERENCES drives(id) ON DELETE SET NULL
);

-- 6. Policy Exceptions & Administrative Disciplinary Overrides
CREATE TABLE IF NOT EXISTS policy_exceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    drive_id INTEGER NULL,
    exception_type TEXT NOT NULL CHECK(exception_type IN ('Absenteeism Waiver', 'Switching Rule Override', 'Eligibility Waiver', 'Deadline Extension')),
    justification TEXT NOT NULL,
    status TEXT DEFAULT 'Approved' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
    approved_by TEXT NOT NULL,
    approved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(drive_id) REFERENCES drives(id) ON DELETE SET NULL
);

-- 7. Policy Evaluation Cache & Audit
CREATE TABLE IF NOT EXISTS policy_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    drive_id INTEGER NULL,
    decision TEXT NOT NULL CHECK(decision IN ('Allowed', 'Blocked', 'Referred for Manual Review')),
    reasons TEXT NOT NULL, -- JSON formatted explanation steps
    evaluated_by TEXT NOT NULL,
    evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(drive_id) REFERENCES drives(id) ON DELETE SET NULL
);

-- 8. Forensic Tamper-Evident Cryptographic Audit Log
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    actor_username TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NULL,
    details TEXT NOT NULL,
    before_state TEXT NULL,
    after_state TEXT NULL,
    ip_address TEXT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL
);

-- Indexes for performance & security queries
CREATE INDEX IF NOT EXISTS idx_students_course ON students(course);
CREATE INDEX IF NOT EXISTS idx_students_placement_status ON students(placement_status);
CREATE INDEX IF NOT EXISTS idx_students_placement_id ON students(placement_id);
CREATE INDEX IF NOT EXISTS idx_offers_student_id ON offers(student_id);
CREATE INDEX IF NOT EXISTS idx_offers_acceptance ON offers(offer_acceptance);
CREATE INDEX IF NOT EXISTS idx_drives_status ON drives(status);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
