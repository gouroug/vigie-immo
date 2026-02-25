import RiskBadge from './RiskBadge';
import DataQualityWarning from './DataQualityWarning';

export default function HydrantsCard({ hydrants }) {
  const nearest = hydrants.nearest_hydrant;
  const list = hydrants.hydrants || [];

  return (
    <div className="card">
      <h2>🚿 Bornes fontaines</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Niveau de risque</div>
          <div className="info-value">
            <RiskBadge level={hydrants.risk_level} />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Borne la plus proche</div>
          <div className="info-value">
            {nearest ? `${nearest.distance}m` : 'Aucune trouvée'}
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Dans un rayon de 200m</div>
          <div className="info-value">
            {hydrants.hydrants_count_200m ?? 0} borne(s)
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Dans un rayon de 500m</div>
          <div className="info-value">
            {hydrants.hydrants_count_500m ?? 0} borne(s)
          </div>
        </div>
      </div>

      {list.length > 0 && (
        <div className="service-list">
          {list.map((h, i) => (
            <div className="service-item" key={i}>
              <span className="service-icon">🔴</span>
              <span>Borne fontaine #{i + 1}</span>
              <span className="distance">{h.distance}m</span>
            </div>
          ))}
        </div>
      )}

      <DataQualityWarning
        source={hydrants.source}
        dataQuality={hydrants.data_quality}
      />
    </div>
  );
}
