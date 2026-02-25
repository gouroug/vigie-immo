import RiskBadge from './RiskBadge';
import DataQualityWarning from './DataQualityWarning';

export default function AirQualityCard({ airQuality }) {
  const pollutants = airQuality.pollutants || {};
  const hasPollutants = Object.keys(pollutants).length > 0;

  return (
    <div className="card">
      <h2>💨 Qualité de l'air</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Niveau de risque</div>
          <div className="info-value">
            <RiskBadge level={airQuality.risk_level} />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Indice de qualité de l'air (IQA)</div>
          <div className="info-value">
            {airQuality.aqi != null ? airQuality.aqi : 'N/A'}{' '}
            — {airQuality.aqi_category || 'Non déterminé'}
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Station la plus proche</div>
          <div className="info-value">
            {airQuality.nearest_station || 'Non disponible'}
            {airQuality.station_distance_km != null &&
              ` (${airQuality.station_distance_km} km)`}
          </div>
        </div>
        {hasPollutants && (
          <div className="info-item">
            <div className="info-label">Polluants</div>
            <div className="info-value">
              {Object.entries(pollutants).map(([key, val]) => (
                <span key={key} style={{ marginRight: 12 }}>
                  {key}: {val}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
      <DataQualityWarning
        source={airQuality.source}
        dataQuality={airQuality.data_quality}
      />
    </div>
  );
}
