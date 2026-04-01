"""
Unit tests for the User/Teacher module.

Tests the lecture retrieval endpoint functionality.

Requirements: 8.1, 8.2, 8.3
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from user import router
import pyodbc
from unittest.mock import patch, MagicMock
from datetime import datetime


# Create a test FastAPI app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


@patch('user.execute_query')
def test_get_lectures_success(mock_execute_query):
    """
    Test successful retrieval of lectures for a user.
    
    Validates:
        - 8.1: Retrieves all lectures matching user_id
        - 8.2: Returns complete lecture details
        - 8.3: Orders by lecture_datetime DESC
    """
    # Mock database results
    mock_row1 = MagicMock()
    mock_row1.lec_id = 3
    mock_row1.lec_name = "Lecture 3"
    mock_row1.panel = "A"
    mock_row1.lecture_datetime = datetime(2024, 1, 17, 9, 0, 0)
    mock_row1.attendance_status = "N"
    
    mock_row2 = MagicMock()
    mock_row2.lec_id = 2
    mock_row2.lec_name = "Lecture 2"
    mock_row2.panel = "B"
    mock_row2.lecture_datetime = datetime(2024, 1, 16, 11, 0, 0)
    mock_row2.attendance_status = "Y"
    
    mock_row3 = MagicMock()
    mock_row3.lec_id = 1
    mock_row3.lec_name = "Lecture 1"
    mock_row3.panel = "A"
    mock_row3.lecture_datetime = datetime(2024, 1, 15, 10, 0, 0)
    mock_row3.attendance_status = "N"
    
    mock_execute_query.return_value = [mock_row1, mock_row2, mock_row3]
    
    # Make request with valid privilege level
    response = client.get(
        "/user/lectures/1",
        headers={"X-Privilege-Level": "3"}
    )
    
    # Verify response
    assert response.status_code == 200
    lectures = response.json()
    
    # Should return 3 lectures
    assert len(lectures) == 3
    
    # Verify all required fields are present
    for lecture in lectures:
        assert "lec_id" in lecture
        assert "lec_name" in lecture
        assert "panel" in lecture
        assert "lecture_datetime" in lecture
        assert "attendance_status" in lecture
    
    # Verify ordering by lecture_datetime DESC (most recent first)
    assert lectures[0]["lec_name"] == "Lecture 3"  # 2024-01-17
    assert lectures[1]["lec_name"] == "Lecture 2"  # 2024-01-16
    assert lectures[2]["lec_name"] == "Lecture 1"  # 2024-01-15
    
    # Verify the query was called with correct parameters
    mock_execute_query.assert_called_once()
    call_args = mock_execute_query.call_args
    assert call_args[0][1] == (1,)  # user_id parameter
    assert call_args[1]['fetch'] == True


@patch('user.execute_query')
def test_get_lectures_no_lectures_found(mock_execute_query):
    """
    Test retrieval when user has no lectures.
    
    Validates:
        - Returns 404 when no lectures exist for user_id
    """
    # Mock empty result
    mock_execute_query.return_value = []
    
    # Use a non-existent user_id
    response = client.get(
        "/user/lectures/99999",
        headers={"X-Privilege-Level": "3"}
    )
    
    # Should return 404
    assert response.status_code == 404
    assert "No lectures found" in response.json()["detail"]


def test_get_lectures_invalid_privilege():
    """
    Test retrieval with invalid privilege level.
    
    Validates:
        - Returns 403 for invalid privilege levels
    """
    response = client.get(
        "/user/lectures/1",
        headers={"X-Privilege-Level": "0"}
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_get_lectures_missing_privilege_header():
    """
    Test retrieval without privilege level header.
    
    Validates:
        - Returns 403 when privilege header is missing
    """
    response = client.get("/user/lectures/1")
    
    # Should return 403
    assert response.status_code == 403


@patch('user.execute_query')
def test_get_lectures_filters_by_user_id(mock_execute_query):
    """
    Test that lectures are properly filtered by user_id.
    
    Validates:
        - 8.1: Only returns lectures for the specified user_id
    """
    # Mock database results for user_id 1
    mock_row1 = MagicMock()
    mock_row1.lec_id = 1
    mock_row1.lec_name = "Lecture 1"
    mock_row1.panel = "A"
    mock_row1.lecture_datetime = datetime(2024, 1, 15, 10, 0, 0)
    mock_row1.attendance_status = "N"
    
    mock_row2 = MagicMock()
    mock_row2.lec_id = 2
    mock_row2.lec_name = "Lecture 2"
    mock_row2.panel = "B"
    mock_row2.lecture_datetime = datetime(2024, 1, 16, 11, 0, 0)
    mock_row2.attendance_status = "Y"
    
    mock_execute_query.return_value = [mock_row2, mock_row1]
    
    # Get lectures for user_id 1
    response = client.get(
        "/user/lectures/1",
        headers={"X-Privilege-Level": "3"}
    )
    
    assert response.status_code == 200
    lectures = response.json()
    
    # Should return 2 lectures
    assert len(lectures) == 2
    
    # Verify the query was called with user_id 1
    mock_execute_query.assert_called_once()
    call_args = mock_execute_query.call_args
    assert call_args[0][1] == (1,)  # user_id parameter


@patch('user.execute_query')
def test_get_lectures_database_error(mock_execute_query):
    """
    Test handling of database errors.
    
    Validates:
        - Returns 500 for database errors
    """
    # Mock database error
    mock_execute_query.side_effect = pyodbc.Error("Database connection failed")
    
    response = client.get(
        "/user/lectures/1",
        headers={"X-Privilege-Level": "3"}
    )
    
    # Should return 500
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]


@patch('user.execute_query')
def test_get_lectures_response_format(mock_execute_query):
    """
    Test that response format matches LectureResponse model.
    
    Validates:
        - 8.2: Returns complete lecture details in correct format
    """
    # Mock database result
    mock_row = MagicMock()
    mock_row.lec_id = 123
    mock_row.lec_name = "Data Structures"
    mock_row.panel = "H"
    mock_row.lecture_datetime = datetime(2024, 1, 20, 14, 30, 0)
    mock_row.attendance_status = "N"
    
    mock_execute_query.return_value = [mock_row]
    
    response = client.get(
        "/user/lectures/5",
        headers={"X-Privilege-Level": "3"}
    )
    
    assert response.status_code == 200
    lectures = response.json()
    
    # Verify response structure
    assert len(lectures) == 1
    lecture = lectures[0]
    
    assert lecture["lec_id"] == 123
    assert lecture["lec_name"] == "Data Structures"
    assert lecture["panel"] == "H"
    assert "2024-01-20" in lecture["lecture_datetime"]
    assert lecture["attendance_status"] == "N"


@patch('user.execute_query')
def test_get_lectures_with_different_privilege_levels(mock_execute_query):
    """
    Test that all valid privilege levels can access the endpoint.
    
    Validates:
        - Users with privilege levels 1, 2, and 3 can access
    """
    # Mock database result
    mock_row = MagicMock()
    mock_row.lec_id = 1
    mock_row.lec_name = "Test Lecture"
    mock_row.panel = "A"
    mock_row.lecture_datetime = datetime(2024, 1, 15, 10, 0, 0)
    mock_row.attendance_status = "N"
    
    mock_execute_query.return_value = [mock_row]
    
    # Test with privilege level 1 (Super Admin)
    response = client.get("/user/lectures/1", headers={"X-Privilege-Level": "1"})
    assert response.status_code == 200
    
    # Test with privilege level 2 (Admin)
    response = client.get("/user/lectures/1", headers={"X-Privilege-Level": "2"})
    assert response.status_code == 200
    
    # Test with privilege level 3 (Teacher)
    response = client.get("/user/lectures/1", headers={"X-Privilege-Level": "3"})
    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# Tests for attendance marking endpoint

@patch('user.get_inference_engine')
@patch('user.recognition_service.recognize_students')
@patch('user.execute_query')
def test_mark_attendance_success(mock_execute_query, mock_recognize_students, mock_get_inference_engine):
    """
    Test successful attendance marking with identified students.
    
    Validates:
        - 9.1: Accepts multiple images and lecture_id
        - 9.7: Returns identified students and unidentified faces
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    # Mock recognition service response
    mock_recognize_students.return_value = (
        [
            {'prn': 'PRN001', 'name': 'John Doe', 'similarity': 0.85},
            {'prn': 'PRN002', 'name': 'Jane Smith', 'similarity': 0.92}
        ],
        [
            {'face_id': 'uuid-123', 'image': 'base64_image_data'}
        ]
    )
    
    # Mock inference engine
    mock_get_inference_engine.return_value = MagicMock()
    
    # Make request
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1", "base64_image_2"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Check identified students
    assert len(data["identified_students"]) == 2
    assert data["identified_students"][0]["prn"] == "PRN001"
    assert data["identified_students"][0]["name"] == "John Doe"
    assert data["identified_students"][0]["similarity"] == 0.85
    
    # Check unidentified faces
    assert len(data["unidentified_faces"]) == 1
    assert data["unidentified_faces"][0]["face_id"] == "uuid-123"
    
    # Verify recognition service was called
    mock_recognize_students.assert_called_once()


