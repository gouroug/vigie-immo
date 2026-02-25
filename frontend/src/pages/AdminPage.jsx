import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../context/AuthContext';

export default function AdminPage() {
  const { getAccessToken, refreshAccessToken, logout } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [form, setForm] = useState({ email: '', name: '', password: '', is_admin: false });
  const [formMsg, setFormMsg] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  async function authFetch(url, options = {}) {
    let token = getAccessToken();
    let res = await fetch(url, {
      ...options,
      headers: { ...options.headers, Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      try {
        token = await refreshAccessToken();
        res = await fetch(url, {
          ...options,
          headers: { ...options.headers, Authorization: `Bearer ${token}` },
        });
      } catch (_) {
        await logout();
        navigate('/login');
        throw new Error('Session expirée');
      }
    }
    return res;
  }

  async function fetchUsers() {
    setLoading(true);
    setListError('');
    try {
      const res = await authFetch(`${API_URL}/api/admin/users`);
      const data = await res.json();
      if (data.success) setUsers(data.users);
      else setListError(data.error || 'Erreur lors du chargement des utilisateurs');
    } catch (err) {
      setListError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    setFormMsg('');
    try {
      const res = await authFetch(`${API_URL}/api/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setFormMsg(`✅ Compte créé : ${data.user.email}`);
        setForm({ email: '', name: '', password: '', is_admin: false });
        fetchUsers();
      } else {
        setFormMsg(`❌ ${data.error}`);
      }
    } catch (err) {
      setFormMsg(`❌ ${err.message}`);
    }
  }

  async function toggleStatus(user) {
    const newStatus = user.status === 'active' ? 'suspended' : 'active';
    try {
      const res = await authFetch(`${API_URL}/api/admin/users/${user.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const data = await res.json();
        setFormMsg(`❌ ${data.error || 'Erreur lors du changement de statut'}`);
        return;
      }
      fetchUsers();
    } catch (err) {
      setFormMsg(`❌ ${err.message}`);
    }
  }

  async function toggleAdmin(user) {
    try {
      const res = await authFetch(`${API_URL}/api/admin/users/${user.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_admin: !user.is_admin }),
      });
      if (!res.ok) {
        const data = await res.json();
        setFormMsg(`❌ ${data.error || 'Erreur lors du changement de rôle'}`);
        return;
      }
      fetchUsers();
    } catch (err) {
      setFormMsg(`❌ ${err.message}`);
    }
  }

  async function deleteUser(user) {
    if (!confirm(`Supprimer ${user.email} ?`)) return;
    try {
      const res = await authFetch(`${API_URL}/api/admin/users/${user.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        setFormMsg(`❌ ${data.error || 'Erreur lors de la suppression'}`);
        return;
      }
      fetchUsers();
    } catch (err) {
      setFormMsg(`❌ ${err.message}`);
    }
  }

  return (
    <div className="admin-page">
      <div className="dashboard-header">
        <button className="back-btn" onClick={() => navigate('/')}>← Retour</button>
        <h1>⚙️ Administration des comptes</h1>
      </div>

      {/* Création de compte */}
      <section className="dashboard-card">
        <h2>➕ Créer un compte</h2>
        {formMsg && <div className="form-msg">{formMsg}</div>}
        <form onSubmit={handleCreate} className="admin-form">
          <input
            type="email"
            placeholder="Courriel"
            value={form.email}
            onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
            required
          />
          <input
            type="text"
            placeholder="Nom complet"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            required
          />
          <input
            type="password"
            placeholder="Mot de passe (min. 8 car.)"
            value={form.password}
            onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
            required
            minLength={8}
          />
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={form.is_admin}
              onChange={e => setForm(f => ({ ...f, is_admin: e.target.checked }))}
            />
            Administrateur
          </label>
          <button type="submit">Créer le compte</button>
        </form>
      </section>

      {/* Liste des utilisateurs */}
      <section className="dashboard-card">
        <h2>👥 Utilisateurs ({users.length})</h2>
        {loading ? (
          <p>Chargement...</p>
        ) : listError ? (
          <p className="error-msg">⚠️ {listError}</p>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Courriel</th>
                <th>Statut</th>
                <th>Admin</th>
                <th>Créé le</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className={`status-badge status-${u.status}`}>
                      {u.status === 'active' ? '✅ Actif' : '🚫 Suspendu'}
                    </span>
                  </td>
                  <td>{u.is_admin ? '⚙️ Oui' : '—'}</td>
                  <td>{new Date(u.created_at).toLocaleDateString('fr-CA')}</td>
                  <td className="action-cell">
                    <button
                      onClick={() => toggleStatus(u)}
                      title={u.status === 'active' ? 'Suspendre' : 'Activer'}
                    >
                      {u.status === 'active' ? '🚫' : '✅'}
                    </button>
                    <button onClick={() => toggleAdmin(u)} title="Modifier rôle admin">
                      ⚙️
                    </button>
                    <button
                      onClick={() => deleteUser(u)}
                      className="delete-btn"
                      title="Supprimer"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
