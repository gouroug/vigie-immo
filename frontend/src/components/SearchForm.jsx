import { useState } from 'react';

export default function SearchForm({ onSubmit, loading }) {
  const [address, setAddress] = useState(
    '2, Rue de la Commune Ouest, Montréal, Québec'
  );

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = address.trim();
    if (trimmed) onSubmit(trimmed);
  }

  return (
    <div className="search-section">
      <form className="search-form" onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="address">
            Adresse complète (Province de Québec)
          </label>
          <input
            type="text"
            id="address"
            placeholder="Ex: 2, Rue de la Commune Ouest, Montréal, Québec"
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? '⏳ Analyse en cours...' : '🔍 Générer le rapport'}
        </button>
      </form>
    </div>
  );
}
