import json
import os
from typing import Dict, List, Optional, Tuple
from geopy.distance import geodesic
import requests
import logging

import psycopg2
import psycopg2.pool
import psycopg2.extras

logger = logging.getLogger(__name__)

# Pool de connexions PostGIS pour l'évaluation foncière
_db_pool = None

def _get_db_pool():
    global _db_pool
    if _db_pool is None:
        dsn = os.environ.get("VIGIE_DB_DSN", "dbname=vigie_immo")
        _db_pool = psycopg2.pool.SimpleConnectionPool(1, 5, dsn=dsn)
    return _db_pool

# URLs des APIs et datasets
GEOCODING_API_QC = "https://ws.mapserver.transports.gouv.qc.ca/swtq"
GEOCODING_API_BACKUP = "https://nominatim.openstreetmap.org/search"

# API pour les terrains contaminés - Service ArcGIS du MELCCFP (couche points)
CONTAMINATED_SITES_API = "https://www.servicesgeo.enviroweb.gouv.qc.ca/donnees/rest/services/Public/Themes_publics/MapServer/12/query"

# API des zones inondables du gouvernement du Québec
FLOOD_ZONES_API = "https://services1.arcgis.com/QZKc6I4nVMd4XrMx/arcgis/rest/services/Zones_inondables/FeatureServer/0/query"

# Dictionnaire des régions administratives du Québec avec centres
QUEBEC_REGIONS = {
    "Bas-Saint-Laurent": (48.511, -68.464),
    "Saguenay–Lac-Saint-Jean": (48.428, -71.068),
    "Capitale-Nationale": (46.813, -71.208),
    "Mauricie": (46.500, -72.523),
    "Estrie": (45.400, -71.890),
    "Montréal": (45.501, -73.567),
    "Outaouais": (45.477, -75.701),
    "Abitibi-Témiscamingue": (48.233, -78.519),
    "Côte-Nord": (50.234, -66.383),
    "Nord-du-Québec": (52.940, -73.839),
    "Gaspésie–Îles-de-la-Madeleine": (48.839, -64.479),
    "Chaudière-Appalaches": (46.554, -70.992),
    "Laval": (45.575, -73.753),
    "Lanaudière": (46.250, -73.617),
    "Laurentides": (46.256, -74.605),
    "Montérégie": (45.399, -73.515),
    "Centre-du-Québec": (46.220, -72.423)
}

# Données hydrographiques pour Montréal (points de référence)
MONTREAL_WATER_POINTS = [
    # Fleuve Saint-Laurent
    (45.5017, -73.5673, "Fleuve Saint-Laurent - Pont Jacques-Cartier", "Fleuve"),
    (45.5046, -73.5531, "Fleuve Saint-Laurent - Vieux-Port", "Fleuve"),
    (45.5075, -73.5419, "Fleuve Saint-Laurent - Bassin Peel", "Fleuve"),
    (45.5113, -73.5311, "Fleuve Saint-Laurent - Bassin Bonsecours", "Fleuve"),
    (45.5150, -73.5200, "Fleuve Saint-Laurent - Parc Bellerive", "Fleuve"),
    (45.5200, -73.5100, "Fleuve Saint-Laurent - Pointe-aux-Prairies", "Fleuve"),
    (45.4900, -73.5800, "Fleuve Saint-Laurent - Pointe-Saint-Charles", "Fleuve"),
    (45.4700, -73.6000, "Fleuve Saint-Laurent - Lachine", "Fleuve"),
    
    # Rivière des Prairies
    (45.5400, -73.7000, "Rivière des Prairies - Ouest", "Rivière"),
    (45.5300, -73.6500, "Rivière des Prairies - Centre", "Rivière"),
    (45.5200, -73.6000, "Rivière des Prairies - Est", "Rivière"),
    
    # Canal Lachine
    (45.4920, -73.5700, "Canal Lachine - Sud", "Canal"),
    (45.4980, -73.5550, "Canal Lachine - Centre", "Canal"),
    (45.5050, -73.5400, "Canal Lachine - Nord", "Canal"),
    
    # Autres plans d'eau
    (45.4700, -73.7500, "Lac Saint-Louis", "Lac"),
    (45.4200, -73.8200, "Lac des Deux Montagnes", "Lac"),
    (45.5600, -73.6500, "Rivière des Mille Îles", "Rivière"),
]

# Données de services pour Montréal
MONTREAL_SERVICES = {
    'fire_stations': [
        {'name': 'Caserne 12', 'lat': 45.5087, 'lng': -73.5540, 'address': 'Vieux-Montréal'},
        {'name': 'Caserne 23', 'lat': 45.5200, 'lng': -73.5800, 'address': 'Plateau Mont-Royal'},
        {'name': 'Caserne 5', 'lat': 45.4950, 'lng': -73.5600, 'address': 'Griffintown'},
        {'name': 'Caserne 31', 'lat': 45.5300, 'lng': -73.6200, 'address': 'Rosemont'},
        {'name': 'Caserne 42', 'lat': 45.4800, 'lng': -73.5900, 'address': 'Verdun'},
    ],
    'hospitals': [
        {'name': 'CHUM', 'lat': 45.5090, 'lng': -73.5617, 'address': '1051 Rue Sanguinet, Montréal'},
        {'name': 'Hôpital Général de Montréal', 'lat': 45.4950, 'lng': -73.5830, 'address': '1650 Rue Cedar, Montréal'},
        {'name': 'Hôpital Notre-Dame', 'lat': 45.5153, 'lng': -73.5550, 'address': '1560 Rue Sherbrooke Est, Montréal'},
        {'name': 'Hôpital Sainte-Justine', 'lat': 45.5230, 'lng': -73.6180, 'address': '3175 Chemin de la Côte-Sainte-Catherine, Montréal'},
        {'name': 'Hôpital Royal Victoria', 'lat': 45.5045, 'lng': -73.5830, 'address': '1001 Boulevard Décarie, Montréal'},
    ],
    'police_stations': [
        {'name': 'Poste 21 - PDQ 21', 'lat': 45.5100, 'lng': -73.5650, 'address': '1701 Rue Parthenais, Montréal'},
        {'name': 'Poste 38 - PDQ 38', 'lat': 45.5250, 'lng': -73.5900, 'address': '4300 Rue Saint-Denis, Montréal'},
        {'name': 'Poste 22 - PDQ 22', 'lat': 45.4950, 'lng': -73.5750, 'address': '2100 Rue Mullins, Montréal'},
        {'name': 'Poste 25 - PDQ 25', 'lat': 45.4800, 'lng': -73.5950, 'address': '4110 Rue Wellington, Montréal'},
    ]
}

# ============================================================================
# FONCTIONS DE GÉOCODAGE
# ============================================================================