@patch('user.execute_query')
def test_mark_attendance_lecture_not_found(mock_execute_query):
    """
    Test attendance marking when lecture doesn't exist.
    
    Validates:
        - Returns 404 when lecture not found
    """
    # Mock empty result (lecture not found)
    mock_execute_query.return_value = []
    
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 99999,
            "images": ["base64_image_1"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 404
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@patch('user.execute_query')
def test_mark_attendance_wrong_user(mock_execute_query):
    """
    Test attendance marking when lecture belongs to different user.
    
    Validates:
        - Returns 403 when lecture doesn't belong to authenticated user
    """
    # Mock lecture belonging to different user
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 10  # Different from requesting user
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1"]
        },
        headers={
            "X-User-Id": "5",  # Requesting user is 5
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "does not belong to user" in response.json()["detail"]


def test_mark_attendance_missing_images():
    """
    Test attendance marking with no images.
    
    Validates:
        - 15.2: Returns 400 for validation errors
    """
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": []
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "At least one image is required" in response.json()["detail"]


def test_mark_attendance_missing_user_id():
    """
    Test attendance marking without user ID header.
    
    Validates:
        - 15.2: Returns 400 for missing user ID
    """
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1"]
        },
        headers={
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "User ID is required" in response.json()["detail"]


def test_mark_attendance_invalid_privilege():
    """
    Test attendance marking with invalid privilege level.
    
    Validates:
        - Returns 403 for invalid privilege levels
    """
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "0"
        }
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


