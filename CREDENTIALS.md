# System Credentials & Access Reference

> **Security notice:** This file contains plaintext passwords for development and testing only.
> Do not commit this file to a public repository. Add `CREDENTIALS.md` to `.gitignore` for production deployments.

---

## Live Deployment

| Layer | URL / Host | Notes |
|---|---|---|
| Frontend | https://capstone-class-attendance-system-us.vercel.app | Vercel — built from `deploy-clean` branch |
| Backend | https://Shaunak2110-attendance-backend.hf.space | Hugging Face Spaces (Docker) |
| Backend health check | https://Shaunak2110-attendance-backend.hf.space/health | Should return `{"status":"ok"}` |
| Database | `attendance-server-shaunak.database.windows.net` / `ClassAttendanceDB` | Azure SQL Serverless |

### Azure SQL — admin login

| Field | Value |
|---|---|
| Server | `attendance-server-shaunak.database.windows.net` |
| Database | `ClassAttendanceDB` |
| Authentication | SQL Server Authentication |
| Username | `attendanceadmin` |
| Password | `Capstone@2026` |

Use these in **Azure portal → ClassAttendanceDB → Query editor (preview)** for ad-hoc SQL, or in SSMS / Azure Data Studio with the same hostname + SQL auth.

### Connection string used by the backend

```
Driver={ODBC Driver 18 for SQL Server};Server=tcp:attendance-server-shaunak.database.windows.net,1433;Database=ClassAttendanceDB;Uid=attendanceadmin;Pwd={Capstone@2026};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
```

Stored as the `DB_CONNECTION_STRING` secret on the HF Space. The backend's `database.py` parses ODBC-style strings into pymssql kwargs (strips `tcp:`, `{...}` braces, ignores driver/encrypt directives).

> **Rotate this password** after the capstone demo. Same goes for the HF access token — both are in this file (and chat history) and should not be considered secret long-term.

---

## Default Accounts

These accounts are seeded by running `usernamepsswd.sql` against `AttendanceDB`.

### Superadmin (Privilege Level 1)

| Field | Value |
|---|---|
| Username | `superadmin@mitwpu.edu.in` |
| Password | `Super@admin` |
| Privilege Level | `1` (Superadmin — full access) |
| Name | Super Admin |
| School | Administration |
| Department | IT |

> The bcrypt hash stored in the database for this account is:
> `$2b$12$rb35pVJMsmeypCGI3PzJUO6CJAYmLXYsSUB1VQsQ6AtjEMlix4Bl2`

---

## Creating Additional Accounts

All accounts are created through the application UI or API. Passwords are **always** stored as bcrypt hashes — never plaintext.

### Create an Admin (Privilege Level 2)

Log in as Superadmin → Superadmin Hub → **Register Admin** tab.

Required fields:
- Username (must be unique)
- Password (min 8 chars recommended)
- Full Name
- Email
- School
- Department

Or via API:
```http
POST /superadmin/create-admin
Headers: X-Privilege-Level: 1, X-User-Id: <superadmin_user_id>
Body:
{
  "username": "admin1@mitwpu.edu.in",
  "password": "Admin@1234",
  "name": "Admin One",
  "email_id": "admin1@mitwpu.edu.in",
  "school": "Computer Engineering and Technology",
  "department": "Computer Science and Engineering"
}
```

### Create a Teacher (Privilege Level 3)

Log in as Admin or Superadmin → Management Portal → **Onboard Faculty** form.

Required fields:
- Username (must be unique)
- Password
- Full Name
- Email
- Mobile Number
- School
- Department

Or via API:
```http
POST /admin/create-teacher
Headers: X-Privilege-Level: 2, X-User-Id: <admin_user_id>
Body:
{
  "username": "teacher1@mitwpu.edu.in",
  "password": "Teacher@1234",
  "name": "Teacher One",
  "email_id": "teacher1@mitwpu.edu.in",
  "school": "Computer Engineering and Technology",
  "department": "Computer Science and Engineering",
  "mob": "9999999999"
}
```

---

## Privilege Level Reference

| Level | Role | Can Do |
|---|---|---|
| `1` | **Superadmin** | Everything: create admins, create teachers, view all users, approve privilege requests, view attendance records |
| `2` | **Admin** | Create teachers, schedule lectures, create timetable templates, enroll students, view all lectures, view analytics |
| `3` | **Teacher** | Mark attendance, view own lectures, resolve unidentified faces, finalize attendance, download CSV, view own profile |

