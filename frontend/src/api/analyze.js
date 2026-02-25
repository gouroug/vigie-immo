const API_URL = import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:5001`;

/**
 * analyzeAddress — sends POST /api/analyze with JWT auth.
 * getToken / refreshToken / onAuthFailure are injected by the caller (App.jsx)
 * to keep this module decoupled from React context.
 */
export async function analyzeAddress(address, { getToken, refreshToken, onAuthFailure }) {
  async function doFetch(token) {
    return fetch(`${API_URL}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ address }),
    });
  }

  let token = getToken();
  let response = await doFetch(token);

  if (response.status === 401) {
    // Try to refresh the access token once
    try {
      token = await refreshToken();
      response = await doFetch(token);
    } catch (_) {
      onAuthFailure();
      throw new Error('Session expirée. Veuillez vous reconnecter.');
    }
    if (response.status === 401) {
      onAuthFailure();
      throw new Error('Session expirée. Veuillez vous reconnecter.');
    }
  }

  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }

  const data = await response.json();
  if (!data.success) {
    throw new Error(data.message || "Erreur lors de l'analyse de l'adresse");
  }

  return data;
}
