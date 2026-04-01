"""
Unit tests for superadmin.py module.

Tests cover privilege escalation endpoints and admin creation.
"""

import pytest
import bcrypt
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from superadmin import router


# Create test client
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestGetPrivilegeRequests:
    """Test suite for GET /superadmin/requests endpoint."""
    
    @patch('superadmin.execute_query')
    def test_get_requests_returns_all_pending_requests(self, mock_execute_query):
        """
        Test that GET /superadmin/requests returns all pending requests.
        Requirements: 3.1
        """
        # Setup: Mock pending requests
        mock_row1 = MagicMock()
        mock_row1.request_id = 1
        mock_row1.user_id = 5
        mock_row1.username = "teacher1"
        mock_row1.name = "John Doe"
        mock_row1.privilege = 3
        
        mock_row2 = MagicMock()
        mock_row2.request_id = 2
        mock_row2.user_id = 6
        mock_row2.username = "teacher2"
        mock_row2.name = "Jane Smith"
        mock_row2.privilege = 3
        
        mock_execute_query.return_value = [mock_row1, mock_row2]
        
        # Execute: Get requests as Super Admin
        response = client.get("/superadmin/requests", headers={"X-Privilege-Level": "1"})
        
        # Verify: All requests returned
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["request_id"] == 1
        assert data[0]["username"] == "teacher1"
        assert data[1]["request_id"] == 2
        assert data[1]["username"] == "teacher2"
    
    def test_get_requests_requires_superadmin_privilege(self):
        """
        Test that non-super-admins cannot access requests endpoint.
        Requirements: 2.5, 15.5
        """
        # Test with Admin privilege (level 2)
        response = client.get("/superadmin/requests", headers={"X-Privilege-Level": "2"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Super Admin privileges required" in response.json()["detail"]
        
        # Test with User privilege (level 3)
        response = client.get("/superadmin/requests", headers={"X-Privilege-Level": "3"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Test with no privilege header
        response = client.get("/superadmin/requests")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestApprovePrivilegeRequest:
    """Test suite for POST /superadmin/approve-request endpoint."""
    
    @patch('superadmin.get_db_connection')
    def test_approve_request_updates_both_tables(self, mock_get_connection):
        """
        Test that approving a request updates privilege in both tables.
        Requirements: 3.2, 3.3, 3.4, 3.5
        """
        # Setup: Mock database connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        # Mock request exists
        mock_request_row = MagicMock()
        mock_request_row.request_id = 1
        mock_request_row.user_id = 5
        mock_cursor.fetchone.return_value = mock_request_row
        
        # Mock successful update (1 row affected)
        mock_cursor.rowcount = 1
        
        # Execute: Approve request
        response = client.post(
            "/superadmin/approve-request",
            json={"request_id": 1, "user_id": 5},
            headers={"X-Privilege-Level": "1"}
        )
        
        # Verify: Success response
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Privilege escalation approved"
        
        # Verify: All SQL operations were executed
        assert mock_cursor.execute.call_count >= 4  # verify, update login, update user, delete
        mock_connection.commit.assert_called_once()
    
    @patch('superadmin.get_db_connection')
    def test_approve_nonexistent_request_returns_404(self, mock_get_connection):
        """
        Test that approving non-existent request returns 404.
        """
        # Setup: Mock database connection
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        # Mock request not found
        mock_cursor.fetchone.return_value = None
        
        # Execute: Approve non-existent request
        response = client.post(
            "/superadmin/approve-request",
            json={"request_id": 999, "user_id": 999},
            headers={"X-Privilege-Level": "1"}
        )
        
        # Verify: 404 error
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()
    
    def test_approve_request_requires_superadmin_privilege(self):
        """
        Test that non-super-admins cannot approve requests.
        Requirements: 2.5, 15.5
        """
        response = client.post(
            "/superadmin/approve-request",
            json={"request_id": 1, "user_id": 5},
            headers={"X-Privilege-Level": "2"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCreateAdmin:
    """Test suite for POST /superadmin/create-admin endpoint."""
    
    @patch('superadmin.get_db_connection')
    def test_create_admin_inserts_into_both_tables(self, mock_get_connection):
        """
        Test that creating admin inserts into both Login_Master and User_Master.
        Requirements: 4.1, 4.2, 4.3
        """
        # Setup: Mock database connection
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        # Mock username doesn't exist
        mock_cursor.fetchone.side_effect = [None, MagicMock(user_id=10)]
        
        # Execute: Create admin
        response = client.post(
            "/superadmin/create-admin",
            json={
                "username": "newadmin",
                "password": "securepass123",
                "name": "New Admin",
                "email_id": "admin@example.com",
                "school": "Engineering",
                "department": "CS"
            },
            headers={"X-Privilege-Level": "1"}
        )
        
        # Verify: Success response
        assert response.status_code == status.HTTP_201_CREATED
        assert "user_id" in response.json()
        assert response.json()["message"] == "Admin created successfully"
        
        # Verify: Both inserts were executed
        assert mock_cursor.execute.call_count >= 3  # check, get max id, insert login, insert user
        mock_connection.commit.assert_called_once()
    
    @patch('superadmin.get_db_connection')
    def test_create_admin_hashes_password(self, mock_get_connection):
        """
        Test that password is hashed using bcrypt.
        Requirements: 13.1
        """
        # Setup: Mock database
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        mock_cursor.fetchone.side_effect = [None, MagicMock(user_id=5)]
        
        # Execute: Create admin
        password = "plaintext123"
        response = client.post(
            "/superadmin/create-admin",
            json={
                "username": "admin2",
                "password": password,
                "name": "Admin Two",
                "email_id": "admin2@example.com",
                "school": "Engineering",
                "department": "CS"
            },
            headers={"X-Privilege-Level": "1"}
        )
        
        # Verify: Password was hashed (check that bcrypt hash was used in insert)
        assert response.status_code == status.HTTP_201_CREATED
        
        # Get the password argument from the insert call
        insert_calls = [call for call in mock_cursor.execute.call_args_list 
                       if 'INSERT INTO Login_Master' in str(call)]
        assert len(insert_calls) > 0
        
        # The hashed password should not be the plaintext password
        insert_args = insert_calls[0][0][1]
        hashed_password = insert_args[2]
        assert hashed_password != password
        assert len(hashed_password) > 50  # bcrypt hashes are long
    
    @patch('superadmin.get_db_connection')
    def test_create_admin_duplicate_username_returns_409(self, mock_get_connection):
        """
        Test that duplicate username returns 409 conflict.
        Requirements: 4.4
        """
        # Setup: Mock database with existing username
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_connection
        
        # Mock username already exists
        existing_user = MagicMock()
        existing_user.user_id = 5
        mock_cursor.fetchone.return_value = existing_user
        
        # Execute: Try to create admin with existing username
        response = client.post(
            "/superadmin/create-admin",
            json={
                "username": "existingadmin",
                "password": "pass123",
                "name": "Admin",
                "email_id": "admin@example.com",
                "school": "Engineering",
                "department": "CS"
            },
            headers={"X-Privilege-Level": "1"}
        )
        
        # Verify: 409 conflict
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"].lower()
    
    def test_create_admin_missing_fields_returns_400(self):
        """
        Test that missing required fields returns 400.
        Requirements: 4.5, 15.2
        """
        # Test missing name
        response = client.post(
            "/superadmin/create-admin",
            json={
                "username": "admin",
                "password": "pass",
                "email_id": "admin@example.com",
                "school": "Engineering",
                "department": "CS"
            },
            headers={"X-Privilege-Level": "1"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_admin_requires_superadmin_privilege(self):
        """
        Test that non-super-admins cannot create admins.
        Requirements: 2.5, 15.5
        """
        response = client.post(
            "/superadmin/create-admin",
            json={
                "username": "admin",
                "password": "pass",
                "name": "Admin",
                "email_id": "admin@example.com",
                "school": "Engineering",
                "department": "CS"
            },
            headers={"X-Privilege-Level": "2"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
