"""
User/Teacher module for the Role-Based Attendance System.

This module provides Teacher functionality including lecture retrieval,
attendance marking, face resolution, and attendance finalization.

Requirements: 8.1, 8.2, 8.3, 9.1, 9.7, 15.2
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List
import datetime as dt
import pymssql
from database import execute_query, get_db_connection
from services import recognition_service, training_service, csv_service
from model.inference import InferenceEngine
from dependencies import require_privilege, get_current_user_id


# Pydantic models for request/response
class LectureResponse(BaseModel):
    """
    Response model for lecture retrieval.
    
    Attributes:
        lec_id: Unique identifier for the lecture
        lec_name: Name of the lecture
        panel: Class section identifier (e.g., 'H', 'I')
        lecture_datetime: Date and time of the lecture
        attendance_status: Status flag ('Y' for finalized, 'N' for pending)
    """
    lec_id: int
    lec_name: str
    panel: str
    lecture_datetime: dt.datetime
    attendance_status: str
    year: Optional[str] = None
    specialisation: Optional[str] = None
    course_code: Optional[str] = None
    lecorlab: Optional[str] = None


class EnrolledStudentResponse(BaseModel):
    """
    Response model for enrolled students in a lecture's target group.
    """
    prn: str
    name: str
    rollno: str


class IdentifiedStudent(BaseModel):
    """
    Model for an identified student in attendance marking.
    
    Attributes:
        prn: Student's Permanent Registration Number
        name: Student's full name
        similarity: Cosine similarity score (0.0 to 1.0)
    """
    prn: str
    name: str
    similarity: float


class UnidentifiedFace(BaseModel):
    """
    Model for an unidentified face in attendance marking.
    
    Attributes:
        face_id: Unique UUID string for this face
        image: Base64-encoded cropped face image
    """
    face_id: str
    image: str


class MarkAttendanceRequest(BaseModel):
    """
    Request model for marking attendance.
    
    Attributes:
        lec_id: ID of the lecture for which attendance is being marked
        images: List of base64-encoded image strings
        lecture_datetime: Optional overridden timestamp specifying exactly when this class actually took place
    """
    lec_id: int
    images: List[str]
    lecture_datetime: Optional[dt.datetime] = None


class MarkAttendanceResponse(BaseModel):
    """
    Response model for attendance marking.
    
    Attributes:
        identified_students: List of identified students with PRN, name, and similarity
        unidentified_faces: List of unidentified faces with face_id and image
    """
    identified_students: List[IdentifiedStudent]
    unidentified_faces: List[UnidentifiedFace]


class FaceResolution(BaseModel):
    """
    Model for resolving an unidentified face.
    
    Attributes:
        face_id: UUID string identifying the unidentified face
        action: Action to take - "existing" (link to existing student), 
                "new" (create new student), or "discard" (ignore face)
        prn: Student's PRN (required for "existing" and "new" actions)
        name: Student's name (required for "new" action only)
        panel: Student's panel (required for "new" action only)
        image: Optional base64 face crop sent by frontend as fallback
               when the server-side cache has been cleared (e.g. after restart)
    """
    face_id: str
    action: str  # "existing", "new", or "discard"
    prn: Optional[str] = None
    name: Optional[str] = None
    panel: Optional[str] = None
    year: Optional[str] = None
    course: Optional[str] = None
    specialisation: Optional[str] = None
    rollno: Optional[str] = None
    image: Optional[str] = None  # base64 fallback from frontend


class ResolveFacesRequest(BaseModel):
    """
    Request model for resolving unidentified faces.
    
    Attributes:
        lec_id: ID of the lecture for which faces are being resolved
        resolutions: List of face resolutions with actions
    """
    lec_id: int
    resolutions: List[FaceResolution]


class ResolveFacesResponse(BaseModel):
    """
    Response model for face resolution.
    
    Attributes:
        message: Success message
        resolved_count: Number of faces successfully resolved
    """
    message: str
    resolved_count: int


class FinalizeAttendanceRequest(BaseModel):
    """
    Request model for finalizing attendance.
    
    Attributes:
        lec_id: ID of the lecture to finalize
        identified_prns: List of PRNs identified by face recognition to mark as Present
    """
    lec_id: int
    identified_prns: List[str] = []


class FinalizeAttendanceResponse(BaseModel):
    """
    Response model for attendance finalization.

    Attributes:
        message: Success message
        csv_path: Path to the generated CSV file
    """
    message: str
    csv_path: str


# Create router for user/teacher endpoints
router = APIRouter(prefix="/user", tags=["User/Teacher"])


# Note: validate_user_privilege is now replaced by require_privilege(3) dependency
# Kept for backward compatibility if needed, but new endpoints should use require_privilege(3)


@router.get("/lectures/{user_id}", response_model=List[LectureResponse])
async def get_user_lectures(
    user_id: int,
    _: int = Depends(require_privilege(3))
):
    """
    Retrieve all scheduled lectures for a specific teacher.

    Timetable integration: before returning, checks Lecture_Schedule for any
    recurring templates belonging to this teacher that match today's day-of-week
    and fall within the semester date range. For each match a Lecture_Master row
    is auto-created for today (idempotent — duplicates are skipped). This means
    a teacher always sees today's classes without the admin pre-creating them
    every morning.

    Results are ordered: today's lectures first (by time ASC), then all others
    by lecture_datetime DESC.

    Requirements: 8.1, 8.2, 8.3
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # ── Step 1: Auto-generate today's lecture instances from Lecture_Schedule ──
        today = dt.date.today()
        today_name = today.strftime('%A')   # e.g. 'Wednesday'

        cursor.execute("""
            SELECT schedule_id, lec_name, course_code, lecorlab,
                   year, specialisation, panel, start_time
            FROM Lecture_Schedule
            WHERE user_id = %s
              AND day_of_week = %s
              AND is_active = 1
              AND sem_start_date <= %s
              AND sem_end_date   >= %s
        """, (user_id, today_name, str(today), str(today)))
        today_schedules = cursor.fetchall()

        # Get teacher's school/department for Lecture_Master NOT NULL columns
        cursor.execute(
            "SELECT school, department FROM User_Master WHERE user_id = %s",
            (user_id,)
        )
        teacher_row = cursor.fetchone()
        teacher_school = teacher_row[0] if teacher_row else ''
        teacher_dept = teacher_row[1] if teacher_row else ''

        for sched in today_schedules:
            (schedule_id, lec_name, course_code, lecorlab,
             year, specialisation, panel, start_time_val) = sched

            # Build today's exact datetime for this lecture
            if hasattr(start_time_val, 'hour'):
                lec_dt = dt.datetime.combine(today, start_time_val)
            else:
                h, m = str(start_time_val).split(':')[:2]
                lec_dt = dt.datetime.combine(today, dt.time(int(h), int(m)))

            # Idempotency: only insert if this (schedule_id, date) doesn't exist yet
            cursor.execute("""
                SELECT lec_id FROM Lecture_Master
                WHERE schedule_id = %s
                  AND CAST(lecture_datetime AS DATE) = %s
            """, (schedule_id, str(today)))
            if cursor.fetchone():
                continue  # already created today

            cursor.execute("""
                INSERT INTO Lecture_Master
                  (user_id, school, department, lecorlab, panel, lec_name, course_code,
                   lecture_datetime, attendance_status,
                   year, specialisation, schedule_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'N', %s, %s, %s)
            """, (
                user_id, teacher_school, teacher_dept,
                lecorlab, panel, lec_name, course_code,
                lec_dt, year, specialisation, schedule_id
            ))

        connection.commit()

        # ── Step 2: Fetch all lectures for this teacher ──────────────────────
        cursor.execute("""
            SELECT lec_id, lec_name, panel, lecture_datetime, attendance_status,
                   year, specialisation, course_code, lecorlab
            FROM Lecture_Master
            WHERE user_id = %s
            ORDER BY
                CASE WHEN CAST(lecture_datetime AS DATE) = CAST(GETDATE() AS DATE)
                     THEN 0 ELSE 1 END,
                lecture_datetime DESC
        """, (user_id,))
        rows = cursor.fetchall()

        if not rows:
            return []

        return [
            LectureResponse(
                lec_id=r[0], lec_name=r[1], panel=r[2],
                lecture_datetime=r[3], attendance_status=r[4],
                year=r[5], specialisation=r[6],
                course_code=r[7], lecorlab=r[8]
            )
            for r in rows
        ]

    except HTTPException:
        raise
    except pymssql.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving lectures: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while retrieving lectures: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/today-lectures/{user_id}", response_model=List[LectureResponse])
