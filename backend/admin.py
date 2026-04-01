from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import datetime as dt
import bcrypt
import pyodbc
import base64
import numpy as np
from io import BytesIO
from PIL import Image

from database import get_db_connection
from services.training_service import incremental_train
from model.face_model import FaceModel
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
    user_id: int
    school: str
    department: str
    lecorlab: str
    panel: str
    lec_name: str
    course_code: str
    lecture_datetime: dt.datetime


class LectureResponse(BaseModel):
    lec_id: int
    message: str


class EnrollStudentRequest(BaseModel):
    prn: str
    name: str
    panel: str
    images: List[str]


class EnrollStudentResponse(BaseModel):
    message: str
    prn: str


# ============================
# CREATE TEACHER
# ============================

@router.post("/create-teacher", response_model=CreateTeacherResponse, status_code=201)
async def create_teacher(
    request: CreateTeacherRequest,
    _: int = Depends(require_privilege(2))
):
    connection = None
    cursor = None

    try:
        password_hash = bcrypt.hashpw(
            request.password.encode(),
            bcrypt.gensalt()
        ).decode()

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check duplicate username
        cursor.execute(
            "SELECT user_id FROM Login_Master WHERE username = ?",
            (request.username,)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Username already exists")

        # Insert into Login_Master (IDENTITY auto-generates user_id)
        cursor.execute("""
            INSERT INTO Login_Master (username, password_hash, privilege_level)
            OUTPUT INSERTED.user_id
            VALUES (?, ?, 3)
        """, (request.username, password_hash))

        user_id = cursor.fetchone()[0]

        # Insert into User_Master
        cursor.execute("""
            INSERT INTO User_Master (user_id, name, email_id, school, department, mob)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            request.name,
            request.email_id,
            request.school,
            request.department,
            request.mob
        ))

        connection.commit()

        return CreateTeacherResponse(
            user_id=user_id,
            message="Teacher created successfully"
        )

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

@router.post("/schedule-lecture", response_model=LectureResponse, status_code=201)
async def schedule_lecture(
    request: ScheduleLectureRequest,
    _: int = Depends(require_privilege(2))
):
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO Lecture_Master
            (user_id, school, department, lecorlab, panel,
             lec_name, course_code, lecture_datetime, attendance_status)
            OUTPUT INSERTED.lec_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'N')
        """, (
            request.user_id,
            request.school,
            request.department,
            request.lecorlab,
            request.panel,
            request.lec_name,
            request.course_code,
            request.lecture_datetime
        ))

        lec_id = cursor.fetchone()[0]

        connection.commit()

        return LectureResponse(
            lec_id=lec_id,
            message="Lecture scheduled successfully"
        )

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
# FACE MODEL GLOBAL
# ============================

_face_model: Optional[FaceModel] = None


def set_face_model(face_model: FaceModel):
    global _face_model
    _face_model = face_model


def get_face_model() -> FaceModel:
    if _face_model is None:
        raise RuntimeError("Face model not initialized.")
    return _face_model


# ============================
# ENROLL STUDENT
# ============================

@router.post("/enroll-student", response_model=EnrollStudentResponse, status_code=201)
async def enroll_student(
    request: EnrollStudentRequest,
    _: int = Depends(require_privilege(2))
):
    if len(request.images) != 25:
        raise HTTPException(status_code=400, detail="Exactly 25 images required")

    connection = None
    cursor = None
    face_images = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if PRN already exists - if so, re-enroll (update)
        cursor.execute(
            "SELECT prn FROM Student_Master WHERE prn = ?",
            (request.prn,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing student record
            cursor.execute("""
                UPDATE Student_Master SET name = ?, panel = ?
                WHERE prn = ?
            """, (request.name, request.panel, request.prn))
        else:
            # Insert new student
            cursor.execute("""
                INSERT INTO Student_Master (prn, name, panel)
                VALUES (?, ?, ?)
            """, (request.prn, request.name, request.panel))

        connection.commit()

        # Decode images and detect faces using MTCNN
        from model.inference import InferenceEngine
        face_model = get_face_model()
        inference_engine = InferenceEngine(face_model)

        for img_b64 in request.images:
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]

            image_bytes = base64.b64decode(img_b64)
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            # Pass PIL image directly to avoid BGR/RGB conversion issues
            # detect_faces accepts PIL images and skips the BGR->RGB conversion

            try:
                cropped_faces = inference_engine.detect_faces(image)
                # Take the first (largest) face from each image
                face_images.append(cropped_faces[0])
            except ValueError:
                # No face detected in this image — skip it
                continue

        if len(face_images) < 1:
            raise HTTPException(
                status_code=400,
                detail="No faces detected in any of the provided images. Please upload clear face photos."
            )

        # Train model - remove old embeddings first if re-enrolling
        face_model.remove_student(request.prn)  # no-op if not enrolled yet
        incremental_train(face_model, request.prn, face_images)

        action = "re-enrolled" if existing else "enrolled"
        return EnrollStudentResponse(
            message=f"Student {action} successfully",
            prn=request.prn
        )

    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()