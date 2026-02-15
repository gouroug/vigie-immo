export function getFloodZoneStyle(feature) {
  const props = feature.properties || {};
  const periode = props.periode_retour;
  const risque = props.niveau_risque;

  if (periode === '20' || risque === 'Élevé') {
    return {
      color: '#ff4444',
      fillColor: '#ff4444',
      weight: 3,
      opacity: 0.7,
      fillOpacity: 0.3,
    };
  }

  if (periode === '100' || risque === 'Moyen') {
    return {
      color: '#ffaa44',
      fillColor: '#ffaa44',
      weight: 2,
      opacity: 0.7,
      fillOpacity: 0.25,
    };
  }

  if (periode === '500' || risque === 'Faible') {
    return {
      color: '#44ff44',
      fillColor: '#44ff44',
      weight: 1,
      opacity: 0.7,
      fillOpacity: 0.2,
      dashArray: '5,5',
    };
  }

  return {
    color: '#888888',
    fillColor: '#888888',
    weight: 1,
    opacity: 0.6,
    fillOpacity: 0.2,
  };
}