async def get_today_lectures(
    user_id: int,
    _: int = Depends(require_privilege(3))
):
    """
    Return only today's lectures for a teacher, ordered by start time ASC.
    Used by the teacher Dashboard 'Today's Classes' smart panel.
    Triggers the same auto-generation logic as get_user_lectures.
    """
    # Reuse the full lectures endpoint which auto-generates today's instances,
    # then filter to today only.
    try:
        today = dt.date.today()
        query = """
            SELECT lec_id, lec_name, panel, lecture_datetime, attendance_status,
                   year, specialisation, course_code, lecorlab
            FROM Lecture_Master
            WHERE user_id = %s
              AND CAST(lecture_datetime AS DATE) = %s
            ORDER BY lecture_datetime ASC
        """
        results = execute_query(query, (user_id, str(today)), fetch=True)

        if not results:
            return []

        return [
            LectureResponse(
                lec_id=r[0], lec_name=r[1], panel=r[2],
                lecture_datetime=r[3], attendance_status=r[4],
                year=r[5], specialisation=r[6],
                course_code=r[7], lecorlab=r[8]
            )
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/{user_id}")
async def get_user_schedules(
    user_id: int,
    _: int = Depends(require_privilege(3))
):
    """
    Retrieve all active recurring lecture templates (Lecture_Schedule rows)
    for a specific teacher. Used by the teacher's profile/timetable view.
    """
    try:
        query = """
            SELECT schedule_id, user_id, lec_name, course_code, lecorlab,
                   year, specialisation, panel, day_of_week, start_time,
                   sem_start_date, sem_end_date, is_active
            FROM Lecture_Schedule
            WHERE user_id = %s AND is_active = 1
            ORDER BY day_of_week, start_time
        """
        results = execute_query(query, (user_id,), fetch=True)
        if not results:
            return []

        schedules = []
        for r in results:
            schedules.append({
                "schedule_id": r.schedule_id,
                "user_id": r.user_id,
                "lec_name": r.lec_name,
                "course_code": r.course_code,
                "lecorlab": r.lecorlab,
                "year": r.year,
                "specialisation": r.specialisation,
                "panel": r.panel,
                "day_of_week": r.day_of_week,
                "start_time": (
                    r.start_time.strftime('%H:%M')
                    if hasattr(r.start_time, 'strftime')
                    else str(r.start_time)[:5]
                ),
                "sem_start_date": str(r.sem_start_date),
                "sem_end_date": str(r.sem_end_date),
                "is_active": bool(r.is_active),
            })
        return schedules
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enrolled-students/{lec_id}", response_model=List[EnrolledStudentResponse])
async def get_enrolled_students(
    lec_id: int,
    _: int = Depends(require_privilege(3))
):
    """
    Retrieve all enrolled students for a given lecture based on year, specialisation, and panel.
    """
    try:
        query_lec = "SELECT year, specialisation, panel FROM Lecture_Master WHERE lec_id = %s"
        lec_result = execute_query(query_lec, (lec_id,), fetch=True)
        if not lec_result or len(lec_result) == 0:
            raise HTTPException(status_code=404, detail="Lecture not found")
        lec = lec_result[0]
        
        query_stu = "SELECT prn, name, rollno FROM Student_Master WHERE year = %s AND specialisation = %s AND panel = %s"
        students = execute_query(query_stu, (lec.year, lec.specialisation, lec.panel), fetch=True)
        
        if not students:
            return []
            
        return [EnrolledStudentResponse(
            prn=s.prn,
            name=s.name,
            rollno=getattr(s, 'rollno', 'N/A') or 'N/A'
        ) for s in students]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attendance-records/{lec_id}")
async def get_attendance_records(
    lec_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    _: int = Depends(require_privilege(3))
):
    """
    Retrieve attendance records for a specific lecture with optional date range filter.
    Returns student name, rollno, PRN, status, and the lecture datetime.
    """
    try:
        query = """
            SELECT
                sm.name,
                sm.rollno,
                ar.prn,
                ar.status,
                lm.lecture_datetime,
                lm.lec_name
            FROM Attendance_Record ar
            JOIN Student_Master sm ON ar.prn = sm.prn
            JOIN Lecture_Master lm ON ar.lec_id = lm.lec_id
            WHERE ar.lec_id = %s
        """
        params = [lec_id]

        if date_from:
            query += " AND lm.lecture_datetime >= %s"
            params.append(date_from)
        if date_to:
            query += " AND lm.lecture_datetime <= %s"
            params.append(date_to + " 23:59:59")

        query += " ORDER BY lm.lecture_datetime DESC, sm.rollno ASC"

        rows = execute_query(query, tuple(params), fetch=True)
        if not rows:
            return []

        return [
            {
                "name": row.name,
                "rollno": getattr(row, 'rollno', 'N/A') or 'N/A',
                "prn": row.prn,
                "status": row.status,
                "lecture_datetime": str(row.lecture_datetime) if row.lecture_datetime else None,
                "lec_name": row.lec_name,
            }
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-attendance", response_model=MarkAttendanceResponse)
async def mark_attendance(
    request: MarkAttendanceRequest,
    user_id: int = Depends(get_current_user_id),
    _: int = Depends(require_privilege(3))
):
    """
    Mark attendance for a lecture using facial recognition.
    
    This endpoint processes classroom images to identify students:
    1. Validates that the lecture exists and belongs to the authenticated user
    2. Processes images through the facial recognition engine
    3. Identifies students by matching face embeddings
    4. Returns lists of identified students and unidentified faces
    
    All authenticated users (privilege levels 1, 2, 3) can access this endpoint.
    
    Args:
        request: MarkAttendanceRequest containing lec_id and images
        user_id: ID of the authenticated user from request header (via dependency)
        _: Privilege validation dependency (requires User level 3 or higher)
        
    Returns:
        MarkAttendanceResponse: Lists of identified students and unidentified faces
        
    Raises:
        HTTPException 400: If validation fails (missing images, invalid data)
        HTTPException 403: If user lacks valid privileges
        HTTPException 404: If lecture not found or doesn't belong to user
        HTTPException 500: If database or recognition operation fails
        
    Requirements:
        - 9.1: Accept multiple images and lecture_id for attendance marking
        - 9.7: Return list of identified students and unidentified face images
        - 15.2: Return 400 for validation errors
    """
    # Privilege validation is handled by require_privilege(3) dependency
    # User ID extraction is handled by get_current_user_id dependency
    
    # Validate request data
    if not request.images or len(request.images) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one image is required for attendance marking"
        )
    
    try:
        # Step 1: Validate lecture exists, belongs to user, and is not finalized
        query = """
            SELECT lec_id, user_id, panel, attendance_status
            FROM Lecture_Master
            WHERE lec_id = %s
        """
        
        results = execute_query(query, (request.lec_id,), fetch=True)
        
        # Check if lecture exists
        if not results or len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecture with ID {request.lec_id} not found"
            )
        
        lecture = results[0]
        
        # Check if lecture belongs to the authenticated user
        if lecture.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Lecture {request.lec_id} does not belong to user {user_id}"
            )

        # Block processing if lecture is already finalized
        if lecture.attendance_status == 'Y':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This lecture has already been finalized. Attendance cannot be marked again."
            )
        
        # Optional: Update lecture datetime if overridden by teacher
        if request.lecture_datetime:
            update_dt_query = "UPDATE Lecture_Master SET lecture_datetime = %s WHERE lec_id = %s"
            execute_query(update_dt_query, (request.lecture_datetime, request.lec_id), fetch=False)
        
        # Step 2: Get inference engine instance
        inference_engine = InferenceEngine()
        
        # Step 3: Call recognition_service.recognize_students()
        identified_students_list, unidentified_faces_list = recognition_service.recognize_students(
            images=request.images,
            lecture_id=request.lec_id,
            inference_engine=inference_engine
        )
        
        # Step 4: Convert to Pydantic models
        identified_students = [
            IdentifiedStudent(
                prn=student['prn'],
                name=student['name'],
                similarity=student['similarity']
            )
            for student in identified_students_list
        ]
        
        unidentified_faces = [
            UnidentifiedFace(
                face_id=face['face_id'],
                image=face['image']
            )
            for face in unidentified_faces_list
        ]
        
        # Step 5: Return response
        return MarkAttendanceResponse(
            identified_students=identified_students,
            unidentified_faces=unidentified_faces
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, 400, etc.)
        raise
    except ValueError as e:
        # Handle validation errors from recognition service
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except pymssql.Error as e:
        # Handle database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while marking attendance: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while marking attendance: {str(e)}"
        )



