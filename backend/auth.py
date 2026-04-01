"""
Authentication module for the Role-Based Attendance System.

This module provides user authentication functionality including login endpoint,
credential validation, and password verification using bcrypt.

Requirements: 1.1, 1.2, 13.2
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import bcrypt
from typing import Optional
import pyodbc
from database import execute_query


# Pydantic models for request/response
class LoginRequest(BaseModel):
    """
    Request model for user login.
    
    Attributes:
        username: User's login username
        password: User's plaintext password (will be verified against hashed password)
    """
    username: str
    password: str


class LoginResponse(BaseModel):
    """
    Response model for successful login.
    
    Attributes:
        user_id: Unique identifier for the user
        username: User's login username
        privilege_level: User's access level (1=Super Admin, 2=Admin, 3=User/Teacher)
    """
    user_id: int
    username: str
    privilege_level: int


# Create router for authentication endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest):
    """
    Authenticate user with username and password.
    
    This endpoint validates user credentials against the Login_Master table,
    verifies the password using bcrypt, and returns user information on success.
    
    Args:
        request: LoginRequest containing username and password
        
    Returns:
        LoginResponse: User information including user_id, username, and privilege_level
        
    Raises:
        HTTPException 401: Invalid credentials (username not found or password incorrect)
        HTTPException 500: Database or server error
        
    Requirements:
        - 1.1: Return user_id, username, and privilege_level on successful authentication
        - 1.2: Return 401 error for invalid credentials
        - 13.2: Verify password using bcrypt.checkpw()
        
    Example:
        POST /auth/login
        {
            "username": "teacher1",
            "password": "securepassword123"
        }
        
        Response 200:
        {
            "user_id": 5,
            "username": "teacher1",
            "privilege_level": 3
        }
    """
    try:
        # Query Login_Master table for username
        query = """
            SELECT user_id, username, password_hash, privilege_level
            FROM Login_Master
            WHERE username = ?
        """
        results = execute_query(query, (request.username,), fetch=True)
        
        # Check if user exists
        if not results or len(results) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Extract user data from query result
        user_row = results[0]
        user_id = user_row.user_id
        username = user_row.username
        password_hash = user_row.password_hash
        privilege_level = user_row.privilege_level
        
        # Verify password using bcrypt
        # Convert password_hash to bytes if it's a string
        if isinstance(password_hash, str):
            password_hash_bytes = password_hash.encode('utf-8')
        else:
            password_hash_bytes = password_hash
        
        # Convert plaintext password to bytes
        password_bytes = request.password.encode('utf-8')
        
        # Check password using bcrypt.checkpw()
        if not bcrypt.checkpw(password_bytes, password_hash_bytes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Return user information on success
        return LoginResponse(
            user_id=user_id,
            username=username,
            privilege_level=privilege_level
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (401 errors)
        raise
        
    except pyodbc.Error as e:
        # Database error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
        
    except Exception as e:
        # Unexpected server error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}"
        )
