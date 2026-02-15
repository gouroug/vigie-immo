import { getRiskLabel, getRiskClass } from '../utils/riskLabels';

export default function RiskBadge({ level, suffix }) {
  const label = getRiskLabel(level);
  const cls = getRiskClass(level);

  return (
    <span className={`risk-badge ${cls}`}>
      {label}
      {suffix ? ` ${suffix}` : ''}
    </span>
  );
}
