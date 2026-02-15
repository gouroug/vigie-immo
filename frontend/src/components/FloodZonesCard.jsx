import RiskBadge from './RiskBadge';
import DataQualityWarning from './DataQualityWarning';

export default function FloodZonesCard({ flood }) {
  const wd = flood.water_distance || {};

  return (
    <div className="card">
      <h2>💧 Zones inondables</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Niveau de risque</div>
          <div className="info-value">
            <RiskBadge level={flood.risk_level} />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Zone de récurrence</div>
          <div className="info-value">
            {flood.zone_type || 'Non disponible'}
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Distance cours d'eau</div>
          <div className="info-value">
            {wd.distance_meters || 'N/A'} mètres de{' '}
            {wd.water_name || "cours d'eau"}
          </div>
        </div>
      </div>
      <DataQualityWarning
        source={flood.source}
        dataQuality={flood.data_quality}
      />
    </div>
  );
}
