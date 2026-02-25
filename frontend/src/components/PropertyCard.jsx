import DataQualityWarning from './DataQualityWarning';

function formatCurrency(value) {
  if (value == null || value === 0) return 'Non disponible';
  return new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(value);
}

export default function PropertyCard({ property }) {
  const hasData = property.total_value != null;

  return (
    <div className="card">
      <h2>🏠 Évaluation foncière</h2>
      {hasData ? (
        <div className="info-grid">
          <div className="info-item">
            <div className="info-label">Valeur totale</div>
            <div className="info-value">{formatCurrency(property.total_value)}</div>
          </div>
          <div className="info-item">
            <div className="info-label">Valeur du terrain</div>
            <div className="info-value">{formatCurrency(property.land_value)}</div>
          </div>
          <div className="info-item">
            <div className="info-label">Valeur du bâtiment</div>
            <div className="info-value">{formatCurrency(property.building_value)}</div>
          </div>
          {property.building_year > 0 && (
            <div className="info-item">
              <div className="info-label">Année de construction</div>
              <div className="info-value">{property.building_year}</div>
            </div>
          )}
          {property.lot_area_sqm > 0 && (
            <div className="info-item">
              <div className="info-label">Superficie du terrain</div>
              <div className="info-value">{property.lot_area_sqm} m²</div>
            </div>
          )}
          {property.building_area_sqm > 0 && (
            <div className="info-item">
              <div className="info-label">Superficie du bâtiment</div>
              <div className="info-value">{property.building_area_sqm} m²</div>
            </div>
          )}
          {property.property_type && (
            <div className="info-item">
              <div className="info-label">Type de propriété</div>
              <div className="info-value">{property.property_type}</div>
            </div>
          )}
        </div>
      ) : (
        <p style={{ color: '#718096', fontStyle: 'italic' }}>
          Données d'évaluation foncière non disponibles pour cette adresse
        </p>
      )}
      <DataQualityWarning
        source={property.source}
        dataQuality={property.data_quality}
      />
    </div>
  );
}
