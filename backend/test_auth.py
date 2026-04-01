"""
Unit tests for auth.py module.

Tests cover login endpoint, credential validation, and password verification.
"""

import pytest
import bcrypt
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from auth import router, LoginRequest, LoginResponse


# Create test client
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestLoginEndpoint:
    """Test suite for POST /auth/login endpoint."""
    
    @patch('auth.execute_query')
    def test_successful_login_returns_user_data(self, mock_execute_query):
        """
        Test successful login with valid credentials returns complete user data.
        Requirements: 1.1
        """
        # Setup: Create mock user with hashed password
        password = "securepassword123"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        mock_row = MagicMock()
        mock_row.user_id = 5
        mock_row.username = "teacher1"
        mock_row.password_hash = password_hash
        mock_row.privilege_level = 3
        
        mock_execute_query.return_value = [mock_row]
        
        # Execute: Login with valid credentials
        response = client.post("/auth/login", json={
            "username": "teacher1",
            "password": password
        })
        
        # Verify: Response contains complete user data
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == 5
        assert data["username"] == "teacher1"
        assert data["privilege_level"] == 3
        
        # Verify query was called correctly
        mock_execute_query.assert_called_once()
        call_args = mock_execute_query.call_args
        assert "SELECT" in call_args[0][0]
        assert "Login_Master" in call_args[0][0]
        assert call_args[0][1] == ("teacher1",)
    
    @patch('auth.execute_query')
    def test_login_with_nonexistent_username_returns_401(self, mock_execute_query):
        """
        Test login with non-existent username returns 401 error.
        Requirements: 1.2
        """
        # Setup: No user found
        mock_execute_query.return_value = []
        
        # Execute: Login with non-existent username
        response = client.post("/auth/login", json={
            "username": "nonexistent_user",
            "password": "anypassword"
        })
        
        # Verify: 401 error returned
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid credentials" in response.json()["detail"]
    
    @patch('auth.execute_query')
    def test_login_with_incorrect_password_returns_401(self, mock_execute_query):
        """
        Test login with incorrect password returns 401 error.
        Requirements: 1.2, 13.2
        """
        # Setup: Create mock user with hashed password
        correct_password = "correctpassword"
        password_hash = bcrypt.hashpw(correct_password.encode('utf-8'), bcrypt.gensalt())
        
        mock_row = MagicMock()
        mock_row.user_id = 5
        mock_row.username = "teacher1"
        mock_row.password_hash = password_hash
        mock_row.privilege_level = 3
        
        mock_execute_query.return_value = [mock_row]
        
        # Execute: Login with incorrect password
        response = client.post("/auth/login", json={
            "username": "teacher1",
            "password": "wrongpassword"
        })
        
        # Verify: 401 error returned
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid credentials" in response.json()["detail"]
    
    @patch('auth.execute_query')
    def test_login_verifies_password_with_bcrypt(self, mock_execute_query):
        """
        Test that login uses bcrypt.checkpw() for password verification.
        Requirements: 13.2
        """
        # Setup: Create user with bcrypt hashed password
        password = "testpassword"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        mock_row = MagicMock()
        mock_row.user_id = 1
        mock_row.username = "admin"
        mock_row.password_hash = password_hash
        mock_row.privilege_level = 1
        
        mock_execute_query.return_value = [mock_row]
        
        # Execute: Login with correct password
        response = client.post("/auth/login", json={
            "username": "admin",
            "password": password
        })
        
        # Verify: Login successful (bcrypt verification passed)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_id"] == 1
    
    @patch('auth.execute_query')
    def test_login_handles_string_password_hash(self, mock_execute_query):
        """
        Test that login handles password_hash stored as string in database.
        """
        # Setup: Password hash as string (common in databases)
        password = "testpass"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        password_hash_str = password_hash.decode('utf-8')
        
        mock_row = MagicMock()
        mock_row.user_id = 2
        mock_row.username = "user2"
        mock_row.password_hash = password_hash_str  # String format
        mock_row.privilege_level = 2
        
        mock_execute_query.return_value = [mock_row]
        
        # Execute: Login
        response = client.post("/auth/login", json={
            "username": "user2",
            "password": password
        })
        
        # Verify: Login successful
        assert response.status_code == status.HTTP_200_OK
    
    @patch('auth.execute_query')
    def test_login_with_different_privilege_levels(self, mock_execute_query):
        """
        Test login returns correct privilege_level for different user types.
        """
        test_cases = [
            (1, "superadmin", 1),  # Super Admin
            (2, "admin", 2),        # Admin
            (3, "teacher", 3)       # Teacher/User
        ]
        
        for user_id, username, privilege_level in test_cases:
            password = "password123"
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            mock_row = MagicMock()
            mock_row.user_id = user_id
            mock_row.username = username
            mock_row.password_hash = password_hash
            mock_row.privilege_level = privilege_level
            
            mock_execute_query.return_value = [mock_row]
            
            response = client.post("/auth/login", json={
                "username": username,
                "password": password
            })
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["privilege_level"] == privilege_level
    
    @patch('auth.execute_query')
    def test_login_database_error_returns_500(self, mock_execute_query):
        """
        Test that database errors return 500 status code.
        """
        # Setup: Simulate database error
        import pyodbc
        mock_execute_query.side_effect = pyodbc.Error("Database connection failed")
        
        # Execute: Attempt login
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        
        # Verify: 500 error returned
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database error" in response.json()["detail"]
    
    def test_login_request_validation(self):
        """
        Test that missing required fields are validated.
        """
        # Test missing username
        response = client.post("/auth/login", json={
            "password": "testpass"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test missing password
        response = client.post("/auth/login", json={
            "username": "testuser"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test empty request body
        response = client.post("/auth/login", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginModels:
    """Test suite for Pydantic models."""
    
    def test_login_request_model(self):
        """Test LoginRequest model validation."""
        request = LoginRequest(username="testuser", password="testpass")
        assert request.username == "testuser"
        assert request.password == "testpass"
    
    def test_login_response_model(self):
        """Test LoginResponse model validation."""
        response = LoginResponse(
            user_id=1,
            username="admin",
            privilege_level=1
        )
        assert response.user_id == 1
        assert response.username == "admin"
        assert response.privilege_level == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
