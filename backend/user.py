"""
User/Teacher module for the Role-Based Attendance System.

This module provides Teacher functionality including lecture retrieval,
attendance marking, face resolution, and attendance finalization.

Requirements: 8.1, 8.2, 8.3, 9.1, 9.7, 15.2
"""

from fastapi import APIRouter, HTTPException, status, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
import datetime as dt
import pyodbc
from database import execute_query
from services import recognition_service, training_service, csv_service
from model.face_model import FaceModel
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
    """
    lec_id: int
    images: List[str]


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
    """
    face_id: str
    action: str  # "existing", "new", or "discard"
    prn: Optional[str] = None
    name: Optional[str] = None
    panel: Optional[str] = None


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

    class FinalizeAttendanceRequest(BaseModel):
        """
        Request model for finalizing attendance.

        Attributes:
            lec_id: ID of the lecture to finalize
        """
        lec_id: int


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


# Global face model and inference engine instances
# These will be set by main.py at startup via set_face_model / set_inference_engine
_face_model = None
_inference_engine = None


def set_face_model(face_model):
    global _face_model
    _face_model = face_model


def set_inference_engine(inference_engine):
    global _inference_engine
    _inference_engine = inference_engine


def get_face_model():
    global _face_model
    if _face_model is None:
        _face_model = FaceModel()
    return _face_model


def get_inference_engine():
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = InferenceEngine(get_face_model())
    return _inference_engine


# Note: validate_user_privilege is now replaced by require_privilege(3) dependency
# Kept for backward compatibility if needed, but new endpoints should use require_privilege(3)


@router.get("/lectures/{user_id}", response_model=List[LectureResponse])
async def get_user_lectures(
    user_id: int,
    _: int = Depends(require_privilege(3))
):
    """
    Retrieve all scheduled lectures for a specific teacher.
    
    This endpoint returns all lectures associated with the given user_id,
    ordered by lecture_datetime in descending order (most recent first).
    All authenticated users (privilege levels 1, 2, 3) can access this endpoint.
    
    Args:
        user_id: ID of the teacher whose lectures to retrieve
        _: Privilege validation dependency (requires User level 3 or higher)
        
    Returns:
        List[LectureResponse]: List of lectures with details
        
    Raises:
        HTTPException 403: If user lacks valid privileges
        HTTPException 404: If no lectures found for the user
        HTTPException 500: If database operation fails
        
    Requirements:
        - 8.1: Retrieve all Lecture_Master records matching user_id
        - 8.2: Return lecture details including lec_id, lec_name, panel, 
               lecture_datetime, and attendance_status
        - 8.3: Order results by lecture_datetime DESC
    """
    # Privilege validation is handled by require_privilege(3) dependency
    
    try:
        # Query Lecture_Master for all lectures belonging to the user
        query = """
            SELECT lec_id, lec_name, panel, lecture_datetime, attendance_status
            FROM Lecture_Master
            WHERE user_id = ?
            ORDER BY lecture_datetime DESC
        """
        
        results = execute_query(query, (user_id,), fetch=True)
        
        # Check if any lectures were found
        if not results or len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No lectures found for user_id {user_id}"
            )
        
        # Convert database rows to LectureResponse models
        lectures = []
        for row in results:
            lectures.append(LectureResponse(
                lec_id=row.lec_id,
                lec_name=row.lec_name,
                panel=row.panel,
                lecture_datetime=row.lecture_datetime,
                attendance_status=row.attendance_status
            ))
        
        return lectures
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, etc.)
        raise
    except pyodbc.Error as e:
        # Handle database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving lectures: {str(e)}"
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while retrieving lectures: {str(e)}"
        )


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
        # Step 1: Validate lecture exists and belongs to authenticated user
        query = """
            SELECT lec_id, user_id, panel
            FROM Lecture_Master
            WHERE lec_id = ?
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
        
        # Step 2: Get inference engine instance
        inference_engine = get_inference_engine()
        
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
    except pyodbc.Error as e:
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
            WHERE lec_id = ?
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
        
        # Get face model instance for training
        face_model = get_face_model()
        
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
            
            # Retrieve face image from cache
            try:
                face_image = recognition_service.get_unidentified_face(face_id)
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Face ID {face_id} not found in cache. It may have already been processed."
                )
            
            # Handle "existing" action
            if action == "existing":
                # Verify PRN exists in Student_Master
                query = "SELECT prn, panel FROM Student_Master WHERE prn = ?"
                results = execute_query(query, (prn,), fetch=True)
                
                if not results or len(results) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Student with PRN {prn} not found in database"
                    )
                
                student = results[0]
                student_panel = student.panel
                
                # Insert into Attendance_Record
                insert_query = """
                    INSERT INTO Attendance_Record (lec_id, prn, status)
                    VALUES (?, ?, 'Present')
                """
                execute_query(insert_query, (request.lec_id, prn), fetch=False)
                
                # Perform incremental training
                training_service.incremental_train(face_model, prn, [face_image])
                
                # Remove face from cache
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
                query = "SELECT prn FROM Student_Master WHERE prn = ?"
                results = execute_query(query, (prn,), fetch=True)
                
                if results and len(results) > 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Student with PRN {prn} already exists in database"
                    )
                
                # Insert new student into Student_Master
                insert_student_query = """
                    INSERT INTO Student_Master (prn, name, panel)
                    VALUES (?, ?, ?)
                """
                execute_query(insert_student_query, (prn, name, panel), fetch=False)
                
                # Insert into Attendance_Record
                insert_attendance_query = """
                    INSERT INTO Attendance_Record (lec_id, prn, status)
                    VALUES (?, ?, 'Present')
                """
                execute_query(insert_attendance_query, (request.lec_id, prn), fetch=False)
                
                # Perform incremental training
                training_service.incremental_train(face_model, prn, [face_image])
                
                # Remove face from cache
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
    except pyodbc.Error as e:
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
            WHERE lec_id = ?
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
                "SELECT 1 FROM Attendance_Record WHERE lec_id = ? AND prn = ?",
                (request.lec_id, prn),
                fetch=True
            )
            if not existing:
                execute_query(
                    "INSERT INTO Attendance_Record (lec_id, prn, status) VALUES (?, ?, 'Present')",
                    (request.lec_id, prn),
                    fetch=False
                )

        # Step 3: Update attendance_status to 'Y' in Lecture_Master
        update_query = """
            UPDATE Lecture_Master
            SET attendance_status = 'Y'
            WHERE lec_id = ?
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
    except pyodbc.Error as e:
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
