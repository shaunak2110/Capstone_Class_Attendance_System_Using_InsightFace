"""
Main application entry point for the Role-Based Attendance System.

This module initializes the FastAPI application, configures CORS middleware,
registers all routers, and sets up the face recognition model at startup.

To run the application:
    uvicorn main:app --reload

Or from the command line:
    python main.py

Requirements: 13.4, 14.1, 14.2, 14.5
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import sys
import os
import logging
import pyodbc

# Import routers from all modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import router as auth_router
from admin import router as admin_router
from admin import set_face_model
from user import set_face_model as set_user_face_model, set_inference_engine
from model.inference import InferenceEngine
from user import router as user_router
from superadmin import router as superadmin_router

# Import FaceModel for startup initialization
from model.face_model import FaceModel


# Global face model instance
face_model = None


# Configure logging for error tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Loads the FaceModel at startup to ensure it's ready for inference
    and student enrollment operations.
    """
    global face_model
    
    # Startup: Load the face recognition model
    print("Loading face recognition model...")
    try:
        model_path = os.getenv("FACE_MODEL_PATH", "trained_face_brain.pth")
        face_model = FaceModel(model_path=model_path)
        print(f"Face model loaded successfully with {len(face_model.get_enrolled_students())} enrolled students")
        set_face_model(face_model)
        # Share the same face_model and inference_engine with user.py
        inference_engine = InferenceEngine(face_model)
        set_user_face_model(face_model)
        set_inference_engine(inference_engine)
    except Exception as e:
        print(f"Warning: Failed to load face model: {e}")
        print("The application will start but face recognition features may not work correctly")
    
    yield
    
    # Shutdown: Cleanup if needed
    print("Shutting down application...")


# Initialize FastAPI application
app = FastAPI(
    title="Role-Based Attendance System",
    description="Automated attendance tracking system with facial recognition and role-based access control",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# Global Exception Handlers
# ============================================================================
# These handlers ensure consistent error responses across all endpoints
# Requirements: 13.5, 15.1, 15.2, 15.3, 15.4, 15.5


@app.exception_handler(pyodbc.IntegrityError)
async def integrity_error_handler(request: Request, exc: pyodbc.IntegrityError):
    """
    Handle database integrity constraint violations (e.g., unique constraints, foreign keys).
    
    Returns HTTP 409 Conflict for duplicate entries or constraint violations.
    Logs full error details for debugging.
    
    Requirements: 15.4
    """
    error_message = str(exc)
    logger.error(f"Database integrity error on {request.method} {request.url.path}: {error_message}")
    
    # Determine if it's a duplicate/unique constraint violation
    if "unique" in error_message.lower() or "duplicate" in error_message.lower():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "Conflict",
                "message": "A record with this identifier already exists",
                "details": {"type": "duplicate_entry"}
            }
        )
    
    # Other integrity errors (foreign key violations, etc.)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "Conflict",
            "message": "Database constraint violation",
            "details": {"type": "integrity_constraint"}
        }
    )


@app.exception_handler(pyodbc.Error)
async def database_error_handler(request: Request, exc: pyodbc.Error):
    """
    Handle general database errors (connection failures, query errors, etc.).
    
    Returns HTTP 500 Internal Server Error.
    Logs full error details for debugging.
    
    Requirements: 15.1
    """
    error_message = str(exc)
    logger.error(f"Database error on {request.method} {request.url.path}: {error_message}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "message": "A database error occurred while processing your request",
            "details": {"type": "database_error"}
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors (missing fields, invalid formats, type errors).
    
    Returns HTTP 400 Bad Request with detailed field-level errors.
    Lists all validation errors, not just the first one.
    
    Requirements: 15.2
    """
    errors = exc.errors()
    logger.warning(f"Validation error on {request.method} {request.url.path}: {errors}")
    
    # Format validation errors for clear client feedback
    formatted_errors = []
    for error in errors:
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        formatted_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation Error",
            "message": "Request validation failed. Please check the required fields and formats.",
            "details": {
                "validation_errors": formatted_errors
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unexpected exceptions.
    
    Returns HTTP 500 Internal Server Error.
    Logs full exception details including traceback for debugging.
    
    This handler catches any exception not handled by more specific handlers.
    
    Requirements: 13.5, 15.1
    """
    import traceback
    
    error_message = str(exc)
    error_traceback = traceback.format_exc()
    
    logger.error(
        f"Unexpected error on {request.method} {request.url.path}: {error_message}\n"
        f"Traceback:\n{error_traceback}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing your request",
            "details": {"type": "unexpected_error"}
        }
    )


# Note: HTTPException is handled by FastAPI's default handler, which already
# provides appropriate status codes and messages. We rely on the existing
# HTTPException usage throughout the codebase for:
# - 401 Unauthorized (invalid credentials)
# - 403 Forbidden (insufficient privileges) - Requirement 15.5
# - 404 Not Found (resource not found) - Requirement 15.3
# - 409 Conflict (handled above for database integrity)
# - 500 Internal Server Error (handled above for database and general errors)


# Configure CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers from all modules
app.include_router(auth_router)
app.include_router(superadmin_router)
app.include_router(admin_router)
app.include_router(user_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify the application is running.
    
    Returns:
        dict: Status message and model information
    """
    model_status = "loaded" if face_model is not None else "not loaded"
    enrolled_count = len(face_model.get_enrolled_students()) if face_model else 0
    
    return {
        "status": "healthy",
        "message": "Role-Based Attendance System is running",
        "face_model_status": model_status,
        "enrolled_students": enrolled_count
    }


# Entry point for running with uvicorn
if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload
    )