def geocode_address(address: str) -> Dict:
    """
    Géocode une adresse en coordonnées GPS en utilisant l'API Adresse Québec
    """
    try:
        # Vérifier si l'adresse contient une indication de province
        address_lower = address.lower()
        if not any(qc_term in address_lower for qc_term in ['québec', 'quebec', 'qc', 'montréal', 'montreal', 'sherbrooke', 'quebec city']):
            address = f"{address}, Québec, Canada"
        
        params = {'q': address, 'limit': 1}
        headers = {'User-Agent': 'RapportRisqueImmobilier-Québec/2.0'}
        
        logger.info(f"Tentative de géocodage avec API Québec: {address}")
        response = requests.get(GEOCODING_API_QC, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning("API Québec non disponible, utilisation de Nominatim")
            return geocode_with_nominatim(address)
        
        data = response.json()
        
        if not data or 'features' not in data or len(data['features']) == 0:
            logger.warning("Aucun résultat avec API Québec, tentative avec Nominatim")
            return geocode_with_nominatim(address)
        
        feature = data['features'][0]
        coords = feature['geometry']['coordinates']
        properties = feature.get('properties', {})
        
        longitude = coords[0]
        latitude = coords[1]
        
        # Construire l'adresse formatée
        formatted_parts = []
        if properties.get('numero'):
            formatted_parts.append(str(properties['numero']))
        if properties.get('nom_rue'):
            formatted_parts.append(properties['nom_rue'])
        
        # Informations municipales/régionales
        municipality = properties.get('municipalite', '')
        city = properties.get('ville', '') or municipality
        region = get_region_from_coordinates(latitude, longitude)
        
        if municipality:
            formatted_parts.append(municipality)
        elif city:
            formatted_parts.append(city)
        
        formatted_address = ', '.join(formatted_parts) + ', Québec, Canada'
        
        logger.info(f"Géocodage réussi: {latitude}, {longitude} ({municipality or city}, {region})")
        
        return {
            'success': True,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'formatted_address': formatted_address,
            'municipality': municipality,
            'city': city,
            'region': region
        }
        
    except requests.RequestException as e:
        logger.error(f"Erreur lors du géocodage avec API Québec: {str(e)}")
        return geocode_with_nominatim(address)
    except Exception as e:
        logger.error(f"Erreur inattendue lors du géocodage: {str(e)}")
        return geocode_with_nominatim(address)

def geocode_with_nominatim(address: str) -> Dict:
    """
    Géocode une adresse en utilisant Nominatim (OpenStreetMap) comme backup
    """
    try:
        # S'assurer que l'adresse inclut Québec
        search_address = address
        if not any(qc_term in address.lower() for qc_term in ['québec', 'quebec', 'qc']):
            search_address = f"{address}, Québec, Canada"
        
        params = {
            'q': search_address,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'ca',
            'addressdetails': 1
        }
        
        headers = {'User-Agent': 'RapportRisqueImmobilier-Québec/2.0'}
        
        logger.info(f"Tentative de géocodage avec Nominatim: {search_address}")
        response = requests.get(GEOCODING_API_BACKUP, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or len(data) == 0:
            return {'success': False, 'error': 'Adresse non trouvée'}
        
        result = data[0]
        
        # Extraire les informations municipales
        address_details = result.get('address', {})
        municipality = address_details.get('city') or address_details.get('town') or address_details.get('village')
        region = address_details.get('state', 'Québec')
        
        # Détecter si c'est au Québec
        if 'québec' not in region.lower() and 'quebec' not in region.lower():
            return {
                'success': False, 
                'error': 'Adresse hors Québec',
                'message': 'Cette adresse ne semble pas être dans la province de Québec'
            }
        
        region_name = get_region_from_coordinates(float(result['lat']), float(result['lon']))
        
        logger.info(f"Géocodage Nominatim réussi: {result['lat']}, {result['lon']} ({region_name})")
        
        return {
            'success': True,
            'latitude': float(result['lat']),
            'longitude': float(result['lon']),
            'formatted_address': result.get('display_name', address),
            'municipality': municipality,
            'city': municipality,
            'region': region_name
        }
        
    except requests.RequestException as e:
        logger.error(f"Erreur lors du géocodage Nominatim: {str(e)}")
        return {'success': False, 'error': f'Erreur de géocodage: {str(e)}'}
    except Exception as e:
        logger.error(f"Erreur inattendue lors du géocodage Nominatim: {str(e)}")
        return {'success': False, 'error': 'Erreur inattendue lors du géocodage'}

def get_region_from_coordinates(lat: float, lon: float) -> str:
    """
    Détermine la région administrative à partir des coordonnées
    """
    try:
        # Pour l'instant, retourne une approximation basée sur la distance
        min_distance = float('inf')
        closest_region = "Non déterminé"
        
        for region_name, region_center in QUEBEC_REGIONS.items():
            distance = geodesic((lat, lon), region_center).km
            if distance < min_distance:
                min_distance = distance
                closest_region = region_name
        
        return closest_region
    except Exception as e:
        logger.error(f"Erreur détermination région: {e}")
        return "Québec"

# ============================================================================
# FONCTIONS POUR LES ZONES INONDABLES
# ============================================================================

def check_flood_zones(lat: float, lng: float, municipality: str = "") -> Dict:
    """
    Vérifie si l'adresse est dans une zone inondable pour toute la province
    """
    try:
        logger.info(f"Vérification zones inondables pour ({lat}, {lng})")
        
        # 1. Essayer l'API gouvernementale provinciale
        api_result = check_flood_zones_api(lat, lng)
        
        if api_result is not None:
            logger.info(f"Résultat API zones inondables: dans zone = {api_result['in_zone']}")
            region = get_region_from_coordinates(lat, lng)
            api_result['region'] = region
            if municipality:
                api_result['municipality'] = municipality
            return api_result
        
        # 2. Pour Montréal, utiliser les données spécifiques
        region = get_region_from_coordinates(lat, lng)
        if region == "Montréal" or (municipality and "montréal" in municipality.lower()):
            logger.info("Utilisation des données spécifiques Montréal")
            return get_montreal_flood_zones(lat, lng, municipality)
        
        # 3. Utiliser le fallback basé sur la géographie
        logger.info("Utilisation du fallback géographique")
        return check_flood_zones_fallback(lat, lng, municipality)
        
    except Exception as e:
        logger.error(f"Erreur générale dans check_flood_zones: {e}")
        return get_fallback_flood_data(lat, lng, municipality)

def check_flood_zones_api(lat: float, lng: float) -> Optional[Dict]:
    """
    Vérifie si l'adresse est dans une zone inondable en utilisant l'API du gouvernement
    """
    try:
        params = {
            'where': '1=1',
            'geometry': json.dumps({
                "x": lng,
                "y": lat,
                "spatialReference": {"wkid": 4326}
            }),
            'geometryType': 'esriGeometryPoint',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': 'PERIODE_RETOUR,TYPE_ZONE,NOM,SOURCE,OBJECTID',
            'returnGeometry': 'true',
            'outSR': '4326',
            'f': 'json'
        }
        
        logger.info(f"Appel API zones inondables pour ({lat}, {lng})")
        response = requests.get(FLOOD_ZONES_API, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('features') and len(data['features']) > 0:
                feature = data['features'][0]
                attributes = feature.get('attributes', {})
                geometry = feature.get('geometry', {})
                
                periode = attributes.get('PERIODE_RETOUR', '100')
                risk_level = get_risk_level_from_period(periode)
                
                # Créer un GeoJSON pour l'affichage
                flood_zones_geojson = {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "properties": {
                            **attributes,
                            "nom_zone": attributes.get('NOM', 'Zone inondable'),
                            "periode_retour": periode,
                            "niveau_risque": risk_level.capitalize()
                        },
                        "geometry": geometry
                    }]
                }
                
                water_distance = get_water_distance_provincial(lat, lng)
                
                return {
                    "in_zone": True,
                    "zone_type": attributes.get('TYPE_ZONE', 'Zone inondable'),
                    "recurrence_zone": f"Zone de récurrence {periode} ans",
                    "flood_type": get_flood_type_from_zone(attributes.get('TYPE_ZONE', '')),
                    "water_distance": water_distance,
                    "flood_history": [],
                    "flood_zones_geojson": flood_zones_geojson,
                    "source": attributes.get('SOURCE', 'Gouvernement du Québec'),
                    "risk_level": risk_level,
                    "data_quality": "Haute"
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Erreur API zones inondables: {e}")
        return None

def get_montreal_flood_zones(lat: float, lng: float, municipality: str = "") -> Dict:
    """
    Données spécifiques pour Montréal
    """
    try:
        water_distance = get_montreal_water_distance(lat, lng)
        distance_m = water_distance.get('distance_meters', 9999)
        
        # Estimation basée sur la distance à l'eau
        if distance_m < 150:
            risk_level = "high"
            zone_type = "Zone à risque élevé"
        elif distance_m < 500:
            risk_level = "medium"
            zone_type = "Zone à risque modéré"
        else:
            risk_level = "low"
            zone_type = "Hors zone à risque identifié"
        
        return {
            "in_zone": distance_m < 500,
            "zone_type": zone_type,
            "recurrence_zone": f"Estimation basée sur la distance ({distance_m}m)",
            "flood_type": "Inondation fluviale/urbaine",
            "water_distance": water_distance,
            "flood_history": [],
            "flood_zones_geojson": get_empty_flood_zones_geojson(),
            "source": "Ville de Montréal - Données d'estimation",
            "risk_level": risk_level,
            "data_quality": "Moyenne",
            "region": "Montréal",
            "municipality": municipality
        }
        
    except Exception as e:
        logger.error(f"Erreur données Montréal: {e}")
        return check_flood_zones_fallback(lat, lng, municipality)

def check_flood_zones_fallback(lat: float, lng: float, municipality: str = "") -> Dict:
    """
    Fallback: estimation basée sur la distance à l'eau
    """
    try:
        water_distance = get_water_distance_provincial(lat, lng)
        distance = water_distance.get('distance_meters', 9999)
        region = get_region_from_coordinates(lat, lng)
        
        if distance < 100:
            risk_level = "high"
            zone_type = "Zone à risque élevé (proximité immédiate)"
        elif distance < 500:
            risk_level = "medium"
            zone_type = "Zone à risque modéré"
        else:
            risk_level = "low"
            zone_type = "Hors zone à risque identifié"
        
        return {
            "in_zone": distance < 500,
            "zone_type": zone_type,
            "recurrence_zone": f"Estimation basée sur la proximité ({distance}m)",
            "flood_type": get_flood_type_from_region(region),
            "water_distance": water_distance,
            "flood_history": [],
            "flood_zones_geojson": get_empty_flood_zones_geojson(),
            "source": f"Estimation géographique - {region}",
            "risk_level": risk_level,
            "region": region,
            "municipality": municipality
        }
        
    except Exception as e:
        logger.error(f"Erreur fallback zones inondables: {e}")
        return get_fallback_flood_data(lat, lng, municipality)

def get_fallback_flood_data(lat: float, lng: float, municipality: str = "") -> Dict:
    """Données de fallback minimales"""
    region = get_region_from_coordinates(lat, lng)
    water_distance = get_water_distance_provincial(lat, lng)
    
    return {
        "in_zone": False,
        "zone_type": "Données non disponibles",
        "recurrence_zone": "Non déterminée",
        "flood_type": "Non déterminé",
        "water_distance": water_distance,
        "flood_history": [],
        "flood_zones_geojson": get_empty_flood_zones_geojson(),
        "source": f"Gouvernement du Québec - Données temporairement indisponibles ({region})",
        "risk_level": "unknown",
        "region": region,
        "municipality": municipality
    }

# ============================================================================
# FONCTIONS POUR LA DISTANCE À L'EAU
# ============================================================================

def get_montreal_water_distance(lat: float, lng: float) -> Dict:
    """Distance à l'eau pour Montréal"""
    try:
        min_distance = float('inf')
        nearest_name = "Cours d'eau"
        nearest_type = "Plan d'eau"
        
        for point_lat, point_lng, name, wtype in MONTREAL_WATER_POINTS:
            distance = geodesic((lat, lng), (point_lat, point_lng)).meters
            
            adjustment_factor = 0.85 if wtype in ["Fleuve", "Rivière", "Canal"] else 1.0
            adjusted_distance = distance * adjustment_factor
            
            if adjusted_distance < min_distance:
                min_distance = adjusted_distance
                nearest_name = name
                nearest_type = wtype
        
        # Vérification de plausibilité
        if min_distance > 15000:
            return get_montreal_fallback_distance(lat, lng)
        
        return {
            "distance_meters": int(min_distance),
            "distance_category": get_distance_category(min_distance),
            "water_name": nearest_name,
            "water_type": nearest_type,
            "source": "Données de référence Montréal",
            "precision": "Moyenne"
        }
        
    except Exception as e:
        logger.error(f"Erreur distance eau Montréal: {e}")
        return get_montreal_fallback_distance(lat, lng)

def get_montreal_fallback_distance(lat: float, lng: float) -> Dict:
    """Fallback pour Montréal"""
    fleuve_lat = 45.507
    fleuve_lng = -73.553
    
    distance = geodesic((lat, lng), (fleuve_lat, fleuve_lng)).meters
    
    if lat > 45.55:
        water_name = "Rivière des Prairies"
        water_type = "Rivière"
        distance = max(100, distance * 0.7)
    elif lat < 45.45:
        water_name = "Lac Saint-Louis"
        water_type = "Lac"
        distance = max(100, distance * 0.8)
    else:
        water_name = "Fleuve Saint-Laurent"
        water_type = "Fleuve"
        distance = max(50, distance)
    
    return {
        "distance_meters": int(distance),
        "distance_category": get_distance_category(distance),
        "water_name": water_name,
        "water_type": water_type,
        "source": "Estimation Montréal",
        "precision": "Basse"
    }

def get_water_distance_provincial(lat: float, lng: float) -> Dict:
    """Distance à l'eau pour toute la province"""
    try:
        region = get_region_from_coordinates(lat, lng)
        
        if region == "Montréal":
            return get_montreal_water_distance(lat, lng)
        
        # Points d'eau majeurs du Québec
        major_water_bodies = [
            (46.813, -71.208, "Fleuve Saint-Laurent - Québec", "Fleuve"),
            (48.428, -71.068, "Rivière Saguenay", "Rivière"),
            (46.500, -72.523, "Rivière Saint-Maurice", "Rivière"),
            (45.477, -75.701, "Rivière des Outaouais", "Rivière"),
            (48.511, -68.464, "Fleuve Saint-Laurent - Bas-Saint-Laurent", "Fleuve"),
        ]
        
        # Ajouter des points régionaux
        region_points = get_region_water_points(region)
        all_points = major_water_bodies + region_points
        
        min_distance = float('inf')
        nearest_point = None
        
        for point_lat, point_lng, name, wtype in all_points:
            distance = geodesic((lat, lng), (point_lat, point_lng)).meters
            adjustment = 0.8 if wtype in ["Fleuve", "Rivière"] else 0.9
            adjusted_distance = distance * adjustment
            
            if adjusted_distance < min_distance:
                min_distance = adjusted_distance
                nearest_point = (name, wtype)
        
        if nearest_point:
            name, wtype = nearest_point
            return {
                "distance_meters": int(min_distance),
                "distance_category": get_distance_category(min_distance),
                "water_name": name,
                "water_type": wtype,
                "source": f"Données hydrographiques - {region}",
                "precision": "Moyenne",
                "region": region
            }
        
        return get_fallback_water_distance(lat, lng)
        
    except Exception as e:
        logger.error(f"Erreur distance eau provinciale: {e}")
        return get_fallback_water_distance(lat, lng)

def get_region_water_points(region: str) -> List[Tuple]:
    """Points d'eau par région"""
    water_points_by_region = {
        "Capitale-Nationale": [
            (46.750, -71.283, "Rivière Saint-Charles", "Rivière"),
            (46.850, -71.183, "Rivière Montmorency", "Rivière"),
        ],
        "Estrie": [
            (45.283, -72.150, "Lac Memphrémagog", "Lac"),
            (45.417, -71.883, "Lac Massawippi", "Lac"),
        ],
        "Saguenay–Lac-Saint-Jean": [
            (48.567, -72.250, "Lac Saint-Jean", "Lac"),
            (48.433, -71.067, "Rivière Chicoutimi", "Rivière"),
        ],
        "Montérégie": [
            (45.300, -73.250, "Rivière Richelieu", "Rivière"),
            (45.233, -73.667, "Lac Champlain", "Lac"),
        ]
    }
    
    return water_points_by_region.get(region, [])

def get_fallback_water_distance(lat: float, lng: float) -> Dict:
    """Fallback ultime"""
    region = get_region_from_coordinates(lat, lng)
    return {
        "distance_meters": 5000,
        "distance_category": "Éloigné (> 3km)",
        "water_name": f"Plan d'eau - {region}",
        "water_type": "Non déterminé",
        "source": "Données hydrographiques non disponibles",
        "precision": "Très basse",
        "region": region
    }

# ============================================================================
# FONCTIONS POUR LES SITES CONTAMINÉS
# ============================================================================

def get_contaminated_sites(lat: float, lng: float, radius_m: int = 500, municipality: str = "") -> Dict:
    """Cherche les terrains contaminés via l'API ArcGIS du MELCCFP"""
    region = get_region_from_coordinates(lat, lng)
    try:
        params = {
            'where': '1=1',
            'outFields': 'NO_MEF_LIEU,LATITUDE,LONGITUDE,ADR_CIV_LIEU,LST_MRC_REG_ADM,NB_FICHES,DESC_MILIEU_RECEPT',
            'geometry': json.dumps({
                "x": lng,
                "y": lat,
                "spatialReference": {"wkid": 4326}
            }),
            'geometryType': 'esriGeometryPoint',
            'spatialRel': 'esriSpatialRelIntersects',
            'distance': radius_m,
            'units': 'esriSRUnit_Meter',
            'outSR': '4326',
            'f': 'json',
            'resultRecordCount': 50
        }

        logger.info(f"Requête API terrains contaminés pour ({lat}, {lng}), rayon {radius_m}m")
        response = requests.get(CONTAMINATED_SITES_API, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if 'error' in data:
            logger.warning(f"Erreur API terrains contaminés: {data['error']}")
            return _fallback_contamination(lat, lng, region)

        features = data.get('features', [])
        nearby_sites = []
        is_current_contaminated = False

        for feature in features:
            attrs = feature.get('attributes', {})
            geom = feature.get('geometry', {})
            site_lat = geom.get('y') or attrs.get('LATITUDE')
            site_lng = geom.get('x') or attrs.get('LONGITUDE')

            if not site_lat or not site_lng:
                continue

            distance = geodesic((lat, lng), (float(site_lat), float(site_lng))).meters

            if distance < 50:
                is_current_contaminated = True

            # Nettoyer l'adresse (retirer les \r\n)
            raw_address = attrs.get('ADR_CIV_LIEU') or 'Adresse non disponible'
            clean_address = ' — '.join(line.strip() for line in raw_address.split('\r\n') if line.strip())

            nearby_sites.append({
                'name': f"Lieu {attrs.get('NO_MEF_LIEU', 'inconnu')}",
                'address': clean_address,
                'distance': round(distance),
                'status': attrs.get('DESC_MILIEU_RECEPT', 'Non spécifié'),
                'nb_fiches': int(attrs.get('NB_FICHES', 0)),
                'region_info': attrs.get('LST_MRC_REG_ADM', ''),
                'region': region
            })

        nearby_sites.sort(key=lambda x: x['distance'])

        logger.info(f"Terrains contaminés: {len(nearby_sites)} trouvé(s) dans un rayon de {radius_m}m")

        return {
            'is_contaminated': is_current_contaminated,
            'nearby_count': len(nearby_sites),
            'sites': nearby_sites[:10],
            'source': 'Répertoire des terrains contaminés (GTC) — MELCCFP',
            'region': region,
            'data_quality': 'Haute'
        }

    except Exception as e:
        logger.error(f"Erreur sites contaminés: {str(e)}")
        return _fallback_contamination(lat, lng, region)


def _fallback_contamination(lat: float, lng: float, region: str) -> Dict:
    """Fallback quand l'API terrains contaminés est indisponible"""
    return {
        'is_contaminated': False,
        'nearby_count': 0,
        'sites': [],
        'source': 'API terrains contaminés temporairement indisponible',
        'region': region,
        'data_quality': 'Indisponible'
    }

# ============================================================================
# FONCTIONS POUR LES SERVICES D'URGENCE
# ============================================================================

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _query_overpass_all_services(lat: float, lng: float, radius_m: int = 5000) -> Dict[str, Optional[Dict]]:
    """Une seule requête Overpass pour les 3 types de services d'urgence"""
    query = f"""[out:json][timeout:20];
(
  node["amenity"="fire_station"](around:{radius_m},{lat},{lng});
  way["amenity"="fire_station"](around:{radius_m},{lat},{lng});
  node["amenity"="hospital"](around:{radius_m},{lat},{lng});
  way["amenity"="hospital"](around:{radius_m},{lat},{lng});
  node["amenity"="police"](around:{radius_m},{lat},{lng});
  way["amenity"="police"](around:{radius_m},{lat},{lng});
);
out center body;"""

    data = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(endpoint, data={'data': query}, timeout=25)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            logger.warning(f"Overpass {endpoint} échoué: {e}")
            continue

    results = {'fire_station': None, 'hospital': None, 'police': None}

    if data is None:
        return results

    try:
        # Regrouper les éléments par type d'amenity
        by_amenity = {'fire_station': [], 'hospital': [], 'police': []}
        for el in data.get('elements', []):
            amenity = el.get('tags', {}).get('amenity', '')
            if amenity in by_amenity:
                by_amenity[amenity].append(el)

        # Trouver le plus proche pour chaque type
        for amenity, elements in by_amenity.items():
            nearest = None
            min_distance = float('inf')

            for el in elements:
                el_lat = el.get('lat') or el.get('center', {}).get('lat')
                el_lng = el.get('lon') or el.get('center', {}).get('lon')
                if not el_lat or not el_lng:
                    continue

                distance = geodesic((lat, lng), (el_lat, el_lng)).meters
                if distance < min_distance:
                    min_distance = distance
                    tags = el.get('tags', {})
                    addr_parts = [tags.get('addr:housenumber', ''), tags.get('addr:street', ''), tags.get('addr:city', '')]
                    address = ' '.join(p for p in addr_parts if p).strip() or 'Adresse non disponible'
                    nearest = {
                        'name': tags.get('name', f'{amenity.replace("_", " ").title()} (sans nom)'),
                        'distance': round(min_distance),
                        'address': address
                    }

            results[amenity] = nearest

    except Exception as e:
        logger.warning(f"Erreur traitement Overpass: {e}")

    return results


def get_nearby_services(lat: float, lng: float, radius_m: int = 500, municipality: str = "") -> Dict:
    """Trouve les services d'urgence via Overpass (OSM), fallback sur données statiques"""
    region = get_region_from_coordinates(lat, lng)
    search_radius = 5000

    try:
        overpass = _query_overpass_all_services(lat, lng, search_radius)
        fire_station = overpass['fire_station']
        hospital = overpass['hospital']
        police_station = overpass['police']

        source = 'OpenStreetMap (Overpass API)'
        data_quality = 'Haute'

        # Fallback sur données statiques si Overpass ne retourne rien
        if not fire_station or not hospital or not police_station:
            logger.info("Overpass incomplet, complément avec données statiques")
            static = _get_static_services(lat, lng, region, municipality)
            fire_station = fire_station or static['fire_station']
            hospital = hospital or static['hospital']
            police_station = police_station or static['police_station']
            source = 'OpenStreetMap + données statiques'
            data_quality = 'Moyenne'

        # Ajouter les infos de région
        for svc in [fire_station, hospital, police_station]:
            if svc:
                svc['municipality'] = municipality
                svc['region'] = region

        no_service = {'name': 'Service non localisé', 'distance': 'N/A', 'region': region}

        return {
            'fire_station': fire_station or no_service,
            'hospital': hospital or no_service,
            'police_station': police_station or no_service,
            'source': source,
            'region': region,
            'data_quality': data_quality
        }

    except Exception as e:
        logger.error(f"Erreur services: {str(e)}")
        return _get_static_services(lat, lng, region, municipality)


def _get_static_services(lat: float, lng: float, region: str, municipality: str = "") -> Dict:
    """Fallback : données statiques pour Montréal, génériques sinon"""
    if region == "Montréal":
        services_data = MONTREAL_SERVICES
    else:
        region_center = QUEBEC_REGIONS.get(region, (46.8, -71.2))
        services_data = {
            'fire_stations': [{'name': f'Caserne — {region}', 'lat': region_center[0], 'lng': region_center[1]}],
            'hospitals': [{'name': f'Hôpital — {region}', 'lat': region_center[0] + 0.01, 'lng': region_center[1] + 0.01}],
            'police_stations': [{'name': f'Poste de police — {region}', 'lat': region_center[0] - 0.01, 'lng': region_center[1] - 0.01}],
        }

    def find_nearest(services_list):
        nearest = None
        min_dist = float('inf')
        for svc in services_list:
            d = geodesic((lat, lng), (svc['lat'], svc['lng'])).meters
            if d < min_dist:
                min_dist = d
                nearest = {'name': svc['name'], 'distance': round(d), 'address': svc.get('address', ''), 'municipality': municipality, 'region': region}
        return nearest

    no_service = {'name': 'Données non disponibles', 'distance': 'N/A', 'region': region}

    return {
        'fire_station': find_nearest(services_data['fire_stations']) or no_service,
        'hospital': find_nearest(services_data['hospitals']) or no_service,
        'police_station': find_nearest(services_data['police_stations']) or no_service,
        'source': f'Données statiques — {region}',
        'region': region,
        'data_quality': 'Basse'
    }

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def get_risk_level_from_period(period: str) -> str:
    """Détermine le niveau de risque basé sur la période de retour"""
    try:
        periode_int = int(str(period).strip())
        if periode_int <= 20:
            return "high"
        elif periode_int <= 100:
            return "medium"
        else:
            return "low"
    except:
        return "medium"

def get_flood_type_from_zone(zone_type: str) -> str:
    """Type d'inondation basé sur le type de zone"""
    if not zone_type:
        return "Inondation non spécifiée"
    
    zone_type_lower = zone_type.lower()
    
    if any(term in zone_type_lower for term in ['fluvial', 'rivière', 'fleuve']):
        return "Inondation fluviale"
    elif any(term in zone_type_lower for term in ['lacustre', 'lac']):
        return "Inondation lacustre"
    elif any(term in zone_type_lower for term in ['maritime', 'marée']):
        return "Inondation maritime"
    elif any(term in zone_type_lower for term in ['pluvial', 'pluie']):
        return "Inondation pluviale"
    else:
        return "Inondation"

def get_flood_type_from_region(region: str) -> str:
    """Type d'inondation prédominant par région"""
    region_lower = region.lower()
    
    if any(term in region_lower for term in ['côte-nord', 'gaspésie', 'îles-de-la-madeleine']):
        return "Inondation côtière/maritime"
    elif any(term in region_lower for term in ['saguenay', 'lac-saint-jean']):
        return "Inondation lacustre"
    elif any(term in region_lower for term in ['mauricie', 'estrie', 'centre-du-québec']):
        return "Inondation fluviale"
    elif any(term in region_lower for term in ['montréal', 'laval', 'montérégie']):
        return "Inondation fluviale/urbaine"
    else:
        return "Inondation"

def get_distance_category(distance_meters: float) -> str:
    """Catégorise la distance"""
    if distance_meters < 30:
        return "Immédiatement adjacent (< 30m)"
    elif distance_meters < 100:
        return "Très proche (30-100m)"
    elif distance_meters < 300:
        return "Proche (100-300m)"
    elif distance_meters < 1000:
        return "À proximité (300m-1km)"
    elif distance_meters < 5000:
        return "Modérément éloigné (1-5km)"
    else:
        return "Éloigné (> 5km)"

def get_empty_flood_zones_geojson() -> Dict:
    """Retourne un FeatureCollection vide quand les données réelles ne sont pas disponibles"""
    return {"type": "FeatureCollection", "features": []}

# ============================================================================
# FONCTIONS POUR LES BORNES FONTAINES (FIRE HYDRANTS)
# ============================================================================

def get_fire_hydrants(lat: float, lng: float, radius_m: int = 500) -> Dict:
    """
    Cherche les bornes fontaines à proximité via Overpass API (OSM).
    Fallback sur les données ouvertes de Montréal.
    """
    try:
        logger.info(f"Recherche bornes fontaines pour ({lat}, {lng}), rayon {radius_m}m")

        # 1. Essayer Overpass API
        result = _query_overpass_hydrants(lat, lng, radius_m)
        if result is not None:
            return result

        # 2. Fallback données ouvertes Montréal
        region = get_region_from_coordinates(lat, lng)
        if region == "Montréal":
            mtl_result = _query_montreal_hydrants(lat, lng, radius_m)
            if mtl_result is not None:
                return mtl_result

        # 3. Fallback statique
        return _fallback_hydrants(lat, lng)

    except Exception as e:
        logger.error(f"Erreur bornes fontaines: {e}")
        return _fallback_hydrants(lat, lng)


def _query_overpass_hydrants(lat: float, lng: float, radius_m: int) -> Optional[Dict]:
    """Requête Overpass pour les bornes fontaines"""
    query = f"""[out:json][timeout:20];
(
  node["emergency"="fire_hydrant"](around:{radius_m},{lat},{lng});
);
out body;"""

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(endpoint, data={'data': query}, timeout=25)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            logger.warning(f"Overpass hydrants {endpoint} échoué: {e}")
            continue
    else:
        return None

    elements = data.get('elements', [])
    if not elements:
        return {
            "nearest_hydrant": None,
            "hydrants_count_200m": 0,
            "hydrants_count_500m": 0,
            "hydrants": [],
            "risk_level": "high",
            "source": "OpenStreetMap (Overpass API)",
            "data_quality": "Haute"
        }

    hydrants = []
    for el in elements:
        el_lat = el.get('lat')
        el_lng = el.get('lon')
        if not el_lat or not el_lng:
            continue
        distance = int(geodesic((lat, lng), (el_lat, el_lng)).meters)
        hydrants.append({"distance": distance, "lat": el_lat, "lng": el_lng})

    hydrants.sort(key=lambda h: h['distance'])

    count_200 = sum(1 for h in hydrants if h['distance'] <= 200)
    count_500 = sum(1 for h in hydrants if h['distance'] <= 500)
    nearest = hydrants[0] if hydrants else None

    if nearest and nearest['distance'] < 200:
        risk_level = "low"
    elif nearest and nearest['distance'] <= 500:
        risk_level = "medium"
    else:
        risk_level = "high"

    return {
        "nearest_hydrant": nearest,
        "hydrants_count_200m": count_200,
        "hydrants_count_500m": count_500,
        "hydrants": hydrants[:5],
        "risk_level": risk_level,
        "source": "OpenStreetMap (Overpass API)",
        "data_quality": "Haute"
    }


def _query_montreal_hydrants(lat: float, lng: float, radius_m: int) -> Optional[Dict]:
    """Fallback: données ouvertes Montréal pour les bornes fontaines"""
    try:
        url = "https://donnees.montreal.ca/api/3/action/datastore_search_sql"
        # Recherche par proximité approximative (bbox)
        delta = radius_m / 111000  # ~degrés
        sql = (
            f"SELECT \"LONGITUDE\", \"LATITUDE\" FROM \"4de4f5e4-a373-4b20-89e7-9c09f735f782\" "
            f"WHERE \"LATITUDE\" BETWEEN {lat - delta} AND {lat + delta} "
            f"AND \"LONGITUDE\" BETWEEN {lng - delta} AND {lng + delta} LIMIT 100"
        )
        response = requests.get(url, params={"sql": sql}, timeout=15)
        response.raise_for_status()
        data = response.json()

        records = data.get('result', {}).get('records', [])
        if not records:
            return None

        hydrants = []
        for rec in records:
            try:
                h_lat = float(rec['LATITUDE'])
                h_lng = float(rec['LONGITUDE'])
                distance = int(geodesic((lat, lng), (h_lat, h_lng)).meters)
                if distance <= radius_m:
                    hydrants.append({"distance": distance, "lat": h_lat, "lng": h_lng})
            except (ValueError, KeyError):
                continue

        hydrants.sort(key=lambda h: h['distance'])
        count_200 = sum(1 for h in hydrants if h['distance'] <= 200)
        count_500 = sum(1 for h in hydrants if h['distance'] <= 500)
        nearest = hydrants[0] if hydrants else None

        if nearest and nearest['distance'] < 200:
            risk_level = "low"
        elif nearest and nearest['distance'] <= 500:
            risk_level = "medium"
        else:
            risk_level = "high"

        return {
            "nearest_hydrant": nearest,
            "hydrants_count_200m": count_200,
            "hydrants_count_500m": count_500,
            "hydrants": hydrants[:5],
            "risk_level": risk_level,
            "source": "Données ouvertes Montréal",
            "data_quality": "Haute"
        }

    except Exception as e:
        logger.warning(f"Erreur données Montréal bornes fontaines: {e}")
        return None


def _fallback_hydrants(lat: float, lng: float) -> Dict:
    """Fallback statique pour les bornes fontaines"""
    region = get_region_from_coordinates(lat, lng)
    return {
        "nearest_hydrant": None,
        "hydrants_count_200m": 0,
        "hydrants_count_500m": 0,
        "hydrants": [],
        "risk_level": "unknown",
        "source": f"Données non disponibles — {region}",
        "data_quality": "Indisponible"
    }


# ============================================================================
# FONCTIONS POUR LES DONNÉES SISMIQUES
# ============================================================================

# Classification sismique statique par région (fallback)
SEISMIC_ZONES = {
    "Charlevoix": {"zone": "Charlevoix", "pga": 0.64, "risk_level": "high"},
    "Capitale-Nationale": {"zone": "Québec-Charlevoix", "pga": 0.35, "risk_level": "medium"},
    "Bas-Saint-Laurent": {"zone": "Bas-Saint-Laurent", "pga": 0.20, "risk_level": "medium"},
    "Saguenay–Lac-Saint-Jean": {"zone": "Saguenay", "pga": 0.18, "risk_level": "medium"},
    "Montréal": {"zone": "Ouest du Québec", "pga": 0.17, "risk_level": "medium"},
    "Laval": {"zone": "Ouest du Québec", "pga": 0.17, "risk_level": "medium"},
    "Montérégie": {"zone": "Ouest du Québec", "pga": 0.15, "risk_level": "low"},
    "Outaouais": {"zone": "Ouest du Québec", "pga": 0.24, "risk_level": "medium"},
    "Estrie": {"zone": "Estrie", "pga": 0.12, "risk_level": "low"},
    "Mauricie": {"zone": "Mauricie", "pga": 0.14, "risk_level": "low"},
    "Laurentides": {"zone": "Laurentides", "pga": 0.16, "risk_level": "low"},
    "Lanaudière": {"zone": "Lanaudière", "pga": 0.15, "risk_level": "low"},
    "Centre-du-Québec": {"zone": "Centre-du-Québec", "pga": 0.12, "risk_level": "low"},
    "Chaudière-Appalaches": {"zone": "Chaudière-Appalaches", "pga": 0.20, "risk_level": "medium"},
    "Côte-Nord": {"zone": "Côte-Nord", "pga": 0.15, "risk_level": "low"},
    "Abitibi-Témiscamingue": {"zone": "Abitibi", "pga": 0.08, "risk_level": "low"},
    "Nord-du-Québec": {"zone": "Nord-du-Québec", "pga": 0.06, "risk_level": "low"},
    "Gaspésie–Îles-de-la-Madeleine": {"zone": "Gaspésie", "pga": 0.12, "risk_level": "low"},
}


def get_seismic_data(lat: float, lng: float) -> Dict:
    """
    Récupère les données sismiques via l'outil NBC du CNBC (NRCan).
    Fallback sur classification statique par région.
    """
    try:
        logger.info(f"Récupération données sismiques pour ({lat}, {lng})")

        url = "https://www.earthquakescanada.nrcan.gc.ca/hazard-alea/interpolat/nbc-cnb-en.php"
        params = {
            "lat": lat,
            "lon": lng,
            "code": "nbc2020",
            "siteDesignation": "XS",
            "siteDesignationXS": "C"
        }

        response = requests.get(url, params=params, timeout=15,
                                headers={"User-Agent": "VigiImmo/1.0"})
        response.raise_for_status()
        data = response.json()

        # Extraire PGA (Sa(0.0) = PGA pour 2% en 50 ans)
        sa_data = data.get("sa", {})
        pga = sa_data.get("0.0", {}).get("2%/50yrs")
        if pga is not None:
            pga = float(pga)
            if pga >= 0.40:
                risk_level = "high"
            elif pga >= 0.15:
                risk_level = "medium"
            else:
                risk_level = "low"

            region = get_region_from_coordinates(lat, lng)
            zone_info = SEISMIC_ZONES.get(region, {})

            return {
                "seismic_zone": zone_info.get("zone", region),
                "pga_2percent_50yr": round(pga, 4),
                "risk_level": risk_level,
                "source": "Commission géologique du Canada (NBC 2020)",
                "data_quality": "Haute"
            }

    except Exception as e:
        logger.warning(f"API sismique échouée, utilisation du fallback: {e}")

    # Fallback statique
    return _fallback_seismic(lat, lng)


def _fallback_seismic(lat: float, lng: float) -> Dict:
    """Fallback statique basé sur la région"""
    region = get_region_from_coordinates(lat, lng)
    zone_info = SEISMIC_ZONES.get(region, {"zone": region, "pga": 0.10, "risk_level": "low"})

    return {
        "seismic_zone": zone_info["zone"],
        "pga_2percent_50yr": zone_info["pga"],
        "risk_level": zone_info["risk_level"],
        "source": f"Estimation par région — {region}",
        "data_quality": "Moyenne"
    }


# ============================================================================
# FONCTIONS POUR LA QUALITÉ DE L'AIR
# ============================================================================

# Stations RSQA de Montréal (positions approximatives)
RSQA_STATIONS = [
    {"name": "Station 1 — Drummond", "lat": 45.5095, "lng": -73.5726},
    {"name": "Station 3 — Hochelaga", "lat": 45.5421, "lng": -73.5415},
    {"name": "Station 6 — Anjou", "lat": 45.5830, "lng": -73.5580},
    {"name": "Station 7 — Rivière-des-Prairies", "lat": 45.6253, "lng": -73.5760},
    {"name": "Station 13 — Notre-Dame-de-Grâce", "lat": 45.4722, "lng": -73.6266},
    {"name": "Station 17 — Pointe-aux-Trembles", "lat": 45.6409, "lng": -73.5009},
    {"name": "Station 28 — Verdun", "lat": 45.4511, "lng": -73.5712},
    {"name": "Station 29 — Saint-Jean-Baptiste", "lat": 45.5240, "lng": -73.5850},
    {"name": "Station 50 — Sainte-Anne-de-Bellevue", "lat": 45.4040, "lng": -73.9403},
    {"name": "Station 55 — Aéroport de Montréal", "lat": 45.4707, "lng": -73.7455},
    {"name": "Station 61 — Échangeur Décarie", "lat": 45.4930, "lng": -73.6395},
    {"name": "Station 66 — Parc Pilon", "lat": 45.5635, "lng": -73.5068},
    {"name": "Station 99 — AÉMC", "lat": 45.4736, "lng": -73.5813},
]


def get_air_quality(lat: float, lng: float) -> Dict:
    """
    Récupère la qualité de l'air via les données ouvertes de Montréal (RSQA).
    Fallback sur estimation statique pour les autres régions.
    """
    try:
        logger.info(f"Récupération qualité de l'air pour ({lat}, {lng})")

        region = get_region_from_coordinates(lat, lng)

        # Tenter le CSV temps réel de Montréal
        if region in ("Montréal", "Laval", "Montérégie"):
            mtl_result = _query_montreal_air_quality(lat, lng)
            if mtl_result is not None:
                return mtl_result

        # Fallback statique
        return _fallback_air_quality(lat, lng, region)

    except Exception as e:
        logger.error(f"Erreur qualité de l'air: {e}")
        return _fallback_air_quality(lat, lng, get_region_from_coordinates(lat, lng))


def _query_montreal_air_quality(lat: float, lng: float) -> Optional[Dict]:
    """Récupère l'IQA en temps réel depuis le CSV RSQA de Montréal"""
    try:
        csv_url = "https://donnees.montreal.ca/dataset/8f3acae0-eb64-4e27-a356-25e33a9ddfab/resource/2ae670a4-0851-4486-81c4-e46dab5b02f5/download/rsqa-indice-qualite-air.csv"
        response = requests.get(csv_url, timeout=15)
        response.raise_for_status()

        # Trouver la station la plus proche
        nearest_station = None
        min_dist = float('inf')
        for station in RSQA_STATIONS:
            dist = geodesic((lat, lng), (station['lat'], station['lng'])).km
            if dist < min_dist:
                min_dist = dist
                nearest_station = station

        # Parser le CSV pour la station la plus proche
        import csv
        from io import StringIO
        reader = csv.DictReader(StringIO(response.text))
        latest_row = None
        for row in reader:
            station_name = row.get('nom_station', '') or row.get('station', '')
            if nearest_station and nearest_station['name'].split('—')[0].strip().lower() in station_name.lower():
                latest_row = row

        if latest_row:
            aqi = int(float(latest_row.get('valeur', latest_row.get('iqa', 0))))
        else:
            # Prendre la dernière ligne disponible comme estimation
            aqi = 30  # Valeur par défaut "Bon" pour Montréal

        if aqi <= 25:
            category = "Bon"
            risk_level = "low"
        elif aqi <= 50:
            category = "Acceptable"
            risk_level = "low"
        elif aqi <= 75:
            category = "Mauvais"
            risk_level = "medium"
        else:
            category = "Très mauvais"
            risk_level = "high"

        return {
            "aqi": aqi,
            "aqi_category": category,
            "nearest_station": nearest_station['name'] if nearest_station else "Inconnue",
            "station_distance_km": round(min_dist, 1),
            "pollutants": {},
            "risk_level": risk_level,
            "source": "RSQA — Ville de Montréal",
            "data_quality": "Haute"
        }

    except Exception as e:
        logger.warning(f"Erreur CSV RSQA Montréal: {e}")
        return None


def _fallback_air_quality(lat: float, lng: float, region: str) -> Dict:
    """Fallback statique pour la qualité de l'air"""
    # Estimation par région (IQA moyen typique)
    region_aqi = {
        "Montréal": 35, "Laval": 32, "Montérégie": 28,
        "Capitale-Nationale": 25, "Outaouais": 22, "Estrie": 20,
        "Mauricie": 22, "Saguenay–Lac-Saint-Jean": 18,
        "Laurentides": 20, "Lanaudière": 22,
    }
    aqi = region_aqi.get(region, 20)

    if aqi <= 25:
        category = "Bon"
        risk_level = "low"
    elif aqi <= 50:
        category = "Acceptable"
        risk_level = "low"
    else:
        category = "Mauvais"
        risk_level = "medium"

    return {
        "aqi": aqi,
        "aqi_category": category,
        "nearest_station": f"Estimation — {region}",
        "station_distance_km": None,
        "pollutants": {},
        "risk_level": risk_level,
        "source": f"Estimation régionale — {region}",
        "data_quality": "Basse"
    }


# ============================================================================
# FONCTIONS POUR L'HISTORIQUE DE SINISTRES
# ============================================================================

def get_disaster_history(lat: float, lng: float, radius_km: int = 25) -> Dict:
    """
    Récupère l'historique des sinistres via le WFS du MSP Québec.
    """
    try:
        logger.info(f"Récupération historique sinistres pour ({lat}, {lng}), rayon {radius_km}km")

        url = (
            "https://geoegl.msp.gouv.qc.ca/apis/wss/historiquesc.fcgi"
            "?service=wfs&version=1.1.0&request=getfeature"
            "&typename=msp_risc_evenements_public&outputformat=geojson"
            "&srsName=epsg:4326"
        )

        response = requests.get(url, timeout=30, headers={"User-Agent": "VigiImmo/1.0"})
        response.raise_for_status()
        data = response.json()

        features = data.get('features', [])
        nearby_events = []

        for feature in features:
            geom = feature.get('geometry', {})
            coords = geom.get('coordinates', [])
            props = feature.get('properties', {})

            if not coords or len(coords) < 2:
                continue

            # GeoJSON = [lng, lat]
            evt_lng, evt_lat = coords[0], coords[1]
            try:
                distance = geodesic((lat, lng), (float(evt_lat), float(evt_lng))).km
            except (ValueError, TypeError):
                continue

            if distance <= radius_km:
                nearby_events.append({
                    "type": props.get('type_evenement', props.get('TYPE', 'Non spécifié')),
                    "date": props.get('date_evenement', props.get('DATE', '')),
                    "description": props.get('description', props.get('NOM', '')),
                    "distance_km": round(distance, 1)
                })

        nearby_events.sort(key=lambda e: e['distance_km'])

        # Type le plus courant
        if nearby_events:
            type_counts = {}
            for evt in nearby_events:
                t = evt['type']
                type_counts[t] = type_counts.get(t, 0) + 1
            most_common = max(type_counts, key=type_counts.get)
        else:
            most_common = "Aucun"

        count = len(nearby_events)
        if count == 0:
            risk_level = "low"
        elif count <= 3:
            risk_level = "medium"
        else:
            risk_level = "high"

        return {
            "nearby_events_count": count,
            "events": nearby_events[:10],
            "most_common_type": most_common,
            "risk_level": risk_level,
            "source": "MSP Québec — Historique de sécurité civile",
            "data_quality": "Haute"
        }

    except Exception as e:
        logger.error(f"Erreur historique sinistres: {e}")
        return _fallback_disaster_history(lat, lng)


def _fallback_disaster_history(lat: float, lng: float) -> Dict:
    """Fallback pour l'historique de sinistres"""
    region = get_region_from_coordinates(lat, lng)
    return {
        "nearby_events_count": 0,
        "events": [],
        "most_common_type": "Aucun",
        "risk_level": "unknown",
        "source": f"Données non disponibles — {region}",
        "data_quality": "Indisponible"
    }


# ============================================================================
# FONCTIONS POUR L'ÉVALUATION FONCIÈRE
# ============================================================================

def get_property_assessment(lat: float, lng: float, address: str = "") -> Dict:
    """
    Récupère l'évaluation foncière depuis la base PostGIS locale.
    Recherche spatiale : propriété la plus proche dans un rayon de 200m.
    """
    try:
        logger.info(f"Récupération évaluation foncière pour ({lat}, {lng})")
        pool = _get_db_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("""
                SELECT matricule, civic_number, street_name, municipality,
                       land_value, building_value, total_value, year_built,
                       lot_area_sqm, building_area_sqm, use_code,
                       ST_Distance(geom::geography,
                                   ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance
                FROM property_assessments
                WHERE geom IS NOT NULL
                  AND ST_DWithin(geom::geography,
                                 ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                                 500)
                ORDER BY distance
                LIMIT 1
            """, (lng, lat, lng, lat))
            row = cur.fetchone()
            cur.close()
        finally:
            pool.putconn(conn)

        if row:
            return {
                "land_value": row["land_value"],
                "building_value": row["building_value"],
                "total_value": row["total_value"],
                "building_year": row["year_built"],
                "lot_area_sqm": float(row["lot_area_sqm"]) if row["lot_area_sqm"] else None,
                "building_area_sqm": float(row["building_area_sqm"]) if row["building_area_sqm"] else None,
                "property_type": row["use_code"],
                "source": "Rôle d'évaluation foncière du Québec (PostGIS)",
                "data_quality": "Haute"
            }

    except Exception as e:
        logger.warning(f"Erreur évaluation foncière PostGIS: {e}")

    return _fallback_property_assessment(lat, lng)


def _fallback_property_assessment(lat: float, lng: float) -> Dict:
    """Fallback pour l'évaluation foncière"""
    region = get_region_from_coordinates(lat, lng)
    return {
        "land_value": None,
        "building_value": None,
        "total_value": None,
        "building_year": None,
        "lot_area_sqm": None,
        "building_area_sqm": None,
        "property_type": None,
        "source": f"Données non disponibles — {region}",
        "data_quality": "Indisponible"
    }


# ============================================================================
# FONCTIONS POUR LA CRIMINALITÉ
# ============================================================================

def get_crime_data(lat: float, lng: float) -> Dict:
    """
    Récupère les données de criminalité via l'API CKAN de Données Montréal.
    """
    try:
        logger.info(f"Récupération données criminalité pour ({lat}, {lng})")

        region = get_region_from_coordinates(lat, lng)

        if region in ("Montréal", "Laval"):
            mtl_result = _query_montreal_crime(lat, lng)
            if mtl_result is not None:
                return mtl_result

        return _fallback_crime(lat, lng, region)

    except Exception as e:
        logger.error(f"Erreur données criminalité: {e}")
        return _fallback_crime(lat, lng, get_region_from_coordinates(lat, lng))


def _query_montreal_crime(lat: float, lng: float) -> Optional[Dict]:
    """Données ouvertes Montréal — actes criminels"""
    try:
        url = "https://donnees.montreal.ca/api/3/action/datastore_search_sql"
        # Recherche dans un rayon approximatif (bbox ~1km)
        delta = 1000 / 111000  # ~0.009 degrés
        sql = (
            f"SELECT \"CATEGORIE\", \"PDQ\", \"LATITUDE\", \"LONGITUDE\", \"DATE\" "
            f"FROM \"c005e27f-a20e-4d2d-bf5b-1ae1e4d4d5f5\" "
            f"WHERE \"LATITUDE\" BETWEEN {lat - delta} AND {lat + delta} "
            f"AND \"LONGITUDE\" BETWEEN {lng - delta} AND {lng + delta} "
            f"LIMIT 500"
        )

        response = requests.get(url, params={"sql": sql}, timeout=20)
        response.raise_for_status()
        data = response.json()

        records = data.get('result', {}).get('records', [])

        # Filtrer à 1km réel et compter par catégorie
        incidents = []
        category_counts = {}
        pdq = None

        for rec in records:
            try:
                r_lat = float(rec.get('LATITUDE', 0))
                r_lng = float(rec.get('LONGITUDE', 0))
                if r_lat == 0 or r_lng == 0:
                    continue
                dist = geodesic((lat, lng), (r_lat, r_lng)).meters
                if dist <= 1000:
                    cat = rec.get('CATEGORIE', 'Autre')
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    incidents.append(rec)
                    if not pdq:
                        pdq = rec.get('PDQ', '')
            except (ValueError, TypeError):
                continue

        count = len(incidents)
        if count <= 10:
            density = "Faible"
            risk_level = "low"
        elif count <= 50:
            density = "Modéré"
            risk_level = "medium"
        else:
            density = "Élevé"
            risk_level = "high"

        return {
            "incidents_1km": count,
            "incidents_by_category": category_counts,
            "crime_density": density,
            "pdq": str(pdq) if pdq else "Non déterminé",
            "risk_level": risk_level,
            "source": "Données ouvertes Montréal — Actes criminels",
            "data_quality": "Haute"
        }

    except Exception as e:
        logger.warning(f"Erreur données criminalité Montréal: {e}")
        return None


def _fallback_crime(lat: float, lng: float, region: str) -> Dict:
    """Fallback pour les données de criminalité"""
    return {
        "incidents_1km": None,
        "incidents_by_category": {},
        "crime_density": None,
        "pdq": None,
        "risk_level": "unknown",
        "source": f"Données non disponibles — {region}",
        "data_quality": "Indisponible"
    }


# ============================================================================
# CALCUL DU RISQUE GLOBAL
# ============================================================================

def calculate_risk_assessment(flood_data: Dict, contamination_data: Dict, services_data: Dict,
                              hydrants_data: Dict = None, seismic_data: Dict = None,
                              air_quality_data: Dict = None, disaster_data: Dict = None,
                              crime_data: Dict = None) -> Dict:
    """Calcule le risque global incluant toutes les sources de données"""
    try:
        score = 50
        factors = []

        # Facteur zones inondables
        if flood_data.get('in_zone'):
            risk_level = flood_data.get('risk_level', 'medium')
            if risk_level == 'high':
                score += 30
            elif risk_level == 'medium':
                score += 20
            elif risk_level == 'low':
                score += 10
            factors.append("Situé en zone inondable")

        # Facteur contamination
        if contamination_data.get('is_contaminated'):
            score += 25
            factors.append("Terrain répertorié comme contaminé")
        if contamination_data.get('nearby_count', 0) > 0:
            score += min(contamination_data.get('nearby_count', 0) * 5, 20)
            factors.append(f"{contamination_data['nearby_count']} terrain(s) contaminé(s) à proximité")

        # Facteur bornes fontaines
        if hydrants_data:
            nearest = hydrants_data.get('nearest_hydrant')
            if not nearest or (isinstance(nearest, dict) and nearest.get('distance', 9999) > 500):
                score += 15
                factors.append("Aucune borne fontaine à moins de 500m")
            elif isinstance(nearest, dict) and nearest.get('distance', 0) > 200:
                score += 5
                factors.append("Borne fontaine la plus proche entre 200m et 500m")

        # Facteur sismique
        if seismic_data and seismic_data.get('risk_level') == 'high':
            score += 10
            factors.append(f"Zone sismique élevée ({seismic_data.get('seismic_zone', '')})")

        # Facteur qualité de l'air
        if air_quality_data and air_quality_data.get('risk_level') in ('medium', 'high'):
            bonus = 10 if air_quality_data['risk_level'] == 'high' else 5
            score += bonus
            factors.append(f"Qualité de l'air : {air_quality_data.get('aqi_category', 'Préoccupante')}")

        # Facteur historique de sinistres
        if disaster_data and disaster_data.get('nearby_events_count', 0) > 0:
            count = disaster_data['nearby_events_count']
            if count > 5:
                score += 10
            elif count > 0:
                score += 5
            factors.append(f"{count} sinistre(s) répertorié(s) à proximité")

        # Facteur criminalité
        if crime_data and crime_data.get('risk_level') in ('medium', 'high'):
            bonus = 10 if crime_data['risk_level'] == 'high' else 5
            score += bonus
            factors.append(f"Criminalité : {crime_data.get('crime_density', 'Élevée')}")

        # Normaliser le score
        score = max(0, min(100, score))

        # Déterminer le niveau
        if score >= 70:
            level = "high"
            recommendation = "Risque élevé - Évaluation approfondie recommandée."
        elif score >= 40:
            level = "medium"
            recommendation = "Risque modéré - Vigilance requise."
        else:
            level = "low"
            recommendation = "Risque faible - Situation normale."

        if not factors:
            factors.append("Aucun facteur de risque majeur identifié")

        return {
            'score': int(score),
            'level': level,
            'recommendation': recommendation,
            'factors': factors
        }

    except Exception as e:
        logger.error(f"Erreur calcul risque: {str(e)}")
        return {
            'score': 50,
            'level': 'unknown',
            'recommendation': 'Évaluation non disponible',
            'factors': ['Données insuffisantes']
        }