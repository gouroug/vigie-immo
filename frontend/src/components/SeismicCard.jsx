import RiskBadge from './RiskBadge';
import DataQualityWarning from './DataQualityWarning';

export default function SeismicCard({ seismic }) {
  return (
    <div className="card">
      <h2>🌍 Données sismiques</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Niveau de risque</div>
          <div className="info-value">
            <RiskBadge level={seismic.risk_level} />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Zone sismique</div>
          <div className="info-value">
            {seismic.seismic_zone || 'Non déterminée'}
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">PGA (2% en 50 ans)</div>
          <div className="info-value">
            {seismic.pga_2percent_50yr != null
              ? `${seismic.pga_2percent_50yr}g`
              : 'Non disponible'}
          </div>
        </div>
      </div>
      <DataQualityWarning
        source={seismic.source}
        dataQuality={seismic.data_quality}
      />
    </div>
  );
}
