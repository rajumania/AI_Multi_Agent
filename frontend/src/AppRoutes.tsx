import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import {
  canAccessCitizenPortal,
  canAccessDepartmentManagement,
  canAccessDepartmentPortal,
  canAccessCommandCenter,
  homePathFor,
  normalizeDepartment,
} from './auth/roles';
import App from './App';
import { CitizenPortal } from './pages/CitizenPortal';
import { DepartmentPortal } from './pages/DepartmentPortal';
import { LoginPage } from './pages/LoginPage';


// Validates the :department param and enforces same-department access before
// rendering the shared DepartmentPortal. A department user manually typing
// another department's URL is redirected to their own home.
function DepartmentPortalRoute() {
  const { user } = useAuth();
  const { department } = useParams();
  const dept = normalizeDepartment(department);
  if (!dept || !canAccessDepartmentPortal(user, dept)) {
    return <Navigate to={homePathFor(user)} replace />;
  }
  return <DepartmentPortal department={dept} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<Navigate to="/login" replace />} />
      <Route
        path="/command"
        element={
          <ProtectedRoute allow={canAccessCommandCenter}>
            <App />
          </ProtectedRoute>
        }
      />
      <Route
        path="/command/departments"
        element={
          <ProtectedRoute allow={canAccessDepartmentManagement}>
            <App initialTab="department-management" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/portal"
        element={
          <ProtectedRoute allow={canAccessCitizenPortal}>
            <CitizenPortal />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dept/:department"
        element={
          <ProtectedRoute>
            <DepartmentPortalRoute />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
