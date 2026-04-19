import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Results from './pages/Results';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import AdminStudents from './pages/AdminStudents';
import AdminDashboard from './pages/AdminDashboard';
import AdminRecords from './pages/AdminRecords';
import SuperadminDashboard from './pages/SuperadminDashboard';
import Profile from './pages/Profile';

function RoleBasedRedirect() {
  const role = localStorage.getItem('privilege_level');
  if (role === '1') return <Navigate to="/superadmin" replace />;
  if (role === '2') return <Navigate to="/admin-dashboard" replace />;
  return <Navigate to="/dashboard" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<Login />} />

        {/* All logged-in users */}
        <Route path="/" element={
          <ProtectedRoute minPrivilege={3}>
            <Layout />
          </ProtectedRoute>
        }>
          <Route index element={<RoleBasedRedirect />} />

          {/* Superadmin only */}
          <Route path="superadmin" element={
            <ProtectedRoute minPrivilege={[1]}>
              <SuperadminDashboard />
            </ProtectedRoute>
          } />

          {/* Admin + Teacher */}
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="results" element={<Results />} />

          {/* Admin and above */}
          <Route path="admin-students" element={
            <ProtectedRoute minPrivilege={2}>
              <AdminStudents />
            </ProtectedRoute>
          } />
          
          <Route path="admin-dashboard" element={
            <ProtectedRoute minPrivilege={2}>
              <AdminDashboard />
            </ProtectedRoute>
          } />

          <Route path="admin-records" element={
            <ProtectedRoute minPrivilege={2}>
              <AdminRecords />
            </ProtectedRoute>
          } />

          {/* Profile — all roles */}
          <Route path="profile" element={<Profile />} />
        </Route>

        {/* Unauthorized fallback */}
        <Route path="/unauthorized" element={
          <div className="flex items-center justify-center min-h-screen">
            <p className="text-slate-600 text-lg">You are not authorized to view this page.</p>
          </div>
        } />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
