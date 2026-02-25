import { createContext, useContext, useState, useCallback, useRef } from 'react';

const API_URL = import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:5001`;

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Access token kept in memory (not localStorage) for security
  const accessTokenRef = useRef(null);

  function getAccessToken() {
    return accessTokenRef.current;
  }

  const login = useCallback(async (email, password) => {
    const res = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Identifiants incorrects');
    }
    accessTokenRef.current = data.access_token;
    localStorage.setItem('refresh_token', data.refresh_token);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    try {
      await fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch (_) {}
    accessTokenRef.current = null;
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  const refreshAccessToken = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) throw new Error('Pas de refresh token');

    const res = await fetch(`${API_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error('Session expirée');
    }
    accessTokenRef.current = data.access_token;
    return data.access_token;
  }, []);

  /**
   * Restore session on page load: try to exchange the stored refresh token
   * for a new access token, then fetch /api/auth/me.
   */
  const restoreSession = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;
    try {
      const token = await refreshAccessToken();
      const res = await fetch(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setUser(data.user);
        return true;
      }
    } catch (_) {}
    localStorage.removeItem('refresh_token');
    accessTokenRef.current = null;
    return false;
  }, [refreshAccessToken]);

  return (
    <AuthContext.Provider value={{ user, getAccessToken, login, logout, refreshAccessToken, restoreSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export { API_URL };
