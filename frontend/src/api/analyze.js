const API_URL = import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:5001`;

export async function analyzeAddress(address) {
  const response = await fetch(`${API_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ address }),
  });

  if (!response.ok) {
    throw new Error(`Erreur HTTP: ${response.status}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Erreur lors de l'analyse de l'adresse");
  }

  return data;
}