@patch('user.get_inference_engine')
@patch('user.recognition_service.recognize_students')
@patch('user.execute_query')
def test_mark_attendance_recognition_error(mock_execute_query, mock_recognize_students, mock_get_inference_engine):
    """
    Test handling of recognition service errors.
    
    Validates:
        - Returns 400 for validation errors from recognition service
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    # Mock recognition service error
    mock_recognize_students.side_effect = ValueError("Invalid base64 image data")
    
    # Mock inference engine
    mock_get_inference_engine.return_value = MagicMock()
    
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["invalid_base64"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "Validation error" in response.json()["detail"]


@patch('user.get_inference_engine')
@patch('user.recognition_service.recognize_students')
@patch('user.execute_query')
def test_mark_attendance_database_error(mock_execute_query, mock_recognize_students, mock_get_inference_engine):
    """
    Test handling of database errors during attendance marking.
    
    Validates:
        - Returns 500 for database errors
    """
    # Mock database error
    mock_execute_query.side_effect = pyodbc.Error("Database connection failed")
    
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 500
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]


@patch('user.get_inference_engine')
@patch('user.recognition_service.recognize_students')
@patch('user.execute_query')
def test_mark_attendance_no_faces_detected(mock_execute_query, mock_recognize_students, mock_get_inference_engine):
    """
    Test attendance marking when no faces are detected in images.
    
    Validates:
        - Returns empty lists when no faces detected
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    # Mock recognition service response with no faces
    mock_recognize_students.return_value = ([], [])
    
    # Mock inference engine
    mock_get_inference_engine.return_value = MagicMock()
    
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 200 with empty lists
    assert response.status_code == 200
    data = response.json()
    assert len(data["identified_students"]) == 0
    assert len(data["unidentified_faces"]) == 0


