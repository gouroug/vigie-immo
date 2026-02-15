import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import json  # IMPORT AJOUTÉ
from data_fetcher import (
    geocode_address,
    check_flood_zones,
    get_contaminated_sites,
    get_nearby_services,
    calculate_risk_assessment
)

app = Flask(__name__)

# CORS restreint aux origines autorisées
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://192.168.0.29,http://localhost').split(',')
CORS(app, origins=ALLOWED_ORIGINS)

# Rate limiting — protection contre le spam
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

# Configurer le logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.route('/api/analyze', methods=['POST'])
@limiter.limit("20 per minute")
def analyze_address():
    """
    Endpoint principal pour analyser une adresse
    """
    try:
        # Log la requête entrante
        data = request.get_json()
        logger.info(f"📥 Requête reçue pour l'adresse: {data.get('address', 'Non spécifiée')}")
        
        if not data or 'address' not in data:
            logger.warning("❌ Requête invalide: champ 'address' manquant")
            return jsonify({
                'success': False,
                'error': 'Adresse manquante',
                'message': 'Le champ "address" est requis'
            }), 400
        
        address = data['address']
        logger.info(f"🔍 Début de l'analyse pour: {address}")
        
        # 1. Géocoder l'adresse
        logger.debug("📍 Étape 1/5: Géocodage...")
        geocode_result = geocode_address(address)
        
        if not geocode_result['success']:
            logger.error(f"❌ Échec du géocodage: {geocode_result.get('error', 'Erreur inconnue')}")
            return jsonify({
                'success': False,
                'error': 'Géocodage échoué',
                'message': geocode_result.get('error', 'Impossible de localiser cette adresse')
            }), 404
        
        lat = geocode_result['latitude']
        lng = geocode_result['longitude']
        formatted_address = geocode_result['formatted_address']
        
        logger.info(f"📍 Géocodage réussi: {lat}, {lng}")
        
        # 2. Vérifier les zones inondables
        logger.debug("💧 Étape 2/5: Vérification des zones inondables...")
        flood_data = check_flood_zones(lat, lng, geocode_result.get('municipality', ''))
        
        # 3. Chercher les terrains contaminés
        logger.debug("⚠️ Étape 3/5: Recherche des terrains contaminés...")
        contamination_data = get_contaminated_sites(lat, lng, radius_m=500, 
                                                   municipality=geocode_result.get('municipality', ''))
        
        # 4. Trouver les services d'urgence
        logger.debug("🚒 Étape 4/5: Recherche des services d'urgence...")
        services_data = get_nearby_services(lat, lng, radius_m=500, 
                                           municipality=geocode_result.get('municipality', ''))
        
        # 5. Calculer le score de risque
        logger.debug("📊 Étape 5/5: Calcul du score de risque...")
        risk_score = calculate_risk_assessment(flood_data, contamination_data, services_data)
        
        # Construire la réponse
        response = {
            'success': True,
            'address': {
                'input': address,
                'formatted': formatted_address,
                'latitude': lat,
                'longitude': lng,
                'municipality': geocode_result.get('municipality', ''),
                'city': geocode_result.get('city', ''),
                'region': geocode_result.get('region', ''),
                'province': 'Québec'
            },
            'flood_zones': flood_data,
            'contamination': contamination_data,
            'services': services_data,
            'risk_assessment': risk_score
        }
        
        logger.info(f"✅ Analyse complétée avec succès pour {address}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"💥 ERREUR CRITIQUE lors de l'analyse: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Erreur serveur',
            'message': 'Une erreur s\'est produite lors de l\'analyse'
        }), 500

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Endpoint de test simple"""
    return jsonify({
        'success': True,
        'message': 'API Rapport Risque Immobilier Québec - Fonctionnelle',
        'version': '2.0.0',
        'status': 'OK',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de vérification de santé"""
    return jsonify({
        'status': 'healthy',
        'service': 'Rapport Risque Immobilier Québec',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200

if __name__ == '__main__':
    logger.info("🚀 Démarrage du serveur API...")
    logger.info("🌐 URL: http://0.0.0.0:5000")
    logger.info("📋 Endpoints disponibles:")
    logger.info("   GET  /api/test - Test de l'API")
    logger.info("   GET  /api/health - Vérification santé")
    logger.info("   POST /api/analyze - Analyse d'adresse")
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f"🔄 Mode debug: {'ACTIVÉ' if debug_mode else 'DÉSACTIVÉ'}")

    # Démarrer le serveur
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=debug_mode,
        threaded=True  # Permet de gérer plusieurs requêtes
    )