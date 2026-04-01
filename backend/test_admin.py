"""
Unit tests for admin.py module.

Tests cover teacher creation and lecture scheduling endpoints.
"""

import pytest
from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from admin import router


# Create test client
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestScheduleLectureEndpoint:
    """Test suite for POST /admin/schedule-lecture endpoint."""
    
    @patch('admin.get_db_connection')
    def test_successful_lecture_scheduling(self, mock_get_db_connection):
        """
        Test successful lecture scheduling with all required fields.
        Requirements: 7.1, 7.2, 7.5
        """
        # Setup: Mock database connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        
        # Mock MAX(lec_id) query to return 10
        mock_cursor.fetchone.return_value = [10]
        
        # Execute: Schedule lecture with valid data
        lecture_datetime = "2024-01-15T10:00:00"
        response = client.post("/admin/schedule-lecture", 
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": 15,
                "school": "Engineering School",
                "department": "Computer Science",
                "lecorlab": "Lecture",
                "panel": "H",
                "lec_name": "Data Structures",
                "course_code": "CS201",
                "lecture_datetime": lecture_datetime
            }
        )
        
        # Verify: Response is successful
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["lec_id"] == 11  # MAX(10) + 1
        assert data["message"] == "Lecture scheduled successfully"
        
        # Verify: INSERT query was executed with correct parameters
        insert_call = mock_cursor.execute.call_args_list[1]  # Second call is INSERT
        assert "INSERT INTO Lecture_Master" in insert_call[0][0]
        assert "attendance_status" in insert_call[0][0]
        assert "'N'" in insert_call[0][0]  # Default attendance_status
        
        # Verify: Commit was called
        mock_connection.commit.assert_called_once()
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_sets_attendance_status_to_n(self, mock_get_db_connection):
        """
        Test that attendance_status is set to 'N' by default.
        Requirements: 7.2
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = [5]
        
        # Execute: Schedule lecture
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": 20,
                "school": "Science School",
                "department": "Physics",
                "lecorlab": "Lab",
                "panel": "I",
                "lec_name": "Quantum Mechanics",
                "course_code": "PHY301",
                "lecture_datetime": "2024-02-20T14:00:00"
            }
        )
        
        # Verify: Success
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify: attendance_status='N' in INSERT query
        insert_call = mock_cursor.execute.call_args_list[1]
        assert "'N'" in insert_call[0][0]
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_generates_unique_lec_id(self, mock_get_db_connection):
        """
        Test that unique lec_id is generated automatically.
        Requirements: 7.5
        """
        # Setup: Mock database with different MAX values
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        
        test_cases = [0, 10, 100, 999]
        
        for max_id in test_cases:
            mock_cursor.fetchone.return_value = [max_id]
            
            response = client.post("/admin/schedule-lecture",
                headers={"X-Privilege-Level": "2"},
                json={
                    "user_id": 1,
                    "school": "Test School",
                    "department": "Test Dept",
                    "lecorlab": "Lecture",
                    "panel": "A",
                    "lec_name": "Test Lecture",
                    "course_code": "TEST101",
                    "lecture_datetime": "2024-01-01T10:00:00"
                }
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["lec_id"] == max_id + 1
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_handles_null_max_id(self, mock_get_db_connection):
        """
        Test that lec_id generation handles empty table (NULL MAX).
        """
        # Setup: Mock database with NULL MAX (empty table)
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = [None]
        
        # Execute: Schedule first lecture
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": 1,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "First Lecture",
                "course_code": "FIRST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        # Verify: lec_id starts at 1
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["lec_id"] == 1
    
    def test_lecture_scheduling_missing_fields_returns_400(self):
        """
        Test that missing required fields return 400 error.
        Requirements: 7.3, 15.2
        """
        # Test missing each required field
        required_fields = [
            "user_id", "school", "department", "lecorlab", 
            "panel", "lec_name", "course_code", "lecture_datetime"
        ]
        
        base_data = {
            "user_id": 1,
            "school": "School",
            "department": "Dept",
            "lecorlab": "Lecture",
            "panel": "A",
            "lec_name": "Test",
            "course_code": "TEST",
            "lecture_datetime": "2024-01-01T10:00:00"
        }
        
        for field in required_fields:
            # Create request with missing field
            test_data = base_data.copy()
            del test_data[field]
            
            response = client.post("/admin/schedule-lecture",
                headers={"X-Privilege-Level": "2"},
                json=test_data
            )
            
            # Verify: 422 error for Pydantic validation
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_lecture_scheduling_without_admin_privilege_returns_403(self):
        """
        Test that non-admin users cannot schedule lectures.
        Requirements: 2.5, 15.5
        """
        # Test with privilege level 3 (Teacher)
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "3"},
            json={
                "user_id": 1,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "TEST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_lecture_scheduling_without_privilege_header_returns_403(self):
        """
        Test that requests without privilege header are denied.
        """
        response = client.post("/admin/schedule-lecture",
            json={
                "user_id": 1,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "TEST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_database_error_returns_500(self, mock_get_db_connection):
        """
        Test that database errors return 500 status code.
        Requirements: 15.1
        """
        # Setup: Simulate database error
        import pyodbc
        mock_get_db_connection.side_effect = pyodbc.Error("Database connection failed")
        
        # Execute: Attempt to schedule lecture
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": 1,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "TEST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        # Verify: 500 error returned
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database error" in response.json()["detail"]
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_rollback_on_error(self, mock_get_db_connection):
        """
        Test that transaction is rolled back on error.
        """
        # Setup: Mock database that fails on INSERT
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        
        # First call (MAX query) succeeds, second call (INSERT) fails
        mock_cursor.fetchone.return_value = [10]
        import pyodbc
        mock_cursor.execute.side_effect = [None, pyodbc.Error("Insert failed")]
        
        # Execute: Attempt to schedule lecture
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": 1,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "TEST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        # Verify: Rollback was called
        mock_connection.rollback.assert_called_once()
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_with_superadmin_privilege(self, mock_get_db_connection):
        """
        Test that Super Admin (level 1) can also schedule lectures.
        Requirements: 2.5
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = [5]
        
        # Execute: Schedule lecture with Super Admin privilege
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "1"},
            json={
                "user_id": 1,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "TEST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        # Verify: Success
        assert response.status_code == status.HTTP_201_CREATED
    
    @patch('admin.get_db_connection')
    def test_lecture_scheduling_associates_with_user_id(self, mock_get_db_connection):
        """
        Test that lecture is associated with the provided user_id.
        Requirements: 7.4
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = [0]
        
        # Execute: Schedule lecture with specific user_id
        test_user_id = 42
        response = client.post("/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": test_user_id,
                "school": "School",
                "department": "Dept",
                "lecorlab": "Lecture",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "TEST",
                "lecture_datetime": "2024-01-01T10:00:00"
            }
        )
        
        # Verify: Success
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify: user_id is in INSERT parameters
        insert_call = mock_cursor.execute.call_args_list[1]
        assert test_user_id in insert_call[0][1]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])



class TestEnrollStudentEndpoint:
    """Test suite for POST /admin/enroll-student endpoint."""
    
    @patch('admin.get_face_model')
    @patch('admin.incremental_train')
    @patch('admin.get_db_connection')
    def test_successful_student_enrollment(self, mock_get_db_connection, mock_incremental_train, mock_get_face_model):
        """
        Test successful student enrollment with exactly 25 images.
        Requirements: 6.1, 6.2, 6.4, 6.5
        """
        # Setup: Mock database connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        
        # Mock PRN check query to return None (student doesn't exist)
        mock_cursor.fetchone.return_value = None
        
        # Mock face model
        mock_face_model = MagicMock()
        mock_get_face_model.return_value = mock_face_model
        
        # Create 25 base64-encoded test images (1x1 red pixel)
        import base64
        from PIL import Image
        from io import BytesIO
        
        test_image = Image.new('RGB', (1, 1), color='red')
        buffer = BytesIO()
        test_image.save(buffer, format='PNG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        images = [base64_image] * 25
        
        # Execute: Enroll student with valid data
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN12345",
                "name": "Jane Smith",
                "panel": "H",
                "images": images
            }
        )
        
        # Verify: Response is successful
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["prn"] == "PRN12345"
        assert data["message"] == "Student enrolled successfully"
        
        # Verify: INSERT query was executed
        insert_call = mock_cursor.execute.call_args_list[1]  # Second call is INSERT
        assert "INSERT INTO Student_Master" in insert_call[0][0]
        assert "PRN12345" in insert_call[0][1]
        assert "Jane Smith" in insert_call[0][1]
        assert "H" in insert_call[0][1]
        
        # Verify: Commit was called
        mock_connection.commit.assert_called_once()
        
        # Verify: incremental_train was called
        mock_incremental_train.assert_called_once()
        call_args = mock_incremental_train.call_args
        assert call_args[0][1] == "PRN12345"  # PRN argument
        assert len(call_args[0][2]) == 25  # 25 face images
    
    @patch('admin.get_db_connection')
    def test_enrollment_with_wrong_image_count_returns_400(self, mock_get_db_connection):
        """
        Test that enrollment with not exactly 25 images returns 400.
        Requirements: 6.1, 15.2
        """
        # Test with various wrong counts
        for count in [0, 1, 10, 24, 26, 50]:
            images = ["base64_image"] * count
            
            response = client.post("/admin/enroll-student",
                headers={"X-Privilege-Level": "2"},
                json={
                    "prn": "PRN12345",
                    "name": "Jane Smith",
                    "panel": "H",
                    "images": images
                }
            )
            
            # Verify: 400 error returned
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Exactly 25 images required" in response.json()["detail"]
            assert str(count) in response.json()["detail"]
    
    @patch('admin.get_db_connection')
    def test_enrollment_with_duplicate_prn_returns_409(self, mock_get_db_connection):
        """
        Test that enrollment with existing PRN returns 409.
        Requirements: 6.6, 15.4
        """
        # Setup: Mock database to return existing student
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        
        # Mock PRN check query to return existing student
        mock_cursor.fetchone.return_value = ["PRN12345"]
        
        # Create valid base64 images
        import base64
        from PIL import Image
        from io import BytesIO
        
        test_image = Image.new('RGB', (1, 1), color='red')
        buffer = BytesIO()
        test_image.save(buffer, format='PNG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        images = [base64_image] * 25
        
        # Execute: Attempt to enroll student with duplicate PRN
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN12345",
                "name": "Jane Smith",
                "panel": "H",
                "images": images
            }
        )
        
        # Verify: 409 conflict error returned
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]
        assert "PRN12345" in response.json()["detail"]
    
    def test_enrollment_without_admin_privilege_returns_403(self):
        """
        Test that non-admin users cannot enroll students.
        Requirements: 2.5, 15.5
        """
        images = ["base64_image"] * 25
        
        # Test with privilege level 3 (Teacher)
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "3"},
            json={
                "prn": "PRN12345",
                "name": "Jane Smith",
                "panel": "H",
                "images": images
            }
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin privileges required" in response.json()["detail"]
    
    def test_enrollment_missing_required_fields_returns_400(self):
        """
        Test that missing required fields return 400 error.
        Requirements: 15.2
        """
        images = ["base64_image"] * 25
        
        # Test missing prn
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "name": "Jane Smith",
                "panel": "H",
                "images": images
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test missing name
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN12345",
                "panel": "H",
                "images": images
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test missing panel
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN12345",
                "name": "Jane Smith",
                "images": images
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @patch('admin.get_face_model')
    @patch('admin.incremental_train')
    @patch('admin.get_db_connection')
    def test_enrollment_rollback_on_training_error(self, mock_get_db_connection, mock_incremental_train, mock_get_face_model):
        """
        Test that database transaction is rolled back if training fails.
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = None
        
        # Mock face model
        mock_face_model = MagicMock()
        mock_get_face_model.return_value = mock_face_model
        
        # Mock training to fail
        mock_incremental_train.side_effect = RuntimeError("Training failed")
        
        # Create test images
        import base64
        from PIL import Image
        from io import BytesIO
        
        test_image = Image.new('RGB', (1, 1), color='red')
        buffer = BytesIO()
        test_image.save(buffer, format='PNG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        images = [base64_image] * 25
        
        # Execute: Attempt to enroll student
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN12345",
                "name": "Jane Smith",
                "panel": "H",
                "images": images
            }
        )
        
        # Verify: Error returned
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "training error" in response.json()["detail"].lower()
        
        # Verify: Rollback was called
        mock_connection.rollback.assert_called_once()
    
    @patch('admin.get_db_connection')
    def test_enrollment_with_invalid_base64_returns_400(self, mock_get_db_connection):
        """
        Test that invalid base64 images return 400 error.
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = None
        
        # Create list with one invalid base64 string
        images = ["invalid_base64_data"] * 25
        
        # Execute: Attempt to enroll student
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN12345",
                "name": "Jane Smith",
                "panel": "H",
                "images": images
            }
        )
        
        # Verify: 400 error returned
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to decode image" in response.json()["detail"]
    
    @patch('admin.get_face_model')
    @patch('admin.incremental_train')
    @patch('admin.get_db_connection')
    def test_enrollment_associates_student_with_panel(self, mock_get_db_connection, mock_incremental_train, mock_get_face_model):
        """
        Test that student is associated with exactly one panel.
        Requirements: 6.7
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_db_connection.return_value = mock_connection
        mock_cursor.fetchone.return_value = None
        
        # Mock face model
        mock_face_model = MagicMock()
        mock_get_face_model.return_value = mock_face_model
        
        # Create test images
        import base64
        from PIL import Image
        from io import BytesIO
        
        test_image = Image.new('RGB', (1, 1), color='red')
        buffer = BytesIO()
        test_image.save(buffer, format='PNG')
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        images = [base64_image] * 25
        
        # Execute: Enroll student with specific panel
        test_panel = "I"
        response = client.post("/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN99999",
                "name": "Test Student",
                "panel": test_panel,
                "images": images
            }
        )
        
        # Verify: Success
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify: Panel is in INSERT parameters
        insert_call = mock_cursor.execute.call_args_list[1]
        assert test_panel in insert_call[0][1]
