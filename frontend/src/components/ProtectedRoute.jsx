import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { user, restoreSession } = useAuth();
  const [checking, setChecking] = useState(!user);

  useEffect(() => {
    if (!user) {
      restoreSession().finally(() => setChecking(false));
    }
  }, []);

  if (checking) return null; // Brief loading — can add a spinner here
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
