import RiskBadge from './RiskBadge';
import DataQualityWarning from './DataQualityWarning';

export default function DisasterHistoryCard({ disasterHistory }) {
  const events = disasterHistory.events || [];

  return (
    <div className="card">
      <h2>📜 Historique de sinistres</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Niveau de risque</div>
          <div className="info-value">
            <RiskBadge level={disasterHistory.risk_level} />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Événements à proximité (25 km)</div>
          <div className="info-value">
            {disasterHistory.nearby_events_count ?? 0} événement(s)
          </div>
        </div>
        {disasterHistory.most_common_type && disasterHistory.most_common_type !== 'Aucun' && (
          <div className="info-item">
            <div className="info-label">Type le plus fréquent</div>
            <div className="info-value">
              {disasterHistory.most_common_type}
            </div>
          </div>
        )}
      </div>

      {events.length > 0 && (
        <div className="site-list">
          {events.slice(0, 5).map((evt, i) => (
            <div className="site-item" key={i}>
              <div className="site-name">
                {evt.type || 'Événement'} — {evt.distance_km} km
              </div>
              <div className="site-distance">
                {evt.date && `${evt.date} — `}
                {evt.description || 'Pas de description'}
              </div>
            </div>
          ))}
        </div>
      )}

      <DataQualityWarning
        source={disasterHistory.source}
        dataQuality={disasterHistory.data_quality}
      />
    </div>
  );
}
