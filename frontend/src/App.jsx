import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Results from './pages/Results';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import AdminStudents from './pages/AdminStudents';
import SuperadminDashboard from './pages/SuperadminDashboard';

function RoleBasedRedirect() {
  const role = localStorage.getItem('privilege_level');
  if (role === '1') return <Navigate to="/superadmin" replace />;
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
