// ---------------------------------------------------------------------------
// AITAM Disaster Response AI — role & department helpers (Increment 2)
//
// PURE, DOM-FREE module. It mirrors the backend's role/department constants
// (backend/services/auth_service.py + backend/services/departments.py) so the
// frontend can decide *which portal to render* and *which routes a principal may
// enter*. It is deliberately free of React and browser APIs so it can be unit
// tested with plain vitest (the project has no jsdom / testing-library).
//
// SECURITY NOTE: none of this is a substitute for backend enforcement. The
// backend already scopes every incident by the verified token (Increment 2).
// These helpers only decide client-side navigation/rendering so a user cannot
// *see* another portal's shell — the data itself is protected server-side.
// ---------------------------------------------------------------------------

// Roles — must match backend auth_service.py exactly.
export const ROLE_ADMIN = 'admin';
export const ROLE_OPERATOR = 'operator';
export const ROLE_USER = 'user';
export const ROLE_DEPARTMENT = 'department';
export const ROLE_DEPARTMENT_HEAD = 'department_head';

export const PRIVILEGED_ROLES: readonly string[] = [ROLE_ADMIN, ROLE_OPERATOR];
export const DEPARTMENT_ROLES: readonly string[] = [ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD];

// Departments — must match backend departments.py exactly.
export const DEPARTMENTS = [
  'MEDICAL',
  'SEARCH_AND_RESCUE',
  'FIRE',
  'SECURITY',
  'TRANSPORT',
  'COMMUNICATION',
  'FACILITIES',
  'SHELTER',
] as const;

export type DepartmentCode = (typeof DEPARTMENTS)[number];

export const DEPARTMENT_LABELS: Record<DepartmentCode, string> = {
  MEDICAL: 'Medical & Health',
  SEARCH_AND_RESCUE: 'Search & Rescue',
  FIRE: 'Fire & Safety',
  SECURITY: 'Security / Public Safety',
  TRANSPORT: 'Transport & Logistics',
  COMMUNICATION: 'Communications',
  FACILITIES: 'Facilities & Maintenance',
  SHELTER: 'Shelter & Relief',
};

// The authenticated principal as the frontend sees it. Fields are optional
// because the various backend login/`/me` responses expose slightly different
// shapes (operator has username, citizen has phone, department has department).
export interface AuthUser {
  id?: string | number;
  subject_type?: string;
  role?: string;
  username?: string;
  email?: string | null;
  phone?: string | null;
  full_name?: string | null;
  name?: string | null; // legacy operator-console field
  department?: string | null;
  department_label?: string | null;
}

/** Canonicalize any department-ish value to an UPPER code, or null if unknown. */
export function normalizeDepartment(value: unknown): DepartmentCode | null {
  if (typeof value !== 'string') return null;
  const upper = value.trim().toUpperCase();
  return (DEPARTMENTS as readonly string[]).includes(upper) ? (upper as DepartmentCode) : null;
}

/** Human-friendly label for a department code (falls back to the raw value). */
export function departmentLabel(value: unknown): string {
  const code = normalizeDepartment(value);
  return code ? DEPARTMENT_LABELS[code] : typeof value === 'string' ? value : '';
}

export function isPrivileged(user: AuthUser | null | undefined): boolean {
  return !!user && typeof user.role === 'string' && PRIVILEGED_ROLES.includes(user.role);
}

export function isDepartmentRole(user: AuthUser | null | undefined): boolean {
  return !!user && typeof user.role === 'string' && DEPARTMENT_ROLES.includes(user.role);
}

export function isCitizen(user: AuthUser | null | undefined): boolean {
  return !!user && (user.role === ROLE_USER || user.role === 'student');
}

/** A short, safe role label for the identity indicator. */
export function roleDisplayName(user: AuthUser | null | undefined): string {
  if (!user || !user.role) return 'Guest';
  switch (user.role) {
    case ROLE_ADMIN:
      return 'Administrator';
    case ROLE_OPERATOR:
      return 'Safety Operations';
    case ROLE_USER:
    case 'student':
      return 'Community';
    case ROLE_DEPARTMENT:
    case ROLE_DEPARTMENT_HEAD: {
      const label = departmentLabel(user.department);
      const suffix = user.role === ROLE_DEPARTMENT_HEAD ? ' Lead' : ' Staff';
      return label ? `${label}${suffix}` : 'Department Staff';
    }
    default:
      return user.role;
  }
}

/** Best display name for the identity indicator. */
export function displayName(user: AuthUser | null | undefined): string {
  if (!user) return 'Guest';
  return (
    (user.full_name && user.full_name.trim()) ||
    (user.name && user.name.trim()) ||
    (user.username && user.username.trim()) ||
    (user.email && String(user.email).trim()) ||
    'Signed-in user'
  );
}

/**
 * The home route for a principal after login. This is the single mapping of
 * ROLE -> PORTAL used across the app:
 *   admin/operator      -> /command  (existing command-center dashboard)
 *   department(_head)   -> /dept/<DEPT>
 *   user (citizen)      -> /portal
 *   unknown / no user   -> /login
 */
export function homePathFor(user: AuthUser | null | undefined): string {
  if (!user) return '/login';
  if (isPrivileged(user)) return '/command';
  if (isDepartmentRole(user)) {
    const dept = normalizeDepartment(user.department);
    return dept ? `/dept/${dept}` : '/login';
  }
  if (isCitizen(user)) return '/portal';
  return '/login';
}

/**
 * Whether a principal may open a specific department portal URL. This is the
 * guard that stops a Security user from manually entering /dept/MEDICAL.
 *   - privileged operator/admin: may view any department portal (backend still
 *     returns all data to them; this is not a data leak).
 *   - department staff: ONLY their own department.
 *   - everyone else (citizen/anonymous): denied.
 */
export function canAccessDepartmentPortal(
  user: AuthUser | null | undefined,
  department: string,
): boolean {
  const target = normalizeDepartment(department);
  if (!target) return false;
  if (isPrivileged(user)) return true;
  if (isDepartmentRole(user)) return normalizeDepartment(user?.department) === target;
  return false;
}

/** Whether a principal may open the citizen portal. */
export function canAccessCitizenPortal(user: AuthUser | null | undefined): boolean {
  return isCitizen(user);
}

/** Whether a principal may open the operator command center. */
export function canAccessCommandCenter(user: AuthUser | null | undefined): boolean {
  return isPrivileged(user);
}

/** Whether a principal may open the privileged department-account manager. */
export function canAccessDepartmentManagement(user: AuthUser | null | undefined): boolean {
  return isPrivileged(user);
}
