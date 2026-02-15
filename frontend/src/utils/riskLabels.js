export const riskLabels = {
  low: 'Faible',
  medium: 'Moyen',
  high: 'Élevé',
  unknown: 'Non déterminé',
};

export function getRiskLabel(level) {
  return riskLabels[(level || '').toLowerCase()] || 'Non déterminé';
}

export function getRiskClass(level) {
  const l = (level || '').toLowerCase();
  return riskLabels[l] ? `risk-${l}` : 'risk-unknown';
}
