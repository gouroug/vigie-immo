import DataQualityWarning from './DataQualityWarning';

const SERVICE_TYPES = [
  { key: 'fire_station', icon: '🚒', type: 'Caserne' },
  { key: 'hospital', icon: '🏥', type: 'Hôpital' },
  { key: 'police_station', icon: '👮', type: 'Poste de police' },
];

export default function ServicesCard({ services }) {
  const items = SERVICE_TYPES.filter(
    (s) => services[s.key] && services[s.key].distance !== 'N/A'
  ).map((s) => ({
    ...s,
    name: services[s.key].name || 'Inconnu',
    distance: services[s.key].distance,
  }));

  items.sort((a, b) => a.distance - b.distance);

  return (
    <div className="card full-width">
      <h2>🚒 Services d'urgence à proximité</h2>
      {items.length > 0 ? (
        <div className="service-list">
          {items.map((s) => (
            <div className="service-item" key={s.key}>
              <span className="service-icon">{s.icon}</span>
              <span>
                <strong>{s.type}</strong> - {s.name}
              </span>
              <span className="distance">{s.distance}m</span>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: '#718096', fontStyle: 'italic' }}>
          Aucun service d'urgence trouvé à proximité
        </p>
      )}
      <DataQualityWarning
        source={services.source}
        dataQuality={services.data_quality}
      />
    </div>
  );
}
