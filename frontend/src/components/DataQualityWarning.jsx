export default function DataQualityWarning({ source, dataQuality }) {
  if (!dataQuality || dataQuality === 'Haute') return null;

  const isUnavailable = dataQuality === 'Indisponible';
  const className = isUnavailable
    ? 'data-quality-warning unavailable'
    : 'data-quality-warning';
  const icon = isUnavailable ? '\u26A0' : '\u2139';
  const msg = isUnavailable
    ? `Données indisponibles — ${source || 'source inconnue'}`
    : `Données estimées (qualité : ${dataQuality}) — Source : ${source || 'non spécifiée'}`;

  return (
    <div className={className}>
      {icon} {msg}
    </div>
  );
}
