"""
Dependency functions for the Role-Based Attendance System.

This module provides reusable dependency functions for FastAPI endpoints,
including privilege-based access control validation.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 15.5
"""

from fastapi import Header, HTTPException, status
from typing import Optional, Callable


def require_privilege(min_privilege_level: int) -> Callable:
    """
    Create a dependency function that validates user privilege level.
    
    This function returns a FastAPI dependency that checks if the user's
    privilege level meets the minimum required level for accessing an endpoint.
    
    Privilege levels (lower number = higher privilege):
    - 1: Super Admin (highest privilege)
    - 2: Admin
    - 3: User/Teacher (lowest privilege)
    
    Args:
        min_privilege_level: Minimum required privilege level (1, 2, or 3)
                           Users with privilege <= min_privilege_level can access
                           
    Returns:
        Callable: A dependency function that validates privilege from request headers
        
    Raises:
        ValueError: If min_privilege_level is not 1, 2, or 3
        
    Requirements:
        - 2.1: Support exactly three privilege levels (1, 2, 3)
        - 2.2: Grant Super Admin access when privilege=1
        - 2.3: Grant Admin access when privilege=2
        - 2.4: Grant User access when privilege=3
        - 2.5: Deny access to features requiring higher privileges
        - 15.5: Return 403 for insufficient privileges
        
    Example Usage:
        @router.get("/admin/endpoint", dependencies=[Depends(require_privilege(2))])
        async def admin_endpoint():
            # Only Super Admins (1) and Admins (2) can access
            return {"message": "Admin access granted"}
            
        @router.get("/superadmin/endpoint", dependencies=[Depends(require_privilege(1))])
        async def superadmin_endpoint():
            # Only Super Admins (1) can access
            return {"message": "Super Admin access granted"}
    """
    # Validate min_privilege_level is valid (Requirement 2.1)
    if min_privilege_level not in [1, 2, 3]:
        raise ValueError(f"Invalid privilege level: {min_privilege_level}. Must be 1, 2, or 3.")
    
    def privilege_dependency(
        privilege_level: Optional[int] = Header(None, alias="X-Privilege-Level")
    ) -> int:
        """
        Dependency function that validates user privilege from request header.
        
        Args:
            privilege_level: User's privilege level from X-Privilege-Level header
            
        Returns:
            int: The validated privilege level
            
        Raises:
            HTTPException 403: If privilege_level is None, invalid, or insufficient
            
        Requirements:
            - 2.5: Deny access when user privilege is insufficient
            - 15.5: Return 403 for authorization errors
        """
        # Check if privilege_level header is present
        if privilege_level is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Privilege level not provided in request header (X-Privilege-Level)."
            )
        
        # Validate privilege_level is a valid value (1, 2, or 3)
        if privilege_level not in [1, 2, 3]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Invalid privilege level: {privilege_level}. Must be 1, 2, or 3."
            )
        
        # Check if user has sufficient privilege (lower number = higher privilege)
        # User can access if their privilege_level <= min_privilege_level
        if privilege_level > min_privilege_level:
            privilege_names = {1: "Super Admin", 2: "Admin", 3: "User/Teacher"}
            required_privilege_name = privilege_names.get(min_privilege_level, "Unknown")
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. {required_privilege_name} privileges required (level {min_privilege_level} or higher)."
            )
        
        return privilege_level
    
    return privilege_dependency


def get_current_user_id(
    user_id: Optional[int] = Header(None, alias="X-User-Id")
) -> int:
    """
    Dependency function to extract and validate user ID from request header.
    
    This is a helper dependency that can be used alongside require_privilege()
    to get the authenticated user's ID from the request.
    
    Args:
        user_id: User's ID from X-User-Id header
        
    Returns:
        int: The validated user ID
        
    Raises:
        HTTPException 400: If user_id header is not provided
        
    Example Usage:
        @router.get("/user/profile")
        async def get_profile(
            user_id: int = Depends(get_current_user_id),
            _: int = Depends(require_privilege(3))
        ):
            # Get user profile for user_id
            return {"user_id": user_id}
    """
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID is required in request header (X-User-Id)."
        )
    
    return user_id
