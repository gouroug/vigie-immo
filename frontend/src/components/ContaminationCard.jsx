import DataQualityWarning from './DataQualityWarning';

export default function ContaminationCard({ contamination }) {
  const sites = contamination.sites || [];

  return (
    <div className="card">
      <h2>⚠️ Terrains contaminés</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Terrain actuel</div>
          <div className="info-value">
            {contamination.is_contaminated
              ? '⚠️ Terrain répertorié comme contaminé'
              : '✅ Non répertorié'}
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Dans un rayon de 500m</div>
          <div className="info-value">
            {contamination.nearby_count || 0} terrain(s) contaminé(s)
          </div>
        </div>
      </div>

      {sites.length > 0 ? (
        <div className="site-list">
          {sites.map((site, i) => (
            <div className="site-item" key={i}>
              <div className="site-name">{site.name || 'Site inconnu'}</div>
              <div className="site-distance">
                {site.distance || 0}m - {site.address || 'Adresse inconnue'}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: '#718096', fontStyle: 'italic', marginTop: 10 }}>
          Aucun site contaminé à proximité
        </p>
      )}

      <DataQualityWarning
        source={contamination.source}
        dataQuality={contamination.data_quality}
      />
    </div>
  );
}
