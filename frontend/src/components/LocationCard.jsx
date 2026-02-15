import RiskMap from './RiskMap';

export default function LocationCard({ address, flood }) {
  const municipality =
    address.municipality || address.city || address.region || 'Non spécifié';

  const geojson = flood.flood_zones_geojson || null;

  return (
    <div className="card full-width">
      <h2>📍 Localisation et carte</h2>
      <div className="info-item">
        <div className="info-label">Adresse analysée</div>
        <div className="info-value">{address.formatted}</div>
      </div>
      <div className="info-item" style={{ marginTop: 15 }}>
        <div className="info-label">Municipalité/Région</div>
        <div className="info-value">{municipality}</div>
      </div>
      <RiskMap
        key={`${address.latitude}-${address.longitude}`}
        lat={address.latitude}
        lng={address.longitude}
        formattedAddress={address.formatted}
        geojson={geojson}
      />
    </div>
  );
}
