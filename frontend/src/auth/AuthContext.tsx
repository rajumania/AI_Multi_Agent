import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from 'react';
import { api, getAuthToken, setUnauthorizedHandler } from '../services/api';
import { AuthUser } from './roles';

// ---------------------------------------------------------------------------
// AuthContext — the single owner of frontend session state (Increment 2).
//
// Responsibilities:
//   * Bootstrap: on load, if a token exists in localStorage, VALIDATE it against
//     the backend (`GET /api/v1/auth/me`). The server-verified principal — not
//     the cached cf_user blob — is the source of truth for role/department.
//   * Login helpers for the existing community and department auth flows
//     department) + citizen self-registration. Each authenticates against the
//     EXISTING backend APIs — there is no fake frontend-only auth.
//   * Logout: clears token + cached user.
//   * Registers the api 401 handler so an expired/invalid token anywhere in the
//     app tears the session down (ProtectedRoute then redirects to /login).
// ---------------------------------------------------------------------------

const AUTH_USER_KEY = 'cf_user';

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  /** True while the initial token validation is in flight. */
  loading: boolean;
  /** Set when a previously-valid session was rejected (expired/invalid token). */
  sessionExpired: boolean;
  loginAdmin: (username: string, password: string) => Promise<AuthUser>;
  loginCitizen: (email: string, phone: string) => Promise<AuthUser>;
  registerCitizen: (email: string, phone: string, fullName?: string) => Promise<AuthUser>;
  loginDepartment: (email: string, password: string, department: string) => Promise<AuthUser>;
  logout: () => void;
  /** Re-validate the current token against the backend. */
  refresh: () => Promise<void>;
  clearSessionExpired: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredUser(): AuthUser | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

function persistUser(user: AuthUser | null): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (user) localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(AUTH_USER_KEY);
  } catch {
    /* storage unavailable — session still works for the current tab */
  }
}

// Helper to log to the diagnostic box
const logDiag = (msg: string) => {
  console.log(`[DIAG] ${msg}`);
  if (typeof document !== 'undefined') {
    const diag = document.getElementById('vite-diag-status');
    if (diag) {
      const logLine = document.createElement('div');
      logLine.style.borderTop = '1px dashed rgba(255,255,255,0.3)';
      logLine.style.marginTop = '3px';
      logLine.style.paddingTop = '3px';
      logLine.innerText = msg;
      diag.appendChild(logLine);
    }
  }
};

export function AuthProvider({ children }: { children: ReactNode }) {
  logDiag('AuthProvider rendering');
  // Optimistic paint from cache; confirmed/replaced by /me during bootstrap.
  const [user, setUser] = useState<AuthUser | null>(() => (getAuthToken() ? readStoredUser() : null));
  const [token, setToken] = useState<string | null>(() => getAuthToken());
  const [loading, setLoading] = useState<boolean>(() => !!getAuthToken());
  const [sessionExpired, setSessionExpired] = useState(false);
  logDiag(`AuthProvider: initial state: user=${JSON.stringify(user)}, loading=${loading}`);

  const applyUser = useCallback((next: AuthUser) => {
    setUser(next);
    setToken(getAuthToken());
    persistUser(next);
    setSessionExpired(false);
  }, []);

  const clearSession = useCallback(() => {
    api.logout(); // clears cf_token + cf_user
    setUser(null);
    setToken(null);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setSessionExpired(false);
  }, [clearSession]);

  // After any successful login, confirm with /me so the stored principal has a
  // consistent shape (subject_type, department_label, canonical role) regardless
  // of which login endpoint was used. Falls back to the login payload's user.
  const establishSession = useCallback(
    async (rawUser: AuthUser | undefined | null): Promise<AuthUser> => {
      let confirmed: AuthUser | null = null;
      try {
        confirmed = (await api.getMe()) as AuthUser;
      } catch {
        confirmed = null;
      }
      const finalUser = confirmed || rawUser || null;
      if (!finalUser) {
        clearSession();
        throw new Error('Login succeeded but no user profile was returned.');
      }
      applyUser(finalUser);
      return finalUser;
    },
    [applyUser, clearSession],
  );

  const loginCitizen = useCallback(
    async (email: string, phone: string) => {
      const data = await api.userLogin(email, phone);
      return establishSession(data?.user);
    },
    [establishSession],
  );

  const loginAdmin = useCallback(
    async (username: string, password: string) => {
      const data = await api.login(username, password);
      return establishSession(data?.user);
    },
    [establishSession],
  );

  const registerCitizen = useCallback(
    async (email: string, phone: string, fullName?: string) => {
      const data = await api.userRegister({ email, phone, full_name: fullName });
      return establishSession(data?.user);
    },
    [establishSession],
  );

  const loginDepartment = useCallback(
    async (email: string, password: string, department: string) => {
      const data = await api.departmentLogin(email, password, department);
      return establishSession(data?.user);
    },
    [establishSession],
  );

  const refresh = useCallback(async () => {
    if (!getAuthToken()) {
      clearSession();
      return;
    }
    try {
      const me = (await api.getMe()) as AuthUser;
      applyUser(me);
    } catch {
      clearSession();
    }
  }, [applyUser, clearSession]);

  // Register the global 401 handler: any tokened request that comes back 401
  // means the session is stale. Tear it down and flag expiry; ProtectedRoute
  // sees user === null and redirects to /login. Idempotent by construction.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (getAuthToken() || user) {
        clearSession();
        setSessionExpired(true);
      }
    });
    return () => setUnauthorizedHandler(null);
  }, [clearSession, user]);

  // Bootstrap: validate an existing token exactly once on mount.
  useEffect(() => {
    let cancelled = false;
    const existing = getAuthToken();
    if (!existing) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const me = (await api.getMe()) as AuthUser;
        if (!cancelled) applyUser(me);
      } catch {
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      sessionExpired,
      loginAdmin,
      loginCitizen,
      registerCitizen,
      loginDepartment,
      logout,
      refresh,
      clearSessionExpired: () => setSessionExpired(false),
    }),
    [
      user,
      token,
      loading,
      sessionExpired,
      loginAdmin,
      loginCitizen,
      registerCitizen,
      loginDepartment,
      logout,
      refresh,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an <AuthProvider>');
  return ctx;
}