@patch('user.get_inference_engine')
@patch('user.recognition_service.recognize_students')
@patch('user.execute_query')
def test_mark_attendance_response_format(mock_execute_query, mock_recognize_students, mock_get_inference_engine):
    """
    Test that response format matches MarkAttendanceResponse model.
    
    Validates:
        - 9.7: Response contains correct structure
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    # Mock recognition service response
    mock_recognize_students.return_value = (
        [{'prn': 'PRN001', 'name': 'John Doe', 'similarity': 0.85}],
        [{'face_id': 'uuid-123', 'image': 'base64_data'}]
    )
    
    # Mock inference engine
    mock_get_inference_engine.return_value = MagicMock()
    
    response = client.post(
        "/user/mark-attendance",
        json={
            "lec_id": 1,
            "images": ["base64_image_1"]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "identified_students" in data
    assert "unidentified_faces" in data
    
    # Verify identified student structure
    student = data["identified_students"][0]
    assert "prn" in student
    assert "name" in student
    assert "similarity" in student
    
    # Verify unidentified face structure
    face = data["unidentified_faces"][0]
    assert "face_id" in face
    assert "image" in face



# Tests for face resolution endpoint

@patch('user.get_face_model')
@patch('user.training_service.incremental_train')
@patch('user.recognition_service.get_unidentified_face')
@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_existing_student(
    mock_execute_query,
    mock_remove_face,
    mock_get_face,
    mock_train,
    mock_get_model
):
    """
    Test resolving an unidentified face to an existing student.
    
    Validates:
        - 10.1: Verifies PRN exists in Student_Master
        - 10.2: Marks student as present for the lecture
        - 10.3: Performs incremental training
    """
    import numpy as np
    
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Mock student verification query
    mock_student = MagicMock()
    mock_student.prn = "PRN001"
    mock_student.panel = "H"
    
    # Setup execute_query to return different results for different queries
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            return [mock_student]
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face image retrieval
    mock_face_image = np.zeros((112, 112, 3), dtype=np.uint8)
    mock_get_face.return_value = mock_face_image
    
    # Mock face model
    mock_face_model = MagicMock()
    mock_get_model.return_value = mock_face_model
    
    # Make request
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "existing",
                    "prn": "PRN001"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["resolved_count"] == 1
    assert "Successfully resolved" in data["message"]
    
    # Verify face was retrieved from cache
    mock_get_face.assert_called_once_with("uuid-123")
    
    # Verify incremental training was called
    mock_train.assert_called_once()
    
    # Verify face was removed from cache
    mock_remove_face.assert_called_once_with("uuid-123")


@patch('user.get_face_model')
@patch('user.training_service.incremental_train')
@patch('user.recognition_service.get_unidentified_face')
@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_new_student(
    mock_execute_query,
    mock_remove_face,
    mock_get_face,
    mock_train,
    mock_get_model
):
    """
    Test resolving an unidentified face as a new student.
    
    Validates:
        - 10.5: Inserts new student into Student_Master
        - 10.6: Performs incremental training for new student
    """
    import numpy as np
    
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Setup execute_query to return different results for different queries
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            return []  # PRN doesn't exist
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face image retrieval
    mock_face_image = np.zeros((112, 112, 3), dtype=np.uint8)
    mock_get_face.return_value = mock_face_image
    
    # Mock face model
    mock_face_model = MagicMock()
    mock_get_model.return_value = mock_face_model
    
    # Make request
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-456",
                    "action": "new",
                    "prn": "PRN999",
                    "name": "New Student",
                    "panel": "H"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["resolved_count"] == 1
    
    # Verify face was retrieved from cache
    mock_get_face.assert_called_once_with("uuid-456")
    
    # Verify incremental training was called
    mock_train.assert_called_once()
    
    # Verify face was removed from cache
    mock_remove_face.assert_called_once_with("uuid-456")


@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_discard(mock_execute_query, mock_remove_face):
    """
    Test discarding an unidentified face.
    
    Validates:
        - 10.4: Skips processing for action="discard"
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    # Make request
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-789",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["resolved_count"] == 1
    
    # Verify face was removed from cache
    mock_remove_face.assert_called_once_with("uuid-789")


