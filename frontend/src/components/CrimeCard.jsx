import RiskBadge from './RiskBadge';
import DataQualityWarning from './DataQualityWarning';

export default function CrimeCard({ crime }) {
  const categories = crime.incidents_by_category || {};
  const hasCategories = Object.keys(categories).length > 0;

  return (
    <div className="card">
      <h2>🔒 Criminalité</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Niveau de risque</div>
          <div className="info-value">
            <RiskBadge level={crime.risk_level} />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Incidents dans 1 km</div>
          <div className="info-value">
            {crime.incidents_1km != null ? crime.incidents_1km : 'Non disponible'}
          </div>
        </div>
        {crime.crime_density && (
          <div className="info-item">
            <div className="info-label">Densité criminelle</div>
            <div className="info-value">{crime.crime_density}</div>
          </div>
        )}
        {crime.pdq && (
          <div className="info-item">
            <div className="info-label">District de police (PDQ)</div>
            <div className="info-value">{crime.pdq}</div>
          </div>
        )}
      </div>

      {hasCategories && (
        <div className="site-list" style={{ marginTop: 10 }}>
          {Object.entries(categories)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([cat, count]) => (
              <div className="service-item" key={cat}>
                <span>{cat}</span>
                <span className="distance">{count}</span>
              </div>
            ))}
        </div>
      )}

      <DataQualityWarning
        source={crime.source}
        dataQuality={crime.data_quality}
      />
    </div>
  );
}