@router.post("/resolve-faces", response_model=ResolveFacesResponse)
async def resolve_faces(
    request: ResolveFacesRequest,
    user_id: int = Depends(get_current_user_id),
    _: int = Depends(require_privilege(3))
):
    """
    Resolve unidentified faces from attendance marking.
    
    This endpoint processes teacher's decisions about unidentified faces:
    1. For action="existing": Verifies PRN exists, marks attendance, performs incremental training
    2. For action="new": Creates new student record, marks attendance, performs incremental training
    3. For action="discard": Skips processing and removes face from cache
    
    All authenticated users (privilege levels 1, 2, 3) can access this endpoint.
    
    Args:
        request: ResolveFacesRequest containing lec_id and list of resolutions
        user_id: ID of the authenticated user from request header (via dependency)
        _: Privilege validation dependency (requires User level 3 or higher)
        
    Returns:
        ResolveFacesResponse: Success message and count of resolved faces
        
    Raises:
        HTTPException 400: If validation fails (invalid PRN, missing fields)
        HTTPException 403: If user lacks valid privileges
        HTTPException 404: If lecture not found or doesn't belong to user
        HTTPException 500: If database or training operation fails
        
    Requirements:
        - 10.1: Verify PRN exists in Student_Master for action="existing"
        - 10.2: Mark student as present for the lecture
        - 10.3: Perform incremental training using cropped face image
        - 10.4: Discard image for action="discard"
        - 10.5: Insert new student into Student_Master for action="new"
        - 10.6: Perform incremental training for new students
        - 10.7: Save updated model weights after processing
    """
    # Privilege validation is handled by require_privilege(3) dependency
    # User ID extraction is handled by get_current_user_id dependency
    
    # Validate request data
    if not request.resolutions or len(request.resolutions) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one face resolution is required"
        )
    
    try:
        # Step 1: Validate lecture exists and belongs to authenticated user
        query = """
            SELECT lec_id, user_id, panel
            FROM Lecture_Master
            WHERE lec_id = %s
        """
        
        results = execute_query(query, (request.lec_id,), fetch=True)
        
        # Check if lecture exists
        if not results or len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecture with ID {request.lec_id} not found"
            )
        
        lecture = results[0]
        
        # Check if lecture belongs to the authenticated user
        if lecture.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Lecture {request.lec_id} does not belong to user {user_id}"
            )
        
        # Step 2: Process each resolution
        resolved_count = 0
        
        for resolution in request.resolutions:
            action = resolution.action.lower()
            face_id = resolution.face_id
            
            # Validate action type
            if action not in ["existing", "new", "discard"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action '{resolution.action}'. Must be 'existing', 'new', or 'discard'"
                )
            
            # Handle "discard" action - skip processing
            if action == "discard":
                # Remove face from cache
                recognition_service.remove_unidentified_face(face_id)
                resolved_count += 1
                continue
            
            # For "existing" and "new" actions, PRN is required
            if not resolution.prn:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PRN is required for action '{action}'"
                )
            
            prn = resolution.prn
            
            # Retrieve face image from cache.
            # If the cache was cleared (e.g. server restart), fall back to the
            # base64 image the frontend sent in the resolution payload.
            try:
                face_image = recognition_service.get_unidentified_face(face_id)
            except KeyError:
                if resolution.image:
                    # Use the frontend-provided base64 crop as fallback
                    face_image = resolution.image
                else:
                    # No cache and no fallback image — skip embedding but still
                    # process attendance so the teacher's action is not lost
                    face_image = None
            
            # Handle "existing" action
            if action == "existing":
                # Verify PRN exists in Student_Master
                query = "SELECT prn, panel FROM Student_Master WHERE prn = %s"
                results = execute_query(query, (prn,), fetch=True)
                
                if not results or len(results) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Student with PRN {prn} not found in database"
                    )
                
                student = results[0]
                student_panel = student.panel
                
                # Insert into Attendance_Record (skip if already marked)
                existing_record = execute_query(
                    "SELECT 1 FROM Attendance_Record WHERE lec_id = %s AND prn = %s",
                    (request.lec_id, prn), fetch=True
                )
                if not existing_record:
                    execute_query(
                        "INSERT INTO Attendance_Record (lec_id, prn, status) VALUES (%s, %s, 'Present')",
                        (request.lec_id, prn), fetch=False
                    )
                
                # Perform incremental enrollment (only if we have the face image)
                if face_image:
                    training_service.incremental_enroll(prn, face_image)
                
                # Remove face from cache (safe even if already gone)
                recognition_service.remove_unidentified_face(face_id)
                resolved_count += 1
            
            # Handle "new" action
            elif action == "new":
                # Validate required fields for new student
                if not resolution.name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Name is required for action 'new'"
                    )
                
                if not resolution.panel:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Panel is required for action 'new'"
                    )
                
                name = resolution.name
                panel = resolution.panel
                
                # Check if PRN already exists
                query = "SELECT prn FROM Student_Master WHERE prn = %s"
                results = execute_query(query, (prn,), fetch=True)
                
                if results and len(results) > 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Student with PRN {prn} already exists in database"
                    )
                
                # Insert new student into Student_Master
                insert_student_query = """
                    INSERT INTO Student_Master (prn, name, year, course, specialisation, rollno, panel)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                execute_query(insert_student_query, (
                    prn, 
                    name, 
                    resolution.year or 'N/A', 
                    resolution.course or 'N/A', 
                    resolution.specialisation or 'N/A', 
                    resolution.rollno or 'N/A', 
                    panel
                ), fetch=False)
                
                # Insert into Attendance_Record (skip if already marked)
                existing_record = execute_query(
                    "SELECT 1 FROM Attendance_Record WHERE lec_id = %s AND prn = %s",
                    (request.lec_id, prn), fetch=True
                )
                if not existing_record:
                    execute_query(
                        "INSERT INTO Attendance_Record (lec_id, prn, status) VALUES (%s, %s, 'Present')",
                        (request.lec_id, prn), fetch=False
                    )
                
                # Perform incremental enrollment (only if we have the face image)
                if face_image:
                    training_service.incremental_enroll(prn, face_image)
                
                # Remove face from cache (safe even if already gone)
                recognition_service.remove_unidentified_face(face_id)
                resolved_count += 1
        
        # Return success response
        return ResolveFacesResponse(
            message=f"Successfully resolved {resolved_count} face(s)",
            resolved_count=resolved_count
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, 400, etc.)
        raise
    except ValueError as e:
        # Handle validation errors from training service
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except pymssql.Error as e:
        # Handle database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while resolving faces: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while resolving faces: {str(e)}"
        )



@router.post("/finalize-attendance", response_model=FinalizeAttendanceResponse)
async def finalize_attendance(
    request: FinalizeAttendanceRequest,
    user_id: int = Depends(get_current_user_id),
    _: int = Depends(require_privilege(3))
):
    """
    Finalize attendance for a lecture and generate CSV report.
    
    This endpoint finalizes attendance by:
    1. Validating that the lecture exists and belongs to the authenticated user
    2. Updating the attendance_status to 'Y' in Lecture_Master
    3. Generating a CSV file with all student attendance data
    4. Returning the CSV file path
    
    Once finalized, the attendance record is locked and a permanent CSV report is created.
    All authenticated users (privilege levels 1, 2, 3) can access this endpoint.
    
    Args:
        request: FinalizeAttendanceRequest containing lec_id
        user_id: ID of the authenticated user from request header (via dependency)
        _: Privilege validation dependency (requires User level 3 or higher)
        
    Returns:
        FinalizeAttendanceResponse: Success message and CSV file path
        
    Raises:
        HTTPException 400: If validation fails
        HTTPException 403: If user lacks valid privileges or lecture doesn't belong to user
        HTTPException 404: If lecture not found
        HTTPException 500: If database or CSV generation operation fails
        
    Requirements:
        - 11.1: Update attendance_status to 'Y' in Lecture_Master
        - 11.2: Generate CSV file containing attendance records
    """
    # Privilege validation is handled by require_privilege(3) dependency
    # User ID extraction is handled by get_current_user_id dependency
    
    try:
        # Step 1: Validate lecture exists and belongs to authenticated user
        query = """
            SELECT lec_id, user_id, attendance_status
            FROM Lecture_Master
            WHERE lec_id = %s
        """
        
        results = execute_query(query, (request.lec_id,), fetch=True)
        
        # Check if lecture exists
        if not results or len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lecture with ID {request.lec_id} not found"
            )
        
        lecture = results[0]
        
        # Check if lecture belongs to the authenticated user
        if lecture.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Lecture {request.lec_id} does not belong to user {user_id}"
            )
        
        # Step 2: Insert identified students into Attendance_Record (skip duplicates)
        for prn in request.identified_prns:
            # Check if already recorded (e.g. from resolve-faces)
            existing = execute_query(
                "SELECT 1 FROM Attendance_Record WHERE lec_id = %s AND prn = %s",
                (request.lec_id, prn),
                fetch=True
            )
            if not existing:
                execute_query(
                    "INSERT INTO Attendance_Record (lec_id, prn, status) VALUES (%s, %s, 'Present')",
                    (request.lec_id, prn),
                    fetch=False
                )

        # Step 3: Update attendance_status to 'Y' in Lecture_Master
        update_query = """
            UPDATE Lecture_Master
            SET attendance_status = 'Y'
            WHERE lec_id = %s
        """
        execute_query(update_query, (request.lec_id,), fetch=False)
        
        # Step 4: Generate CSV file using csv_service
        csv_path = csv_service.generate_attendance_csv(request.lec_id)
        
        # Step 4: Return success response with CSV path
        return FinalizeAttendanceResponse(
            message="Attendance finalized successfully",
            csv_path=csv_path
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, 400, etc.)
        raise
    except ValueError as e:
        # Handle validation errors from CSV service
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except pymssql.Error as e:
        # Handle database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while finalizing attendance: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors (including CSV generation failures)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while finalizing attendance: {str(e)}"
        )


@router.get("/profile")
async def get_user_profile(
    user_id: int = Depends(get_current_user_id),
    _: int = Depends(require_privilege(3))
):
    """
    Return profile details for the currently authenticated user.
    Reads X-User-Id header (injected by the frontend interceptor).
    """
    try:
        query = """
            SELECT l.user_id, l.username, l.privilege_level,
                   u.name, u.email_id, u.school, u.department
            FROM Login_Master l
            JOIN User_Master u ON l.user_id = u.user_id
            WHERE l.user_id = %s
        """
        results = execute_query(query, (user_id,), fetch=True)
        if not results:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        row = results[0]
        return {
            "user_id": row.user_id,
            "username": row.username,
            "privilege_level": row.privilege_level,
            "name": row.name,
            "email_id": row.email_id,
            "school": row.school,
            "department": row.department,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/download-csv/{lec_id}")
async def download_csv(
    lec_id: int,
    user_id: int = Depends(get_current_user_id),
    _: int = Depends(require_privilege(3))
):
    """
    Stream the CSV file for a finalized lecture as a file download.
    Regenerates the CSV on demand so it is always up-to-date.
    """
    import os
    from fastapi.responses import FileResponse

    try:
        # Verify lecture belongs to this user
        results = execute_query(
            "SELECT user_id FROM Lecture_Master WHERE lec_id = %s",
            (lec_id,), fetch=True
        )
        if not results:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
        if results[0].user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        csv_path = csv_service.generate_attendance_csv(lec_id)

        if not os.path.exists(csv_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CSV file not found")

        filename = os.path.basename(csv_path)
        return FileResponse(
            path=csv_path,
            media_type="text/csv",
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/request-privilege")
async def request_privilege(
    user_id: int = Depends(get_current_user_id),
    _: int = Depends(require_privilege(3))
):
    """
    Submit a privilege escalation request for the current user.
    Inserts a row into Request_Master (ignored if one already exists).
    """
    try:
        existing = execute_query(
            "SELECT request_id FROM Request_Master WHERE user_id = %s",
            (user_id,), fetch=True
        )
        if existing:
            return {"message": "Privilege request already submitted"}

        execute_query(
            "INSERT INTO Request_Master (user_id) VALUES (%s)",
            (user_id,), fetch=False
        )
        return {"message": "Privilege request submitted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