@patch('user.execute_query')
def test_resolve_faces_invalid_prn(mock_execute_query):
    """
    Test resolving face with non-existent PRN for action="existing".
    
    Validates:
        - Returns 400 when PRN doesn't exist in database
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Setup execute_query to return different results
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query:
            return []  # PRN doesn't exist
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face retrieval
    with patch('user.recognition_service.get_unidentified_face') as mock_get_face:
        import numpy as np
        mock_get_face.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        
        response = client.post(
            "/user/resolve-faces",
            json={
                "lec_id": 1,
                "resolutions": [
                    {
                        "face_id": "uuid-123",
                        "action": "existing",
                        "prn": "INVALID_PRN"
                    }
                ]
            },
            headers={
                "X-User-Id": "5",
                "X-Privilege-Level": "3"
            }
        )
    
    # Should return 400
    assert response.status_code == 400
    assert "not found in database" in response.json()["detail"]


@patch('user.execute_query')
def test_resolve_faces_missing_prn(mock_execute_query):
    """
    Test resolving face without PRN for action="existing".
    
    Validates:
        - Returns 400 when PRN is missing for actions that require it
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "existing"
                    # Missing PRN
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "PRN is required" in response.json()["detail"]


@patch('user.execute_query')
def test_resolve_faces_missing_name_for_new(mock_execute_query):
    """
    Test resolving face without name for action="new".
    
    Validates:
        - Returns 400 when name is missing for new student
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Setup execute_query to return different results
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            return []  # PRN doesn't exist
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face retrieval
    with patch('user.recognition_service.get_unidentified_face') as mock_get_face:
        import numpy as np
        mock_get_face.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        
        response = client.post(
            "/user/resolve-faces",
            json={
                "lec_id": 1,
                "resolutions": [
                    {
                        "face_id": "uuid-123",
                        "action": "new",
                        "prn": "PRN999",
                        "panel": "H"
                        # Missing name
                    }
                ]
            },
            headers={
                "X-User-Id": "5",
                "X-Privilege-Level": "3"
            }
        )
    
    # Should return 400
    assert response.status_code == 400
    assert "Name is required" in response.json()["detail"]


@patch('user.execute_query')
def test_resolve_faces_missing_panel_for_new(mock_execute_query):
    """
    Test resolving face without panel for action="new".
    
    Validates:
        - Returns 400 when panel is missing for new student
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Setup execute_query to return different results
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            return []  # PRN doesn't exist
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face retrieval
    with patch('user.recognition_service.get_unidentified_face') as mock_get_face:
        import numpy as np
        mock_get_face.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        
        response = client.post(
            "/user/resolve-faces",
            json={
                "lec_id": 1,
                "resolutions": [
                    {
                        "face_id": "uuid-123",
                        "action": "new",
                        "prn": "PRN999",
                        "name": "New Student"
                        # Missing panel
                    }
                ]
            },
            headers={
                "X-User-Id": "5",
                "X-Privilege-Level": "3"
            }
        )
    
    # Should return 400
    assert response.status_code == 400
    assert "Panel is required" in response.json()["detail"]


