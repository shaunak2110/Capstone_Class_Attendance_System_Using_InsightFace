"""
Unit tests for the dependencies module.

This module tests the privilege validation dependency functions including
require_privilege() and get_current_user_id().

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 15.5
"""

import pytest
from fastapi import HTTPException, status
from dependencies import require_privilege, get_current_user_id


class TestRequirePrivilege:
    """Test suite for require_privilege() dependency function."""
    
    def test_require_privilege_creates_dependency_function(self):
        """Test that require_privilege returns a callable dependency function."""
        dependency = require_privilege(1)
        assert callable(dependency)
    
    def test_require_privilege_validates_min_privilege_level(self):
        """Test that require_privilege raises ValueError for invalid privilege levels."""
        with pytest.raises(ValueError, match="Invalid privilege level"):
            require_privilege(0)
        
        with pytest.raises(ValueError, match="Invalid privilege level"):
            require_privilege(4)
        
        with pytest.raises(ValueError, match="Invalid privilege level"):
            require_privilege(-1)
    
    def test_require_privilege_accepts_valid_levels(self):
        """Test that require_privilege accepts valid privilege levels 1, 2, 3."""
        # Should not raise any exceptions
        require_privilege(1)
        require_privilege(2)
        require_privilege(3)
    
    def test_superadmin_dependency_allows_superadmin(self):
        """Test that Super Admin (level 1) can access Super Admin endpoints."""
        dependency = require_privilege(1)
        
        # Super Admin should be allowed
        result = dependency(privilege_level=1)
        assert result == 1
    
    def test_superadmin_dependency_denies_admin(self):
        """Test that Admin (level 2) cannot access Super Admin endpoints."""
        dependency = require_privilege(1)
        
        # Admin should be denied
        with pytest.raises(HTTPException) as exc_info:
            dependency(privilege_level=2)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Super Admin" in exc_info.value.detail
    
    def test_superadmin_dependency_denies_user(self):
        """Test that User (level 3) cannot access Super Admin endpoints."""
        dependency = require_privilege(1)
        
        # User should be denied
        with pytest.raises(HTTPException) as exc_info:
            dependency(privilege_level=3)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Super Admin" in exc_info.value.detail
    
    def test_admin_dependency_allows_superadmin(self):
        """Test that Super Admin (level 1) can access Admin endpoints."""
        dependency = require_privilege(2)
        
        # Super Admin should be allowed (higher privilege)
        result = dependency(privilege_level=1)
        assert result == 1
    
    def test_admin_dependency_allows_admin(self):
        """Test that Admin (level 2) can access Admin endpoints."""
        dependency = require_privilege(2)
        
        # Admin should be allowed
        result = dependency(privilege_level=2)
        assert result == 2
    
    def test_admin_dependency_denies_user(self):
        """Test that User (level 3) cannot access Admin endpoints."""
        dependency = require_privilege(2)
        
        # User should be denied
        with pytest.raises(HTTPException) as exc_info:
            dependency(privilege_level=3)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin" in exc_info.value.detail
    
    def test_user_dependency_allows_all_valid_levels(self):
        """Test that all privilege levels can access User endpoints."""
        dependency = require_privilege(3)
        
        # Super Admin should be allowed
        result = dependency(privilege_level=1)
        assert result == 1
        
        # Admin should be allowed
        result = dependency(privilege_level=2)
        assert result == 2
        
        # User should be allowed
        result = dependency(privilege_level=3)
        assert result == 3
    
    def test_dependency_denies_missing_privilege_header(self):
        """Test that missing privilege header returns 403."""
        dependency = require_privilege(3)
        
        with pytest.raises(HTTPException) as exc_info:
            dependency(privilege_level=None)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "not provided" in exc_info.value.detail
    
    def test_dependency_denies_invalid_privilege_value(self):
        """Test that invalid privilege values return 403."""
        dependency = require_privilege(3)
        
        # Test invalid privilege value 0
        with pytest.raises(HTTPException) as exc_info:
            dependency(privilege_level=0)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Invalid privilege level" in exc_info.value.detail
        
        # Test invalid privilege value 4
        with pytest.raises(HTTPException) as exc_info:
            dependency(privilege_level=4)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Invalid privilege level" in exc_info.value.detail
    
    def test_privilege_hierarchy_enforcement(self):
        """Test that privilege hierarchy is correctly enforced (lower number = higher privilege)."""
        # Super Admin endpoint (requires level 1)
        superadmin_dep = require_privilege(1)
        
        # Level 1 can access
        assert superadmin_dep(privilege_level=1) == 1
        
        # Level 2 cannot access
        with pytest.raises(HTTPException):
            superadmin_dep(privilege_level=2)
        
        # Level 3 cannot access
        with pytest.raises(HTTPException):
            superadmin_dep(privilege_level=3)
        
        # Admin endpoint (requires level 2)
        admin_dep = require_privilege(2)
        
        # Level 1 can access (higher privilege)
        assert admin_dep(privilege_level=1) == 1
        
        # Level 2 can access
        assert admin_dep(privilege_level=2) == 2
        
        # Level 3 cannot access
        with pytest.raises(HTTPException):
            admin_dep(privilege_level=3)
        
        # User endpoint (requires level 3)
        user_dep = require_privilege(3)
        
        # All levels can access
        assert user_dep(privilege_level=1) == 1
        assert user_dep(privilege_level=2) == 2
        assert user_dep(privilege_level=3) == 3


class TestGetCurrentUserId:
    """Test suite for get_current_user_id() dependency function."""
    
    def test_get_current_user_id_returns_user_id(self):
        """Test that get_current_user_id returns the user ID from header."""
        user_id = get_current_user_id(user_id=123)
        assert user_id == 123
    
    def test_get_current_user_id_with_different_values(self):
        """Test that get_current_user_id works with different user IDs."""
        assert get_current_user_id(user_id=1) == 1
        assert get_current_user_id(user_id=999) == 999
        assert get_current_user_id(user_id=42) == 42
    
    def test_get_current_user_id_missing_header_returns_400(self):
        """Test that missing user ID header returns 400 Bad Request."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(user_id=None)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "User ID is required" in exc_info.value.detail
        assert "X-User-Id" in exc_info.value.detail


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
