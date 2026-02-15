import LocationCard from './LocationCard';
import FloodZonesCard from './FloodZonesCard';
import ContaminationCard from './ContaminationCard';
import ServicesCard from './ServicesCard';
import RiskSummaryCard from './RiskSummaryCard';

export default function ResultsPanel({ data }) {
  const flood = data.flood_zones || {};
  const contamination = data.contamination || {};
  const services = data.services || {};
  const assessment = data.risk_assessment || {};

  return (
    <div className="results">
      <LocationCard address={data.address} flood={flood} />
      <FloodZonesCard flood={flood} />
      <ContaminationCard contamination={contamination} />
      <ServicesCard services={services} />
      <RiskSummaryCard assessment={assessment} />
    </div>
  );
}
