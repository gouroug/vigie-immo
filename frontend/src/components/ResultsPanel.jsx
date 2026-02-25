import LocationCard from './LocationCard';
import FloodZonesCard from './FloodZonesCard';
import ContaminationCard from './ContaminationCard';
import ServicesCard from './ServicesCard';
import HydrantsCard from './HydrantsCard';
import SeismicCard from './SeismicCard';
import AirQualityCard from './AirQualityCard';
import DisasterHistoryCard from './DisasterHistoryCard';
import PropertyCard from './PropertyCard';
import CrimeCard from './CrimeCard';
import RiskSummaryCard from './RiskSummaryCard';

export default function ResultsPanel({ data }) {
  const flood = data.flood_zones || {};
  const contamination = data.contamination || {};
  const services = data.services || {};
  const hydrants = data.hydrants || {};
  const seismic = data.seismic || {};
  const airQuality = data.air_quality || {};
  const disasterHistory = data.disaster_history || {};
  const property = data.property_assessment || {};
  const crime = data.crime || {};
  const assessment = data.risk_assessment || {};

  return (
    <div className="results">
      <LocationCard address={data.address} flood={flood} />
      <FloodZonesCard flood={flood} />
      <ContaminationCard contamination={contamination} />
      <ServicesCard services={services} />
      <HydrantsCard hydrants={hydrants} />
      <SeismicCard seismic={seismic} />
      <AirQualityCard airQuality={airQuality} />
      <DisasterHistoryCard disasterHistory={disasterHistory} />
      <PropertyCard property={property} />
      <CrimeCard crime={crime} />
      <RiskSummaryCard assessment={assessment} />
    </div>
  );
}