---

## How Authentication Works

1. User submits username + password to `POST /auth/login`
2. Backend queries `Login_Master` for the username
3. Password is verified using `bcrypt.checkpw(plaintext, stored_hash)`
4. On success, the response returns `{ user_id, username, privilege_level }`
5. Frontend stores these three values in `localStorage`
6. Every subsequent API request automatically attaches:
   - `X-User-Id: <user_id>` header
   - `X-Privilege-Level: <privilege_level>` header
7. Backend `require_privilege(n)` dependency validates `privilege_level <= n` on every protected endpoint

---

## Database Seed Instructions

### Local (SQL Server Express / SSMS)

Run these SQL files **in order** against `AttendanceDB` in SQL Server Management Studio:

```
1. Full Database Query.sql   — Creates all tables, indexes, constraints (uses USE AttendanceDB)
2. timetable_setup.sql        — Adds Lecture_Schedule table + schedule_id FK
3. usernamepsswd.sql          — Seeds the default Superadmin account
```

### Cloud (Azure SQL / Query editor)

Azure SQL forbids `USE <db>` between databases — connections target the DB selected in the connection string. Use these instead:

1. **Schema:** Open `azure_migration.sql` (root of repo). It's the same schema as `Full Database Query.sql` but `USE`-free and idempotent.
   - Azure portal → ClassAttendanceDB → **Query editor (preview)** → log in (`attendanceadmin` / `Capstone@2026`) → paste contents → Run

2. **Superadmin seed:** Strip the `USE AttendanceDB; GO` lines from `usernamepsswd.sql` and run only the INSERT block:

   ```sql
   INSERT INTO Login_Master (username, password_hash, privilege_level)
   VALUES ('superadmin@mitwpu.edu.in', '$2b$12$rb35pVJMsmeypCGI3PzJUO6CJAYmLXYsSUB1VQsQ6AtjEMlix4Bl2', 1);

   INSERT INTO User_Master (user_id, name, email_id, school, department)
   SELECT user_id, 'Super Admin', 'superadmin@mitwpu.edu.in', 'Administration', 'IT'
   FROM Login_Master WHERE username = 'superadmin@mitwpu.edu.in';
   ```

After seeding, log in with the Superadmin credentials above and create Admin and Teacher accounts through the UI.

---

## Viewing All Accounts in the Database

Passwords are stored as **bcrypt hashes** — this is a one-way encryption. You cannot read the original password from the hash. This is intentional and secure.

To see all accounts and their hashes, run this in SSMS:

```sql
USE AttendanceDB;

SELECT 
    l.user_id,
    l.username,
    CASE l.privilege_level 
        WHEN 1 THEN 'Superadmin'
        WHEN 2 THEN 'Admin'
        WHEN 3 THEN 'Teacher'
    END AS role,
    u.name,
    l.password_hash
FROM Login_Master l
JOIN User_Master u ON l.user_id = u.user_id
ORDER BY l.privilege_level, u.name;
```

This shows every account's username, role, full name, and stored hash.

---

## Resetting a Forgotten Password

Since passwords are hashed, you cannot recover them — but you can **replace** them.

### Step 1 — Generate a new bcrypt hash

Open a terminal in the backend folder and run:

```bash
cd C:\CapstoneVer3\backend
python -c "import bcrypt; print(bcrypt.hashpw(b'YourNewPassword', bcrypt.gensalt()).decode())"
```

Replace `YourNewPassword` with whatever password you want to set.
This prints a hash that looks like: `$2b$12$abc123...`

### Step 2 — Update the database

Run this in SSMS (replace the values):

```sql
USE AttendanceDB;

UPDATE Login_Master
SET password_hash = '$2b$12$paste_your_hash_here'
WHERE username = 'the_username_to_reset';
```

### Step 3 — Log in with the new password

The account can now log in with the new password you chose in Step 1.

---

## How Passwords Work (Simple Explanation)

When a user is created, their password goes through **bcrypt** — a one-way scrambling algorithm. The scrambled result (hash) is stored in the database. When someone logs in, the system scrambles the entered password the same way and checks if it matches the stored hash. The original password is never stored anywhere.

This means:
- Even if someone reads the database, they cannot see real passwords
- The only way to "recover" a password is to reset it with a new one
- Every hash looks different even for the same password (bcrypt uses a random salt)


---

## Complete Fresh Start Guide

