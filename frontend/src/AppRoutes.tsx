import { ReactElement } from 'react';
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import { ProtectedRoute, FullScreenMessage } from './auth/ProtectedRoute';
import {
  canAccessCitizenPortal,
  canAccessCommandCenter,
  canAccessDepartmentManagement,
  canAccessDepartmentPortal,
  homePathFor,
  normalizeDepartment,
} from './auth/roles';
import App from './App';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { CitizenPortal } from './pages/CitizenPortal';
import { DepartmentPortal } from './pages/DepartmentPortal';

function RoleHome() {
  const { user, loading } = useAuth();
  if (loading) return <FullScreenMessage title="Loading…" />;
  return <Navigate to={homePathFor(user)} replace />;
}

// Login/Signup are public, but an already-authenticated user should never see
// them — send them to their portal instead.
function PublicOnly({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <FullScreenMessage title="Loading…" />;
  }
  if (user) {
    const target = homePathFor(user);
    return <Navigate to={target} replace />;
  }
  return children;
}


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
      <Route
        path="/login"
        element={
          <PublicOnly>
            <LoginPage />
          </PublicOnly>
        }
      />
      <Route
        path="/signup"
        element={
          <PublicOnly>
            <SignupPage />
          </PublicOnly>
        }
      />
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
      <Route path="/" element={<RoleHome />} />
      <Route path="*" element={<RoleHome />} />
    </Routes>
  );
}
