"""
Super Admin module for the Role-Based Attendance System.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import bcrypt
import pymssql
from database import execute_query, get_db_connection
from dependencies import require_privilege


# -----------------------------
# Pydantic Models
# -----------------------------

class PrivilegeRequest(BaseModel):
    request_id: int
    user_id: int
    username: str
    name: str
    privilege_level: int


class ApproveRequestRequest(BaseModel):
    request_id: int
    user_id: int


class ApproveRequestResponse(BaseModel):
    message: str


class CreateAdminRequest(BaseModel):
    username: str
    password: str
    name: str
    email_id: EmailStr
    school: str
    department: str


class CreateAdminResponse(BaseModel):
    user_id: int
    message: str


router = APIRouter(prefix="/superadmin", tags=["Super Admin"])


# -----------------------------
# GET ALL PRIVILEGE REQUESTS
# -----------------------------
@router.get("/requests", response_model=List[PrivilegeRequest])
async def get_privilege_requests(_: int = Depends(require_privilege(1))):

    try:
        query = """
            SELECT r.request_id,
                   r.user_id,
                   l.username,
                   u.name,
                   l.privilege_level
            FROM Request_Master r
            JOIN Login_Master l ON r.user_id = l.user_id
            JOIN User_Master u ON r.user_id = u.user_id
            ORDER BY r.request_id
        """

        results = execute_query(query, fetch=True)

        return [
            PrivilegeRequest(
                request_id=row.request_id,
                user_id=row.user_id,
                username=row.username,
                name=row.name,
                privilege_level=row.privilege_level
            )
            for row in results
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# APPROVE PRIVILEGE REQUEST
# -----------------------------
@router.post("/approve-request", response_model=ApproveRequestResponse)
async def approve_privilege_request(
    request: ApproveRequestRequest,
    _: int = Depends(require_privilege(1))
):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Verify request exists
        cursor.execute("""
            SELECT request_id
            FROM Request_Master
            WHERE request_id = %s AND user_id = %s
        """, (request.request_id, request.user_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Request not found")

        # Update privilege_level in Login_Master
        cursor.execute("""
            UPDATE Login_Master
            SET privilege_level = 2
            WHERE user_id = %s
        """, (request.user_id,))

        # Delete request
        cursor.execute("""
            DELETE FROM Request_Master
            WHERE request_id = %s
        """, (request.request_id,))

        connection.commit()

        return ApproveRequestResponse(
            message="Privilege escalation approved"
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


# -----------------------------
# CREATE ADMIN
# -----------------------------
@router.post("/create-admin", response_model=CreateAdminResponse, status_code=201)
async def create_admin(
    request: CreateAdminRequest,
    _: int = Depends(require_privilege(1))
):

    connection = None
    cursor = None

    try:
        # Hash password
        password_hash = bcrypt.hashpw(
            request.password.encode(),
            bcrypt.gensalt()
        ).decode()

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check duplicate username
        cursor.execute("""
            SELECT user_id FROM Login_Master WHERE username = %s
        """, (request.username,))

        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Username already exists")

        # Insert into Login_Master (IDENTITY handles user_id)
        insert_login_query = """
    INSERT INTO Login_Master (username, password_hash, privilege_level)
    OUTPUT INSERTED.user_id
    VALUES (%s, %s, 2)
"""

        cursor.execute(insert_login_query, (request.username, password_hash))
        user_id = cursor.fetchone()[0]

        # Insert into User_Master
        cursor.execute("""
            INSERT INTO User_Master (user_id, name, email_id, school, department)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id,
            request.name,
            request.email_id,
            request.school,
            request.department
        ))

        connection.commit()

        return CreateAdminResponse(
            user_id=user_id,
            message="Admin created successfully"
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


# -----------------------------
# GET ALL USERS
# -----------------------------

class UserListItem(BaseModel):
    user_id: int
    username: str
    name: str
    privilege_level: int
    school: Optional[str] = None
    department: Optional[str] = None


@router.get("/users", response_model=List[UserListItem])
async def get_all_users(_: int = Depends(require_privilege(1))):
    try:
        query = """
            SELECT l.user_id, l.username, u.name, l.privilege_level,
                   u.school, u.department
            FROM Login_Master l
            JOIN User_Master u ON l.user_id = u.user_id
            ORDER BY l.privilege_level, u.name
        """
        results = execute_query(query, fetch=True)
        return [
            UserListItem(
                user_id=row.user_id,
                username=row.username,
                name=row.name,
                privilege_level=row.privilege_level,
                school=getattr(row, 'school', None),
                department=getattr(row, 'department', None),
            )
            for row in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# REVOKE USER RIGHTS
# -----------------------------

@router.delete("/revoke-user/{user_id}")
async def revoke_user(
    user_id: int,
    _: int = Depends(require_privilege(1))
):
    """
    Revoke elevated rights for a user by demoting them to privilege level 3 (Teacher).
    Superadmins (privilege 1) cannot be revoked.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check user exists and is not a superadmin
        cursor.execute(
            "SELECT privilege_level FROM Login_Master WHERE user_id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if row[0] == 1:
            raise HTTPException(status_code=400, detail="Cannot revoke superadmin rights")
        if row[0] == 3:
            raise HTTPException(status_code=400, detail="User already has teacher-level access")

        cursor.execute(
            "UPDATE Login_Master SET privilege_level = 3 WHERE user_id = %s",
            (user_id,)
        )
        connection.commit()
        return {"message": "User rights revoked. Account demoted to Teacher level."}

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