@patch('user.execute_query')
def test_resolve_faces_invalid_action(mock_execute_query):
    """
    Test resolving face with invalid action.
    
    Validates:
        - Returns 400 for invalid action values
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "invalid_action"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "Invalid action" in response.json()["detail"]


@patch('user.execute_query')
def test_resolve_faces_lecture_not_found(mock_execute_query):
    """
    Test resolving faces when lecture doesn't exist.
    
    Validates:
        - Returns 404 when lecture not found
    """
    # Mock empty result (lecture not found)
    mock_execute_query.return_value = []
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 99999,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 404
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@patch('user.execute_query')
def test_resolve_faces_wrong_user(mock_execute_query):
    """
    Test resolving faces when lecture belongs to different user.
    
    Validates:
        - Returns 403 when lecture doesn't belong to authenticated user
    """
    # Mock lecture belonging to different user
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 10  # Different from requesting user
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-User-Id": "5",  # Requesting user is 5
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "does not belong to user" in response.json()["detail"]


def test_resolve_faces_missing_user_id():
    """
    Test resolving faces without user ID header.
    
    Validates:
        - Returns 400 for missing user ID
    """
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "User ID is required" in response.json()["detail"]


def test_resolve_faces_empty_resolutions():
    """
    Test resolving faces with empty resolutions list.
    
    Validates:
        - Returns 400 when no resolutions provided
    """
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": []
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "At least one face resolution is required" in response.json()["detail"]


def test_resolve_faces_invalid_privilege():
    """
    Test resolving faces with invalid privilege level.
    
    Validates:
        - Returns 403 for invalid privilege levels
    """
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "0"
        }
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


@patch('user.recognition_service.get_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_face_not_in_cache(mock_execute_query, mock_get_face):
    """
    Test resolving face that's not in cache.
    
    Validates:
        - Returns 400 when face_id not found in cache
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    mock_execute_query.return_value = [mock_lecture]
    
    # Mock face not found in cache
    mock_get_face.side_effect = KeyError("Face ID not found")
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-nonexistent",
                    "action": "existing",
                    "prn": "PRN001"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "not found in cache" in response.json()["detail"]


