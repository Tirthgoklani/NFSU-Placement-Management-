# National Forensic Sciences University (NFSU)
## Secure, Policy-Driven Student Placement Management System (Session 2026–27)

A centralized, forensic-grade, policy-driven web application designed for the **Placement Cell of NFSU** to maintain course-wise student placement records, automate recruitment policy compliance, prevent unauthorized data manipulation, protect candidate privacy, and generate institutional placement statistics.

---

### Table of Contents
1. [Programmes Covered](#1-programmes-covered)
2. [Core Architecture & Tech Stack](#2-core-architecture--tech-stack)
3. [Database Schema & Data Model](#3-database-schema--data-model)
4. [NFSU Placement Guidelines 2026–27 Policy Rule Engine](#4-nfsu-placement-guidelines-202627-policy-rule-engine)
5. [Cybersecurity & Privacy Controls](#5-cybersecurity--privacy-controls)
6. [Role-Based Access Control (RBAC)](#6-role-based-access-control-rbac)
7. [Automated Verification & Test Suite](#7-automated-verification--test-suite)
8. [Installation & Quick Start Guide](#8-installation--quick-start-guide)
9. [Pre-Configured Accounts for Demonstration](#9-pre-configured-accounts-for-demonstration)
10. [System Limitations & Roadmap](#10-system-limitations--roadmap)

---

### 1. Programmes Covered
The system supports the designated academic programmes under the School of Cybersecurity & Digital Forensics / Department of Computer Science:
1. **M.Tech. Computer Science (M.Tech. CS)**
2. **M.Tech. Artificial Intelligence and Data Science (M.Tech. AIDS)**
3. **B.Tech.–M.Tech. Computer Science and Engineering (CS)** *(Integrated Dual Degree)*
4. **M.Sc. Computer Science (M.Sc. CS)**
5. **M.Sc. Digital Forensics and Information Security (M.Sc. DFIS)**

---

### 2. Core Architecture & Tech Stack

```
+-----------------------------------------------------------------------------------+
|                            Presentation Layer (HTML5, Tailwind, Chart.js)          |
|  - Forensic Evaluation Bar  - Course Tabs  - Policy Simulator  - Audit Blockchain  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        Application Controllers & Blueprints (Flask)                |
|  - Auth & RBAC     - Students API     - Recruitment Drives    - Offer Lifecycle   |
|  - Policy Engine   - Audit Log Trail  - Backup / Disaster Recovery                |
+-----------------------------------------------------------------------------------+
                     |                                       |
                     v                                       v
+---------------------------------------+   +---------------------------------------+
|  NFSU 2026-27 Policy Rule Engine      |   |   Forensic Security Subsystem         |
|  - CTC Classification (A+, A, B, C)   |   |   - Cryptographic Hash Chaining       |
|  - 1.5x Switching Multiplier          |   |   - Field Privacy Masking (Phone/CTC) |
|  - Offer-Type Restrictions (I, F, I+F)|   |   - Account Lockout Defense (5 fails) |
|  - 3-Drive Absenteeism Penalty        |   |   - In-Transit / At-Rest Encryption   |
|  - 24h Acceptance Deadline Tracker    |   |   - Strict IDOR Defense Boundaries    |
+---------------------------------------+   +---------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                       Data Persistence Layer (SQLite3 WAL Mode)                   |
|  - Parameterized Queries (? placeholders)  - Foreign Key Constraints              |
|  - Preserved Event History (Offers, Attendance, Waivers, Cryptographic Logs)      |
+-----------------------------------------------------------------------------------+
```

- **Backend**: Python 3.13 + Flask 3.1.2
- **Database**: SQLite3 with Write-Ahead Logging (WAL) and strict foreign key integrity
- **Security Engine**: Fernet field-level cryptography, PBKDF2/scrypt password salting, SHA-256 blockchain hash chaining
- **Frontend**: Responsive Tailwind CSS, Chart.js interactive visualizations, FontAwesome 6 icons

---

### 3. Database Schema & Data Model

The schema is formally defined in `models/schema.sql` and includes:
- `users`: User authentication, roles, department scope, failed attempt counters, lockout timestamps.
- `students`: Core candidate profile, unique `placement_id`, CGPA, active backlogs, registration status (`Registered`, `Deregistered`, `Not Registered`), institutional eligibility (`Eligible`, `Ineligible`, `Pending Verification`), canonical placement status (`Unplaced`, `Internship Only`, `FTE Only`, `Internship + PPO/FTE`), absenteeism penalty counter.
- `drives`: Recruitment drives, company name, CTC category (`A+`, `A`, `B`, `C`), offer classification (`I`, `F`, `I+F`), stipend, eligibility criteria, 24-hour deadline configuration.
- `drive_attendance`: Activity rounds (Pre-Placement Talk, Online Test, Technical Interview, HR Interview), attendance status (`Present`, `Absent`, `Excused Emergency`), automated 3-drive penalty trigger.
- `offers`: **Preserves full placement history** across multiple offers without overwriting prior events. Fields: student ID, drive ID, company, category, offer type, stipend amount/period, annual CTC (LPA), PPO status, acceptance status (`Pending`, `Accepted`, `Declined`, `Expired`), 24h deadline timestamp, joining status, NOC status.
- `policy_exceptions`: Administrative waivers (`Absenteeism Waiver`, `Switching Rule Override`, `Eligibility Waiver`) with justification and approving authority.
- `audit_logs`: Tamper-evident forensic audit ledger with `previous_hash` and `record_hash` (SHA-256).

---

### 4. NFSU Placement Guidelines 2026–27 Policy Rule Engine

The policy rule engine is implemented in `policy_engine.py` and strictly enforces:

#### 4.1 Company Category & CTC Classification
| Category | CTC / Package Range | Institutional Switching Rule |
| :---: | :---: | :--- |
| **A+** | **≥ ₹16.0 LPA** | **No switching permitted.** Candidates selected in Category A+ are completely out of the campus placement process. |
| **A** | **₹10.0 – ₹16.0 LPA** | **Switching permitted ONLY to Category A+ companies (≥ ₹16 LPA).** Lateral moves within Category A or downgrades to B/C are blocked. |
| **B** | **₹6.0 – ₹10.0 LPA** | Further placement permitted **ONLY if the new package is at least 1.5 times the existing package** ($CTC_{new} \ge 1.5 \times CTC_{existing}$). |
| **C** | **&lt; ₹6.0 LPA** | Eligible for higher-category opportunities (Category B, A, or A+). Lateral switching within Category C is blocked. |

#### 4.2 Offer-Type Restrictions
- **Internship only (I)**: After selection for an internship, the student *cannot* apply for another internship-only role. However, they *may* apply for FTE (`F`) or `I+F` roles across categories.
- **FTE only (F)**: After selection for FTE, candidate *cannot* apply for another lateral FTE-only role unless qualifying under category switching rules. Candidate *may* apply for an internship role if required for academic credit.
- **Internship + PPO/FTE (I+F)**: After selection, the candidate *cannot* participate in any other `I`, `F`, or `I+F` recruitment drives at another organization.

#### 4.3 Attendance, Deadlines & Compliance
- **Absenteeism Penalty**: Unexcused absence from any mandatory recruitment activity (PPT, Test, Interview) automatically flags the student and triggers an exclusion from the **next 3 recruitment drives**. Emergency exceptions can be waived only by the Placement Administrator.
- **24-Hour Offer Acceptance Deadline**: Tracked in real time. Offers not accepted within 24 hours (or company deadline) lapse and are flagged.
- **Separate Reporting of Stipend vs. CTC**: Internship stipends (INR/month) and annual FTE CTC (LPA) are reported in separate metrics and charts.
- **Unique Placed Students vs. Total Offers**: Distinct placed individuals are counted separately from total offers received.

---

### 5. Cybersecurity & Privacy Controls

1. **Tamper-Evident SHA-256 Audit Blockchain**:
   - Every state-modifying action computes:
     $$\text{record\_hash} = \text{SHA256}(\text{timestamp} \parallel \text{actor} \parallel \text{role} \parallel \text{action} \parallel \text{entity} \parallel \text{details} \parallel \text{before} \parallel \text{after} \parallel \text{previous\_hash})$$
   - Genesis hash: `0000000000000000000000000000000000000000000000000000000000000000`
   - Built-in blockchain validator (`/audit/verify`) traverses the entire log sequence and flags any unauthorized row modifications or record deletions.
2. **Insecure Direct Object Reference (IDOR) Defense**:
   - Students can only view their own record (`/students/<own_id>`).
   - Attempting to inspect another student's profile or parameters immediately aborts with `HTTP 403 Forbidden` and logs a security incident.
3. **Data Masking & Privacy Controls**:
   - Mobile numbers and email addresses are automatically masked (e.g., `+91 98*****001`, `r***t@nfsu.ac.in`) for restricted roles. Only Placement Administrators and Officers view unmasked contact details.
4. **SQL Injection Resistance**:
   - 100% of queries use parameterized prepared statements (`?` parameter binding) to eliminate SQL injection vulnerabilities.
5. **Cross-Site Scripting (XSS) Prevention**:
   - Jinja2 auto-escaping on all user inputs, coupled with strict HTTP response security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection: 1; mode=block`).
6. **Brute-Force Protection & Account Lockout**:
   - Accounts are locked for 15 minutes after 5 consecutive failed login attempts.
7. **Disaster Recovery**:
   - Online hot-backup API via SQLite backup interface with point-in-time restoration.

---

### 6. Role-Based Access Control (RBAC)

| Permission / Action | Placement Administrator | Placement Officer | Course Coordinator | Recruiter | Student |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **View Executive Dashboard** | Yes | Yes | Yes | Yes | Yes |
| **Browse Master Student Roster** | Yes | Yes | Scoped to Department | Blocked | Blocked (Self Only) |
| **Create / Edit Student Records** | Yes | Yes | Eligibility Only | Blocked | Blocked |
| **Schedule Recruitment Drives** | Yes | Yes | Blocked | Blocked | Blocked |
| **Record Round Attendance** | Yes | Yes | Blocked | Blocked | Blocked |
| **Issue / Record Offers** | Yes | Yes | Blocked | Company Only | Blocked |
| **Accept / Decline Offer** | Yes | Yes | Blocked | Blocked | Own Offer Only |
| **Grant Policy Waivers / Overrides**| Yes | Blocked | Blocked | Blocked | Blocked |
| **Export Roster / Reports to CSV** | Yes | Yes | Blocked | Blocked | Blocked |
| **Inspect Cryptographic Audit Log** | Yes | Blocked | Blocked | Blocked | Blocked |
| **Trigger Database Backup** | Yes | Blocked | Blocked | Blocked | Blocked |

---

### 7. Automated Verification & Test Suite

The test suite contains **33 automated unit and integration tests** across three test modules:

1. `tests/test_policy_engine.py` (20 Tests):
   - Category A+, A, B, C classifications.
   - A+ lockout rule (out of placement process).
   - Category A to A+ exclusive upgrade rule.
   - Category B 1.5x multiplier validation ($CTC_{new} \ge 1.5 \times CTC_{existing}$).
   - Category C lateral switch prohibition.
   - Internship-only restriction (cannot apply for another `I`).
   - `I+F` multi-offer lockout.
   - Attendance penalty exclusion (3-drive block).
   - Academic criteria (CGPA threshold, backlogs, programme match).

2. `tests/test_security_rbac.py` (9 Tests):
   - RBAC boundary enforcement across all 5 roles.
   - Student IDOR attack prevention.
   - Tamper defense (student blocked from modifying placement status/CTC).
   - Course coordinator departmental scope isolation.
   - Recruiter drive isolation.
   - Brute-force account lockout after 5 failed attempts.
   - Cryptographic blockchain audit integrity verification & tamper detection.
   - SQL injection resistance (parameterization defense).

3. `tests/test_api_workflows.py` (4 Tests):
   - Student creation and Placement ID duplicate rejection.
   - Drive creation with auto-classification of categories.
   - Absenteeism penalty application (3 drives) and administrative waiver reset.
   - Separate calculation and reporting of unique placed candidates vs total offers, and FTE CTC vs stipends.

4. `tests/test_secure_backend.py` (7 Tests):
   - AES-256-GCM AEAD authenticated encryption and decryption.
   - Nonce randomness and ciphertext tamper rejection.
   - RFC 6238 TOTP Multi-Factor Authentication code generation and verification.
   - REST API v1 authentication endpoints with Bearer token issuance.
   - REST API schema validation rejecting invalid programmes and malformed Placement IDs.
   - REST API Student IDOR defense (HTTP 403 on accessing other profiles).
   - REST API Policy Rule Engine live evaluation and blockchain integrity verification.

#### Running the Test Suite:
```powershell
python -m unittest discover tests
```
*Result: 40 tests passing with 0 failures, 0 errors.*

---

### 8. Enterprise Secure REST API Reference (`/api/v1`)

The backend exposes a decoupled, enterprise RESTful API for client apps, mobile portals, and ERP integrations:

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/auth/login` | None | Authenticate with credentials & optional TOTP MFA; returns Bearer token |
| `POST` | `/api/v1/auth/mfa/setup` | User | Generates RFC 6238 TOTP Base32 secret and `otpauth://` URI |
| `POST` | `/api/v1/auth/mfa/verify` | User | Validates 6-digit TOTP code |
| `GET` | `/api/v1/auth/me` | User | Current user profile, role, and departmental scope |
| `GET` | `/api/v1/students` | Staff | List candidates with query filters and privacy masking |
| `POST` | `/api/v1/students` | Admin, Officer | Create candidate with schema and duplicate checks |
| `GET` | `/api/v1/students/<id>` | IDOR Protected | Get candidate profile (candidate restricted to self) |
| `PUT` | `/api/v1/students/<id>` | Staff | Update candidate academic info (students blocked from tampering) |
| `DELETE` | `/api/v1/students/<id>` | Admin | Soft-archive candidate record |
| `GET` | `/api/v1/drives` | Authenticated | List recruitment drives (recruiters scoped to own company) |
| `POST` | `/api/v1/drives` | Admin, Officer | Schedule drive with auto-category classification |
| `POST` | `/api/v1/drives/<id>/attendance` | Admin, Officer | Record attendance round; unexcused absence triggers 3-drive penalty |
| `GET` | `/api/v1/offers` | Authenticated | List offers with 24-hour deadline tracking |
| `POST` | `/api/v1/offers` | Admin, Officer, Recruiter | Issue offer with pre-evaluation policy gate |
| `POST` | `/api/v1/offers/<id>/status` | Authorized | Accept/Decline offer; acceptance dynamically updates candidate status |
| `POST` | `/api/v1/offers/<id>/ppo` | Admin, Officer | Convert internship to Pre-Placement Offer (PPO) |
| `POST` | `/api/v1/policy/evaluate` | Authenticated | Run live policy rule check with step-by-step transparency |
| `POST` | `/api/v1/policy/waivers` | Admin | Grant administrative waiver (resets absenteeism penalties) |
| `GET` | `/api/v1/audit/logs` | Admin | Query tamper-evident audit ledger |
| `POST` | `/api/v1/audit/verify` | Admin | Run cryptographic blockchain ledger verification |
| `POST` | `/api/v1/audit/backup` | Admin | Trigger online database backup snapshot |

---

### 8. Installation & Quick Start Guide

#### Prerequisites
- Python 3.10 or higher (Tested on Python 3.13.1)
- Modern web browser (Chrome, Edge, Firefox)

#### Step 1: Clone or Navigate to Project Directory
```powershell
cd C:\Users\Mansi\.gemini\antigravity\scratch\nfsu_placement_system
```

#### Step 2: Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

#### Step 3: Seed Database with Realistic NFSU 2026-27 Data
```powershell
python seed_data.py
```

#### Step 4: Launch Web Application
```powershell
python app.py
```
Open your browser and visit: `http://127.0.0.1:5000`

---

### 9. Pre-Configured Accounts for Demonstration

The portal features a **top-bar Quick Role Switcher** allowing evaluation of any persona in one click. Alternatively, sign in using these pre-configured credentials:

| Role | Username | Password | Persona & Scope |
| :--- | :--- | :--- | :--- |
| **Placement Administrator** | `admin` | `Admin@NFSU2026!` | Full administrative control, waivers, audit blockchain, backups |
| **Placement Officer** | `officer` | `Officer@NFSU2026!` | Operations, drives, attendance, offer records |
| **Course Coordinator (DFIS)** | `coord_dfis` | `Coord@NFSU2026!` | Scoped to M.Sc. Digital Forensics and Information Security |
| **Course Coordinator (CS)** | `coord_cs` | `Coord@NFSU2026!` | Scoped to M.Tech. Computer Science |
| **Recruiter** | `recruiter_crowdstrike` | `Recruiter@NFSU2026!` | Scoped to CrowdStrike Cybersecurity recruitment drives |
| **Student (Category A+ Placed)** | `student_rohit` | `Student@NFSU2026!` | Rohit Sharma (Placed in Microsoft ₹26.5 LPA - out of placement process) |
| **Student (Internship Only)** | `student_ananya` | `Student@NFSU2026!` | Ananya Mishra (Placed in CERT-In ₹45,000/mo - eligible for FTE/I+F) |
| **Student (Category B Placed)** | `student_vikram` | `Student@NFSU2026!` | Vikram Rathore (Placed in Quick Heal ₹8.5 LPA - eligible for ≥ 12.75 LPA) |
| **Student (Unplaced)** | `student_sneha` | `Student@NFSU2026!` | Sneha Kulkarni (B.Tech-M.Tech CS - unplaced, fully eligible) |
| **Student (Absenteeism Flagged)**| `student_arjun` | `Student@NFSU2026!` | Arjun Pandey (M.Sc. CS - 2 penalty drives remaining) |

---

### 10. System Limitations & Roadmap

- **Multi-Factor Authentication (MFA)**: TOTP key infrastructure and seed secret storage is pre-built in `models/schema.sql`; SMS OTP integration can be connected with an institutional SMS gateway (e.g., NIC / CDAC SMS gateway).
- **ERP Integration**: Designed with clean REST JSON endpoints to easily interface with NFSU's central student management ERP for automated CGPA and backlog synchronization.
- **Digital Signatures**: Audit records are currently signed via SHA-256 cryptographic chaining; future enhancements can incorporate X.509 institutional digital certificates for non-repudiation.
