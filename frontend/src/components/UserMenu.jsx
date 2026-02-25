import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  if (!user) return null;

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div className="user-menu" ref={menuRef}>
      <button className="user-menu-btn" onClick={() => setOpen(o => !o)}>
        👤 {user.name} {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="user-menu-dropdown">
          <button onClick={() => { navigate('/dashboard'); setOpen(false); }}>
            📊 Tableau de bord
          </button>
          {user.is_admin && (
            <button onClick={() => { navigate('/admin'); setOpen(false); }}>
              ⚙️ Administration
            </button>
          )}
          <hr />
          <button onClick={handleLogout} className="user-menu-logout">
            🚪 Déconnexion
          </button>
        </div>
      )}
    </div>
  );
}