@patch('user.get_face_model')
@patch('user.training_service.incremental_train')
@patch('user.recognition_service.get_unidentified_face')
@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_multiple_resolutions(
    mock_execute_query,
    mock_remove_face,
    mock_get_face,
    mock_train,
    mock_get_model
):
    """
    Test resolving multiple faces with different actions.
    
    Validates:
        - Handles multiple resolutions in single request
        - Returns correct count of resolved faces
    """
    import numpy as np
    
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Mock student verification query
    mock_student = MagicMock()
    mock_student.prn = "PRN001"
    mock_student.panel = "H"
    
    # Setup execute_query to return different results
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            if params[0] == "PRN001":
                return [mock_student]
            else:
                return []  # New student PRN doesn't exist
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face image retrieval
    mock_face_image = np.zeros((112, 112, 3), dtype=np.uint8)
    mock_get_face.return_value = mock_face_image
    
    # Mock face model
    mock_face_model = MagicMock()
    mock_get_model.return_value = mock_face_model
    
    # Make request with multiple resolutions
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-1",
                    "action": "existing",
                    "prn": "PRN001"
                },
                {
                    "face_id": "uuid-2",
                    "action": "new",
                    "prn": "PRN999",
                    "name": "New Student",
                    "panel": "H"
                },
                {
                    "face_id": "uuid-3",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["resolved_count"] == 3
    
    # Verify training was called twice (for existing and new)
    assert mock_train.call_count == 2
    
    # Verify all faces were removed from cache
    assert mock_remove_face.call_count == 3


@patch('user.get_face_model')
@patch('user.training_service.incremental_train')
@patch('user.recognition_service.get_unidentified_face')
@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_duplicate_prn_for_new(
    mock_execute_query,
    mock_remove_face,
    mock_get_face,
    mock_train,
    mock_get_model
):
    """
    Test resolving face as new student with existing PRN.
    
    Validates:
        - Returns 400 when trying to create student with duplicate PRN
    """
    import numpy as np
    
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Mock student already exists
    mock_student = MagicMock()
    mock_student.prn = "PRN001"
    
    # Setup execute_query to return different results
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            return [mock_student]  # PRN already exists
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face image retrieval
    mock_face_image = np.zeros((112, 112, 3), dtype=np.uint8)
    mock_get_face.return_value = mock_face_image
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "new",
                    "prn": "PRN001",
                    "name": "Duplicate Student",
                    "panel": "H"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@patch('user.get_face_model')
@patch('user.training_service.incremental_train')
@patch('user.recognition_service.get_unidentified_face')
@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_training_error(
    mock_execute_query,
    mock_remove_face,
    mock_get_face,
    mock_train,
    mock_get_model
):
    """
    Test handling of training service errors.
    
    Validates:
        - Returns 400 for validation errors from training service
    """
    import numpy as np
    
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.panel = "H"
    
    # Mock student verification query
    mock_student = MagicMock()
    mock_student.prn = "PRN001"
    mock_student.panel = "H"
    
    # Setup execute_query
    def execute_query_side_effect(query, params, fetch):
        if "Lecture_Master" in query:
            return [mock_lecture]
        elif "Student_Master" in query and "SELECT" in query:
            return [mock_student]
        else:
            return []
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock face image retrieval
    mock_face_image = np.zeros((112, 112, 3), dtype=np.uint8)
    mock_get_face.return_value = mock_face_image
    
    # Mock face model
    mock_face_model = MagicMock()
    mock_get_model.return_value = mock_face_model
    
    # Mock training error
    mock_train.side_effect = ValueError("Invalid face image format")
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "existing",
                    "prn": "PRN001"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "Validation error" in response.json()["detail"]


@patch('user.get_face_model')
@patch('user.training_service.incremental_train')
@patch('user.recognition_service.get_unidentified_face')
@patch('user.recognition_service.remove_unidentified_face')
@patch('user.execute_query')
def test_resolve_faces_database_error(
    mock_execute_query,
    mock_remove_face,
    mock_get_face,
    mock_train,
    mock_get_model
):
    """
    Test handling of database errors during face resolution.
    
    Validates:
        - Returns 500 for database errors
    """
    # Mock database error
    mock_execute_query.side_effect = pyodbc.Error("Database connection failed")
    
    response = client.post(
        "/user/resolve-faces",
        json={
            "lec_id": 1,
            "resolutions": [
                {
                    "face_id": "uuid-123",
                    "action": "discard"
                }
            ]
        },
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 500
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]



# Tests for attendance finalization endpoint

@patch('user.csv_service.generate_attendance_csv')
@patch('user.execute_query')
def test_finalize_attendance_success(mock_execute_query, mock_generate_csv):
    """
    Test successful attendance finalization.
    
    Validates:
        - 11.1: Updates attendance_status to 'Y' in Lecture_Master
        - 11.2: Generates CSV file with attendance records
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.attendance_status = "N"
    
    # Setup execute_query to return lecture for SELECT, None for UPDATE
    def execute_query_side_effect(query, params, fetch):
        if "SELECT" in query:
            return [mock_lecture]
        else:
            return None
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock CSV generation
    mock_generate_csv.return_value = "Attendance Records/H_Python_Programming_2024-01-15_14-30.csv"
    
    # Make request
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Attendance finalized successfully"
    assert "Attendance Records" in data["csv_path"]
    
    # Verify CSV generation was called with correct lecture ID
    mock_generate_csv.assert_called_once_with(1)
    
    # Verify UPDATE query was executed
    update_calls = [call for call in mock_execute_query.call_args_list if "UPDATE" in str(call)]
    assert len(update_calls) > 0


@patch('user.execute_query')
def test_finalize_attendance_lecture_not_found(mock_execute_query):
    """
    Test finalization when lecture doesn't exist.
    
    Validates:
        - Returns 404 when lecture not found
    """
    # Mock empty result (lecture not found)
    mock_execute_query.return_value = []
    
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 99999},
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 404
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@patch('user.execute_query')
def test_finalize_attendance_wrong_user(mock_execute_query):
    """
    Test finalization when lecture belongs to different user.
    
    Validates:
        - Returns 403 when lecture doesn't belong to authenticated user
    """
    # Mock lecture belonging to different user
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 10  # Different from requesting user
    mock_lecture.attendance_status = "N"
    mock_execute_query.return_value = [mock_lecture]
    
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-User-Id": "5",  # Requesting user is 5
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "does not belong to user" in response.json()["detail"]


def test_finalize_attendance_missing_user_id():
    """
    Test finalization without user ID header.
    
    Validates:
        - Returns 400 for missing user ID
    """
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "User ID is required" in response.json()["detail"]


def test_finalize_attendance_invalid_privilege():
    """
    Test finalization with invalid privilege level.
    
    Validates:
        - Returns 403 for invalid privilege levels
    """
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "0"
        }
    )
    
    # Should return 403
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


@patch('user.csv_service.generate_attendance_csv')
@patch('user.execute_query')
def test_finalize_attendance_csv_generation_error(mock_execute_query, mock_generate_csv):
    """
    Test handling of CSV generation errors.
    
    Validates:
        - Returns 400 for validation errors from CSV service
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.attendance_status = "N"
    
    # Setup execute_query to return lecture for SELECT, None for UPDATE
    def execute_query_side_effect(query, params, fetch):
        if "SELECT" in query:
            return [mock_lecture]
        else:
            return None
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock CSV generation error
    mock_generate_csv.side_effect = ValueError("No students found in panel")
    
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 400
    assert response.status_code == 400
    assert "Validation error" in response.json()["detail"]


@patch('user.execute_query')
def test_finalize_attendance_database_error(mock_execute_query):
    """
    Test handling of database errors during finalization.
    
    Validates:
        - Returns 500 for database errors
    """
    # Mock database error
    mock_execute_query.side_effect = pyodbc.Error("Database connection failed")
    
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    # Should return 500
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]


