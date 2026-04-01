import { Navigate } from 'react-router-dom';

export default function ProtectedRoute({ children, minPrivilege = 1 }) {
  const token = localStorage.getItem('token');
  const privilegeLevel = parseInt(localStorage.getItem('privilege_level'), 10);

  // Not logged in
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  // privilege_level: 1=superadmin, 2=admin, 3=teacher
  // Lower number = higher privilege, so allow if level <= minPrivilege
  // OR if minPrivilege is an array, check inclusion
  if (Array.isArray(minPrivilege)) {
    if (!minPrivilege.includes(privilegeLevel)) {
      return <Navigate to="/unauthorized" replace />;
    }
  } else {
    if (privilegeLevel > minPrivilege) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return children;
}
