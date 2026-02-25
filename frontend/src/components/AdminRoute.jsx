import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AdminRoute({ children }) {
  const { user, restoreSession } = useAuth();
  const [checking, setChecking] = useState(!user);

  useEffect(() => {
    if (!user) {
      restoreSession().finally(() => setChecking(false));
    }
  }, []);

  if (checking) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_admin) return <Navigate to="/" replace />;
  return children;
}
