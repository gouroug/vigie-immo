import { useState, useEffect } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Circle,
  Popup,
  GeoJSON,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getFloodZoneStyle } from '../utils/floodZoneStyle';

// Fix default marker icon (Leaflet + bundler issue)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

function Legend({ hasZones }) {
  const map = useMap();

  useEffect(() => {
    const legend = L.control({ position: 'bottomright' });

    legend.onAdd = function () {
      const div = L.DomUtil.create('div', 'info legend');
      div.style.backgroundColor = 'white';
      div.style.padding = '10px';
      div.style.borderRadius = '5px';
      div.style.boxShadow = '0 0 10px rgba(0,0,0,0.2)';
      div.style.fontSize = '12px';

      let html = '<strong>Zones inondables</strong><br>';

      if (hasZones) {
        const zones = [
          { color: '#ff4444', label: 'Zone 20 ans - Risque élevé' },
          { color: '#ffaa44', label: 'Zone 100 ans - Risque moyen' },
          { color: '#44ff44', label: 'Zone 500 ans - Risque faible' },
        ];
        zones.forEach((z) => {
          html += `<div style="margin:5px 0;display:flex;align-items:center;">
            <div style="width:20px;height:10px;background-color:${z.color};margin-right:8px;border:1px solid #666;opacity:0.7;"></div>
            <span>${z.label}</span></div>`;
        });
        html +=
          '<div style="font-size:10px;margin-top:5px;color:#666;">📍 Adresse analysée<br>○ Rayon d\'analyse (500m)<br><em>Cliquez sur les zones pour plus d\'infos</em></div>';
      } else {
        html +=
          '<div style="margin:5px 0;color:#666;">📍 Adresse analysée<br>○ Rayon d\'analyse (500m)<br><br><em>Cette adresse n\'est pas dans une zone inondable répertoriée</em></div>';
      }

      div.innerHTML = html;
      return div;
    };

    legend.addTo(map);
    return () => legend.remove();
  }, [map, hasZones]);

  return null;
}

function FloodZonePopup({ feature }) {
  const props = feature.properties || {};
  return (
    <div className="map-popup">
      <strong>Zone inondable</strong>
      {props.nom_zone && <>Nom: {props.nom_zone}<br /></>}
      {props.type_zone && <>Type: {props.type_zone}<br /></>}
      {props.periode_retour && <>Période: {props.periode_retour} ans<br /></>}
      {props.niveau_risque && <>Risque: {props.niveau_risque}<br /></>}
      {props.source && <>Source: {props.source}<br /></>}
    </div>
  );
}

export default function RiskMap({ lat, lng, formattedAddress, geojson }) {
  const [zonesVisible, setZonesVisible] = useState(true);

  const features = geojson?.features || [];
  const hasZones = features.length > 0;

  function onEachFeature(feature, layer) {
    if (feature.properties) {
      const props = feature.properties;
      let html = '<div class="map-popup"><strong>Zone inondable</strong><br>';
      if (props.nom_zone) html += `Nom: ${props.nom_zone}<br>`;
      if (props.type_zone) html += `Type: ${props.type_zone}<br>`;
      if (props.periode_retour) html += `Période: ${props.periode_retour} ans<br>`;
      if (props.niveau_risque) html += `Risque: ${props.niveau_risque}<br>`;
      if (props.source) html += `Source: ${props.source}<br>`;
      html += '</div>';
      layer.bindPopup(html);
    }
  }

  return (
    <div className="risk-map" style={{ position: 'relative' }}>
      <div className="map-controls">
        <button
          type="button"
          className={`map-control-btn ${zonesVisible && hasZones ? 'active' : ''}`}
          disabled={!hasZones}
          onClick={() => setZonesVisible((v) => !v)}
        >
          {hasZones
            ? zonesVisible
              ? '👁️ Masquer zones'
              : '👁️ Afficher zones'
            : '👁️ Aucune zone'}
        </button>
      </div>

      <MapContainer
        center={[lat, lng]}
        zoom={15}
        style={{ height: '100%', width: '100%', borderRadius: '8px' }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        <Marker position={[lat, lng]}>
          <Popup>
            <div className="map-popup">
              <b>{formattedAddress}</b>
              <br />
              Analyse des risques
            </div>
          </Popup>
        </Marker>

        <Circle
          center={[lat, lng]}
          radius={500}
          pathOptions={{
            color: '#667eea',
            fillColor: '#667eea',
            fillOpacity: 0.1,
            weight: 2,
          }}
        />

        {hasZones && zonesVisible && (
          <GeoJSON
            key={`${lat}-${lng}-zones`}
            data={geojson}
            style={getFloodZoneStyle}
            onEachFeature={onEachFeature}
          />
        )}

        <Legend hasZones={hasZones} />
      </MapContainer>
    </div>
  );
}
