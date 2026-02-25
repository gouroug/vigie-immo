import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../context/AuthContext';

export default function DashboardPage() {
  const { user, getAccessToken, refreshAccessToken, logout } = useAuth();
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' });
  const [pwMsg, setPwMsg] = useState('');

  useEffect(() => {
    fetchHistory();
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

  async function fetchHistory() {
    try {
      const res = await authFetch(`${API_URL}/api/history`);
      const data = await res.json();
      if (data.success) setHistory(data.history);
      else setHistoryError(data.error || 'Erreur lors du chargement de l\'historique');
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setLoadingHistory(false);
    }
  }

  async function handlePasswordChange(e) {
    e.preventDefault();
    setPwMsg('');
    if (pwForm.next !== pwForm.confirm) {
      setPwMsg('Les mots de passe ne correspondent pas.');
      return;
    }
    try {
      const res = await authFetch(`${API_URL}/api/auth/password`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.next }),
      });
      const data = await res.json();
      setPwMsg(data.message || data.error || '');
      if (res.ok) setPwForm({ current: '', next: '', confirm: '' });
    } catch (err) {
      setPwMsg(err.message);
    }
  }

  function riskColor(score) {
    if (score === null || score === undefined) return '#888';
    if (score >= 70) return '#d32f2f';
    if (score >= 40) return '#f57c00';
    return '#388e3c';
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <button className="back-btn" onClick={() => navigate('/')}>← Retour à l'analyse</button>
        <h1>Tableau de bord</h1>
      </div>

      <div className="dashboard-grid">
        {/* Profil */}
        <section className="dashboard-card">
          <h2>👤 Profil</h2>
          <p><strong>Nom :</strong> {user?.name}</p>
          <p><strong>Courriel :</strong> {user?.email}</p>
          <p><strong>Rôle :</strong> {user?.is_admin ? '⚙️ Administrateur' : 'Utilisateur'}</p>
        </section>

        {/* Changement de mot de passe */}
        <section className="dashboard-card">
          <h2>🔑 Changer de mot de passe</h2>
          {pwMsg && <div className="pw-msg">{pwMsg}</div>}
          <form onSubmit={handlePasswordChange}>
            <input
              type="password"
              placeholder="Mot de passe actuel"
              value={pwForm.current}
              onChange={e => setPwForm(f => ({ ...f, current: e.target.value }))}
              required
            />
            <input
              type="password"
              placeholder="Nouveau mot de passe (min. 8 car.)"
              value={pwForm.next}
              onChange={e => setPwForm(f => ({ ...f, next: e.target.value }))}
              required
              minLength={8}
            />
            <input
              type="password"
              placeholder="Confirmer le nouveau mot de passe"
              value={pwForm.confirm}
              onChange={e => setPwForm(f => ({ ...f, confirm: e.target.value }))}
              required
            />
            <button type="submit">Modifier</button>
          </form>
        </section>
      </div>

      {/* Historique */}
      <section className="dashboard-card history-card">
        <h2>📊 Historique des analyses</h2>
        {loadingHistory ? (
          <p>Chargement...</p>
        ) : historyError ? (
          <p className="error-msg">⚠️ {historyError}</p>
        ) : history.length === 0 ? (
          <p>Aucune analyse effectuée pour l'instant.</p>
        ) : (
          <table className="history-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Adresse</th>
                <th>Score de risque</th>
              </tr>
            </thead>
            <tbody>
              {history.map(item => (
                <tr key={item.id}>
                  <td>{new Date(item.created_at).toLocaleString('fr-CA')}</td>
                  <td>{item.address}</td>
                  <td style={{ color: riskColor(item.risk_score), fontWeight: 'bold' }}>
                    {item.risk_score !== null ? item.risk_score : '—'}
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