@patch('user.csv_service.generate_attendance_csv')
@patch('user.execute_query')
def test_finalize_attendance_response_format(mock_execute_query, mock_generate_csv):
    """
    Test that response format matches FinalizeAttendanceResponse model.
    
    Validates:
        - Response contains message and csv_path fields
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.attendance_status = "N"
    
    # Setup execute_query to return lecture for SELECT, None for UPDATE
    def execute_query_side_effect(query, params, fetch):
        if "SELECT" in query:
            return [mock_lecture]
        else:
            return None
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock CSV generation
    csv_path = "Attendance Records/H_Data_Structures_2024-01-20_10-00.csv"
    mock_generate_csv.return_value = csv_path
    
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={
            "X-User-Id": "5",
            "X-Privilege-Level": "3"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "message" in data
    assert "csv_path" in data
    assert data["csv_path"] == csv_path
    assert isinstance(data["message"], str)


@patch('user.csv_service.generate_attendance_csv')
@patch('user.execute_query')
def test_finalize_attendance_with_different_privilege_levels(mock_execute_query, mock_generate_csv):
    """
    Test that all valid privilege levels can finalize attendance.
    
    Validates:
        - Users with privilege levels 1, 2, and 3 can finalize
    """
    # Mock lecture validation query
    mock_lecture = MagicMock()
    mock_lecture.lec_id = 1
    mock_lecture.user_id = 5
    mock_lecture.attendance_status = "N"
    
    # Setup execute_query to return lecture for SELECT, None for UPDATE
    def execute_query_side_effect(query, params, fetch):
        if "SELECT" in query:
            return [mock_lecture]
        else:
            return None
    
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Mock CSV generation
    mock_generate_csv.return_value = "Attendance Records/test.csv"
    
    # Test with privilege level 1 (Super Admin)
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={"X-User-Id": "5", "X-Privilege-Level": "1"}
    )
    assert response.status_code == 200
    
    # Reset mocks
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Test with privilege level 2 (Admin)
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={"X-User-Id": "5", "X-Privilege-Level": "2"}
    )
    assert response.status_code == 200
    
    # Reset mocks
    mock_execute_query.side_effect = execute_query_side_effect
    
    # Test with privilege level 3 (Teacher)
    response = client.post(
        "/user/finalize-attendance",
        json={"lec_id": 1},
        headers={"X-User-Id": "5", "X-Privilege-Level": "3"}
    )
    assert response.status_code == 200