> **Just want to use the deployed system?** Skip this — open https://capstone-class-attendance-system-us.vercel.app and log in with the superadmin credentials above. This guide is only for **setting up local development** on a new machine.

Follow these steps exactly if you are setting up this project on a new machine for the first time.

---

### Prerequisites to install first

Before anything else, make sure these are installed on your machine:

| What | Where to get it |
|---|---|
| Python 3.10 or higher | https://www.python.org/downloads/ |
| Node.js 20.19+ or 22.12+ | https://nodejs.org/ |
| SQL Server (Express is free) | https://www.microsoft.com/en-us/sql-server/sql-server-downloads |
| SQL Server Management Studio (SSMS) | https://aka.ms/ssmsfullsetup |
| ODBC Driver 17 for SQL Server | https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server |

---

### Step 1 — Set up the Database

1. Open **SSMS** and connect to your SQL Server instance (usually `.\SQLEXPRESS`)
2. Open `Full Database Query.sql` from `C:\CapstoneVer3\` and run it — this creates all tables
3. Open `timetable_setup.sql` and run it — this adds the timetable table
4. Open `usernamepsswd.sql` and run it — this creates the default Superadmin account

---

### Step 2 — Configure the Backend

Open `C:\CapstoneVer3\backend\.env` and set your SQL Server details:

```
SERVER=.\SQLEXPRESS
DATABASE=AttendanceDB
```

Change `.\SQLEXPRESS` to match your SQL Server instance name if it is different.

---

### Step 3 — Install and Run the Backend

Open a terminal (PowerShell or Command Prompt):

```bash
cd C:\CapstoneVer3\backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The backend is running when you see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Leave this terminal open. The backend must stay running.

---

### Step 4 — Install and Run the Frontend

Open a **second** terminal:

```bash
cd C:\CapstoneVer3\frontend
npm install --legacy-peer-deps
npm run dev
```

The frontend is running when you see:
```
VITE v7.3.1  ready in 367 ms
Local:   http://localhost:5173/
```

Leave this terminal open too.

---

### Step 5 — Open the App

Go to **http://localhost:5173** in your browser.

Log in with:
- Username: `superadmin@mitwpu.edu.in`
- Password: `Super@admin`

---

### Every Time After (Daily Use)

You only need to run two commands each time you want to use the system:

**Terminal 1 — Backend:**
```bash
cd C:\CapstoneVer3\backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd C:\CapstoneVer3\frontend
npm run dev
```

Then open http://localhost:5173

---

### If InsightFace model is missing (first run only)

The first time you run the backend and mark attendance, InsightFace will automatically download the `buffalo_l` model files (~500MB) from the internet. This only happens once. Make sure you have internet access on first run.

If you are on a machine without internet, copy the model files manually to:
```
C:\Users\<your_username>\.insightface\models\buffalo_l\
```


---

## All Known Accounts

### Superadmin (Privilege Level 1)
| Username | Password |
|---|---|
| superadmin@mitwpu.edu.in | Super@admin |

### Admins (Privilege Level 2)
| Username | Password |
|---|---|
| adminbtech@mitwpu.edu.in | Admin@btech |
| testadmin1@mitwpu.edu.in | Test@admin1 |

### Faculty / Teachers (Privilege Level 3)
| Username | Password |
|---|---|
| madhurap@mitwpu.edu.in | Madhura@mit |
| shilpapaygude@mitwpu.edu.in | Shilpa@mit |

> These accounts must be created through the application UI or via the SQL commands below.
> Passwords are stored as bcrypt hashes — see the "Resetting a Forgotten Password" section above.

### SQL to create these accounts (run in SSMS after generating hashes)

Generate hashes from the backend terminal:
```bash
cd C:\CapstoneVer3\backend
python -c "import bcrypt; print(bcrypt.hashpw(b'Admin@btech', bcrypt.gensalt()).decode())"
python -c "import bcrypt; print(bcrypt.hashpw(b'Test@admin1', bcrypt.gensalt()).decode())"
python -c "import bcrypt; print(bcrypt.hashpw(b'Madhura@mit', bcrypt.gensalt()).decode())"
python -c "import bcrypt; print(bcrypt.hashpw(b'Shilpa@mit', bcrypt.gensalt()).decode())"
```

Then use the application UI (recommended):
- Log in as Superadmin -> Superadmin Hub -> Register Admin (for admins)
- Log in as Admin -> Management Portal -> Onboard Faculty (for teachers)

