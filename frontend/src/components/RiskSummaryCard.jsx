import RiskBadge from './RiskBadge';

export default function RiskSummaryCard({ assessment }) {
  const factors = assessment.factors || [];

  return (
    <div className="card full-width">
      <h2>📊 Résumé des risques</h2>
      <div className="info-grid">
        <div className="info-item">
          <div className="info-label">Score de risque global</div>
          <div className="info-value">
            <RiskBadge
              level={assessment.level}
              suffix={`(${assessment.score || 0}/100)`}
            />
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Facteurs de risque identifiés</div>
          <div className="info-value">
            {Array.isArray(factors) && factors.length > 0 ? (
              <ul style={{ margin: '10px 0 0 20px' }}>
                {factors.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            ) : (
              'Aucun facteur de risque majeur identifié'
            )}
          </div>
        </div>
        <div className="info-item">
          <div className="info-label">Recommandations</div>
          <div className="info-value">
            {assessment.recommendation || 'Aucune recommandation spécifique'}
          </div>
        </div>
      </div>
    </div>
  );
}
