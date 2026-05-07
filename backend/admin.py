from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import datetime as dt
import bcrypt
import pyodbc

from database import get_db_connection, execute_query
from services.training_service import incremental_enroll
from dependencies import require_privilege

router = APIRouter(prefix="/admin", tags=["Admin"])

# ============================
# MODELS
# ============================

class CreateTeacherRequest(BaseModel):
    username: str
    password: str
    name: str
    email_id: EmailStr
    school: str
    department: str
    mob: str


class CreateTeacherResponse(BaseModel):
    user_id: int
    message: str


class ScheduleLectureRequest(BaseModel):
    # Accept either user_id (int) or username (str) — frontend sends username
    user_id: Optional[int] = None
    username: Optional[str] = None
    school: Optional[str] = None
    department: Optional[str] = None
    year: str
    specialisation: str
    lecorlab: str
    panel: str
    lec_name: str
    course_code: str
    lecture_datetime: dt.datetime


class LectureResponse(BaseModel):
    lec_id: int
    message: str


# ─── Timetable / Schedule Template Models ────────────────────────────────────

class CreateScheduleRequest(BaseModel):
    """Request model for creating a recurring lecture schedule template."""
    username: str           # teacher username (resolved to user_id server-side)
    lec_name: str
    course_code: str
    lecorlab: str           # 'lec' or 'lab'
    year: str
    specialisation: str
    panel: str
    days_of_week: List[str] # e.g. ['Monday', 'Wednesday']
    start_time: str         # 'HH:MM' (24-hour)
    sem_start_date: str     # 'YYYY-MM-DD'
    sem_end_date: str       # 'YYYY-MM-DD'


class ScheduleResponse(BaseModel):
    schedule_id: int
    message: str


class ScheduleRecord(BaseModel):
    schedule_id: int
    user_id: int
    username: str
    lec_name: str
    course_code: str
    lecorlab: str
    year: str
    specialisation: str
    panel: str
    day_of_week: str
    start_time: str
    sem_start_date: str
    sem_end_date: str
    is_active: bool


class EnrollStudentRequest(BaseModel):
    prn: str
    name: str
    year: str
    course: str
    specialisation: str
    rollno: str
    panel: str
    images: List[str]


class EnrollStudentResponse(BaseModel):
    message: str
    prn: str


# ============================
# CREATE TEACHER
# ============================

@router.post("/create-teacher", response_model=CreateTeacherResponse)
async def create_teacher(request: CreateTeacherRequest, _: int = Depends(require_privilege(2))):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()

        cursor.execute("SELECT user_id FROM Login_Master WHERE username=?", (request.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Username already exists")

        cursor.execute("""
            INSERT INTO Login_Master (username, password_hash, privilege_level)
            OUTPUT INSERTED.user_id
            VALUES (?, ?, 3)
        """, (request.username, password_hash))

        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO User_Master (user_id, name, email_id, school, department, mob)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, request.name, request.email_id, request.school, request.department, request.mob))

        connection.commit()

        return {"user_id": user_id, "message": "Teacher created successfully"}

    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================
# SCHEDULE LECTURE
# ============================

@router.post("/schedule-lecture", response_model=LectureResponse)
async def schedule_lecture(request: ScheduleLectureRequest, _: int = Depends(require_privilege(2))):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Resolve user_id from username if not provided directly
        resolved_user_id = request.user_id
        if resolved_user_id is None:
            if not request.username:
                raise HTTPException(status_code=400, detail="Either user_id or username must be provided")
            cursor.execute(
                "SELECT l.user_id, u.school, u.department FROM Login_Master l JOIN User_Master u ON l.user_id = u.user_id WHERE l.username = ?",
                (request.username,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Teacher with username '{request.username}' not found")
            resolved_user_id = row[0]
            # Use teacher's school/department if not explicitly provided
            school = request.school or row[1]
            department = request.department or row[2]
        else:
            school = request.school or ''
            department = request.department or ''

        cursor.execute("""
            INSERT INTO Lecture_Master
            (user_id, school, department, year, specialisation, lecorlab, panel, lec_name, course_code, lecture_datetime, attendance_status)
            OUTPUT INSERTED.lec_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'N')
        """, (
            resolved_user_id,
            school,
            department,
            request.year,
            request.specialisation,
            request.lecorlab,
            request.panel,
            request.lec_name,
            request.course_code,
            request.lecture_datetime
        ))

        lec_id = cursor.fetchone()[0]
        connection.commit()

        return {"lec_id": lec_id, "message": "Lecture scheduled successfully"}

    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================
# ENROLL STUDENT
# ============================

@router.post("/enroll-student", response_model=EnrollStudentResponse)
async def enroll_student(request: EnrollStudentRequest, _: int = Depends(require_privilege(2))):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if student exists
        cursor.execute("SELECT prn FROM Student_Master WHERE prn=?", (request.prn,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE Student_Master
                SET name=?, year=?, course=?, specialisation=?, rollno=?, panel=?
                WHERE prn=?
            """, (
                request.name,
                request.year,
                request.course,
                request.specialisation,
                request.rollno,
                request.panel,
                request.prn
            ))
        else:
            cursor.execute("""
                INSERT INTO Student_Master (prn, name, year, course, specialisation, rollno, panel)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                request.prn,
                request.name,
                request.year,
                request.course,
                request.specialisation,
                request.rollno,
                request.panel
            ))

        connection.commit()

        # Remove old embeddings
        cursor.execute("DELETE FROM Student_Embeddings WHERE prn=?", (request.prn,))
        connection.commit()

        # Add new embeddings
        success = 0
        for img in request.images:
            ok = incremental_enroll(request.prn, img)
            if ok:
                success += 1

        if success == 0:
            raise HTTPException(status_code=400, detail="No valid faces found")

        return {
            "message": f"Student enrolled successfully with {success} embeddings",
            "prn": request.prn
        }

    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================
# GET ALL LECTURES (admin view)
# ============================

@router.get("/lectures")
async def get_all_lectures(_: int = Depends(require_privilege(2))):
    """
    Return all lectures with the teacher's username for the admin records view.
    """
    try:
        rows = execute_query("""
            SELECT lm.lec_id, lm.lec_name, lm.panel, lm.year, lm.specialisation,
                   lm.course_code, lm.lecture_datetime, lm.attendance_status,
                   lm.lecorlab, l.username
            FROM Lecture_Master lm
            JOIN Login_Master l ON lm.user_id = l.user_id
            ORDER BY lm.lecture_datetime DESC
        """, fetch=True)

        if not rows:
            return []

        return [
            {
                "lec_id": r.lec_id,
                "lec_name": r.lec_name,
                "panel": r.panel,
                "year": r.year,
                "specialisation": r.specialisation,
                "course_code": r.course_code,
                "lecture_datetime": str(r.lecture_datetime) if r.lecture_datetime else None,
                "attendance_status": r.attendance_status,
                "lecorlab": r.lecorlab,
                "username": r.username,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ATTENDANCE ANALYTICS
# ============================

@router.get("/attendance-analytics")
async def get_attendance_analytics(
    year: Optional[str] = None,
    course_code: Optional[str] = None,
    panel: Optional[str] = None,
    username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    _: int = Depends(require_privilege(2))
):
    """
    Aggregate attendance data for a given subject/panel/teacher combination.
    Returns KPI summary + per-student breakdown.
    """
    try:
        # Build lecture filter
        lec_conditions = ["1=1"]
        lec_params = []

        if year:
            lec_conditions.append("lm.year = ?")
            lec_params.append(year)
        if course_code:
            lec_conditions.append("lm.course_code = ?")
            lec_params.append(course_code)
        if panel:
            lec_conditions.append("lm.panel = ?")
            lec_params.append(panel)
        if username:
            lec_conditions.append("l.username = ?")
            lec_params.append(username)
        if start_date:
            lec_conditions.append("lm.lecture_datetime >= ?")
            lec_params.append(start_date)
        if end_date:
            lec_conditions.append("lm.lecture_datetime <= ?")
            lec_params.append(end_date + " 23:59:59")

        where_clause = " AND ".join(lec_conditions)

        # Get matching lectures
        lec_rows = execute_query(f"""
            SELECT lm.lec_id, lm.lec_name, lm.panel, lm.course_code
            FROM Lecture_Master lm
            JOIN Login_Master l ON lm.user_id = l.user_id
            WHERE {where_clause}
        """, tuple(lec_params), fetch=True)

        if not lec_rows:
            return {
                "subject": course_code or "N/A",
                "panel": panel or "N/A",
                "totalLectures": 0,
                "overallPercentage": 0,
                "students": []
            }

        lec_ids = [r.lec_id for r in lec_rows]
        total_lectures = len(lec_ids)
        subject = lec_rows[0].lec_name
        resolved_panel = lec_rows[0].panel

        # Get all students in the panel
        student_rows = execute_query(
            "SELECT prn, name FROM Student_Master WHERE panel = ? ORDER BY name",
            (resolved_panel,), fetch=True
        )

        if not student_rows:
            return {
                "subject": subject,
                "panel": resolved_panel,
                "totalLectures": total_lectures,
                "overallPercentage": 0,
                "students": []
            }

        # Count present per student across matched lectures
        placeholders = ",".join(["?" for _ in lec_ids])
        attendance_rows = execute_query(f"""
            SELECT prn, COUNT(*) as present_count
            FROM Attendance_Record
            WHERE lec_id IN ({placeholders}) AND status = 'Present'
            GROUP BY prn
        """, tuple(lec_ids), fetch=True)

        present_map = {r.prn: r.present_count for r in (attendance_rows or [])}

        students = []
        total_present_sum = 0
        for s in student_rows:
            present = present_map.get(s.prn, 0)
            total_present_sum += present
            students.append({
                "prn": s.prn,
                "name": s.name,
                "total": total_lectures,
                "present": present,
            })

        total_possible = total_lectures * len(students)
        overall_pct = round((total_present_sum / total_possible * 100), 1) if total_possible > 0 else 0

        return {
            "subject": subject,
            "panel": resolved_panel,
            "totalLectures": total_lectures,
            "overallPercentage": overall_pct,
            "students": students,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# TIMETABLE / SCHEDULE TEMPLATES
# ============================

@router.post("/create-schedule", response_model=ScheduleResponse)
async def create_schedule(
    request: CreateScheduleRequest,
    _: int = Depends(require_privilege(2))
):
    """
    Create one recurring Lecture_Schedule row per selected day of week.

    The admin provides a teacher username, lecture details, which days of the
    week the class recurs, a start time, and the semester date range.
    One row is inserted per day so that the teacher's dashboard can auto-generate
    Lecture_Master instances each morning.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Resolve username → user_id
        cursor.execute(
            "SELECT user_id FROM Login_Master WHERE username = ?",
            (request.username,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Teacher '{request.username}' not found"
            )
        user_id = row[0]

        # Validate days
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                      'Friday', 'Saturday', 'Sunday']
        if not request.days_of_week:
            raise HTTPException(
                status_code=400,
                detail="At least one day_of_week must be selected"
            )
        for d in request.days_of_week:
            if d not in valid_days:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid day_of_week: '{d}'. Must be one of: {valid_days}"
                )

        schedule_ids = []
        for day in request.days_of_week:
            cursor.execute("""
                INSERT INTO Lecture_Schedule
                  (user_id, lec_name, course_code, lecorlab, year, specialisation,
                   panel, day_of_week, start_time, sem_start_date, sem_end_date, is_active)
                OUTPUT INSERTED.schedule_id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                user_id,
                request.lec_name,
                request.course_code,
                request.lecorlab,
                request.year,
                request.specialisation,
                request.panel,
                day,
                request.start_time,
                request.sem_start_date,
                request.sem_end_date,
            ))
            schedule_ids.append(cursor.fetchone()[0])

        connection.commit()
        return ScheduleResponse(
            schedule_id=schedule_ids[0] if schedule_ids else 0,
            message=f"Schedule created for {len(schedule_ids)} day(s) successfully"
        )

    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/schedules", response_model=List[ScheduleRecord])
async def get_all_schedules(_: int = Depends(require_privilege(2))):
    """
    Return all active recurring lecture schedule templates with teacher usernames.
    Used by the admin records view to display the timetable.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                ls.schedule_id,
                ls.user_id,
                lm.username,
                ls.lec_name,
                ls.course_code,
                ls.lecorlab,
                ls.year,
                ls.specialisation,
                ls.panel,
                ls.day_of_week,
                CONVERT(VARCHAR(5), ls.start_time, 108) AS start_time,
                CONVERT(VARCHAR(10), ls.sem_start_date, 120) AS sem_start_date,
                CONVERT(VARCHAR(10), ls.sem_end_date, 120) AS sem_end_date,
                ls.is_active
            FROM Lecture_Schedule ls
            JOIN Login_Master lm ON ls.user_id = lm.user_id
            WHERE ls.is_active = 1
            ORDER BY ls.day_of_week, ls.start_time
        """)
        cols = [c[0] for c in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/schedule/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    _: int = Depends(require_privilege(2))
):
    """
    Soft-delete (deactivate) a recurring schedule template.
    Sets is_active = 0; existing Lecture_Master rows are preserved.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Lecture_Schedule SET is_active = 0 WHERE schedule_id = ?",
            (schedule_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule not found")
        connection.commit()
        return {"message": "Schedule deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================
# GET ALL STUDENTS
# ============================

@router.get("/students")
async def get_all_students(_: int = Depends(require_privilege(3))):
    """
    Return all enrolled students. Accessible to all logged-in users (privilege 3+).
    Used by admin unenroll panel and by the Results page face-resolution dialog
    to show existing students for selection.
    """
    try:
        rows = execute_query(
            """SELECT prn, name, year, course, specialisation, rollno, panel
               FROM Student_Master ORDER BY name""",
            fetch=True
        )
        if not rows:
            return []
        return [
            {
                "prn": r.prn,
                "name": r.name,
                "year": r.year,
                "course": r.course,
                "specialisation": r.specialisation,
                "rollno": r.rollno,
                "panel": r.panel,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# UNENROLL STUDENT
# ============================

@router.delete("/unenroll-student/{prn}")
async def unenroll_student(
    prn: str,
    _: int = Depends(require_privilege(2))
):
    """
    Completely remove a student from the system:
    - Deletes all face embeddings from Student_Embeddings
    - Deletes all attendance records from Attendance_Record
    - Deletes the student from Student_Master

    This is irreversible. The student will need to be re-enrolled from scratch.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Verify student exists
        cursor.execute("SELECT prn, name FROM Student_Master WHERE prn = ?", (prn,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Student with PRN '{prn}' not found")

        student_name = row[1]

        # Delete embeddings
        cursor.execute("DELETE FROM Student_Embeddings WHERE prn = ?", (prn,))
        embeddings_deleted = cursor.rowcount

        # Delete attendance records
        cursor.execute("DELETE FROM Attendance_Record WHERE prn = ?", (prn,))
        records_deleted = cursor.rowcount

        # Delete student
        cursor.execute("DELETE FROM Student_Master WHERE prn = ?", (prn,))

        connection.commit()

        return {
            "message": f"Student '{student_name}' (PRN: {prn}) unenrolled successfully.",
            "embeddings_deleted": embeddings_deleted,
            "attendance_records_deleted": records_deleted,
        }

    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
