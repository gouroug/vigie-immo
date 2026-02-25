import os
import json
import logging
from datetime import datetime, timezone

import psycopg2
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from data_fetcher import (
    geocode_address,
    check_flood_zones,
    get_contaminated_sites,
    get_nearby_services,
    get_fire_hydrants,
    get_seismic_data,
    get_air_quality,
    get_disaster_history,
    get_property_assessment,
    get_crime_data,
    calculate_risk_assessment,
)
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    require_auth,
    require_admin,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

_origins_env = os.environ.get('ALLOWED_ORIGINS', '').strip()
ALLOWED_ORIGINS = [o for o in _origins_env.split(',') if o] if _origins_env else []
if ALLOWED_ORIGINS:
    CORS(app, origins=ALLOWED_ORIGINS)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

_log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_DSN = os.environ.get('VIGIE_DB_DSN', 'dbname=vigie_immo')

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Return a per-request cached psycopg2 connection."""
    if 'db' not in g:
        g.db = psycopg2.connect(DB_DSN)
        g.db.autocommit = False
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        if exc is None:
            db.commit()
        else:
            db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# Auth routes — public
# ---------------------------------------------------------------------------

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """POST /api/auth/login — email + password → tokens"""
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email et mot de passe requis'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'SELECT id, email, name, password_hash, status, is_admin FROM users WHERE email = %s',
        (email,)
    )
    row = cur.fetchone()
    cur.close()

    if row is None or not verify_password(password, row[3]):
        return jsonify({'success': False, 'error': 'Identifiants incorrects'}), 401

    user_id, user_email, user_name, _, status, is_admin = row

    if status != 'active':
        return jsonify({'success': False, 'error': 'Compte suspendu'}), 403

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    return jsonify({
        'success': True,
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user_id,
            'email': user_email,
            'name': user_name,
            'is_admin': is_admin,
        }
    }), 200


@app.route('/api/auth/refresh', methods=['POST'])
@limiter.limit("20 per minute")
def refresh():
    """POST /api/auth/refresh — refresh_token → new access_token"""
    data = request.get_json(force=True, silent=True) or {}
    refresh_token = data.get('refresh_token') or ''

    if not refresh_token:
        return jsonify({'success': False, 'error': 'Refresh token manquant'}), 400

    try:
        import jwt as pyjwt
        payload = decode_token(refresh_token)
    except Exception:
        return jsonify({'success': False, 'error': 'Refresh token invalide ou expiré'}), 401

    if payload.get('type') != 'refresh':
        return jsonify({'success': False, 'error': 'Type de token invalide'}), 401

    jti = payload.get('jti', '')
    conn = get_db()
    cur = conn.cursor()

    # Vérifier si le token est blacklisté
    cur.execute('SELECT 1 FROM token_blacklist WHERE token_jti = %s', (jti,))
    if cur.fetchone():
        cur.close()
        return jsonify({'success': False, 'error': 'Token révoqué'}), 401

    user_id = payload['sub']
    cur.execute('SELECT status FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()

    if user is None or user[0] != 'active':
        return jsonify({'success': False, 'error': 'Compte inactif'}), 403

    return jsonify({
        'success': True,
        'access_token': create_access_token(user_id)
    }), 200


@app.route('/api/auth/logout', methods=['POST'])
@limiter.limit("20 per minute")
def logout():
    """POST /api/auth/logout — blacklist the refresh token"""
    data = request.get_json(force=True, silent=True) or {}
    refresh_token = data.get('refresh_token') or ''

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get('jti', '')
            import datetime as dt
            from datetime import timezone as tz
            exp = payload.get('exp')
            expires_at = datetime.fromtimestamp(exp, tz=tz.utc) if exp else datetime.now(tz=tz.utc)

            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO token_blacklist (token_jti, expires_at) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (jti, expires_at)
            )
            cur.close()
        except Exception:
            pass  # Token déjà invalide, on ignore

    return jsonify({'success': True, 'message': 'Déconnecté'}), 200


# ---------------------------------------------------------------------------
# Auth routes — authenticated user
# ---------------------------------------------------------------------------

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def me():
    """GET /api/auth/me — current user profile"""
    return jsonify({'success': True, 'user': g.user}), 200


@app.route('/api/auth/password', methods=['PUT'])
@require_auth
def change_password():
    """PUT /api/auth/password — change current user's password"""
    data = request.get_json(force=True, silent=True) or {}
    current = data.get('current_password') or ''
    new_pw = data.get('new_password') or ''

    if not current or not new_pw:
        return jsonify({'success': False, 'error': 'Mot de passe actuel et nouveau requis'}), 400

    if len(new_pw) < 8:
        return jsonify({'success': False, 'error': 'Le nouveau mot de passe doit faire au moins 8 caractères'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT password_hash FROM users WHERE id = %s', (g.user_id,))
    row = cur.fetchone()

    if row is None or not verify_password(current, row[0]):
        cur.close()
        return jsonify({'success': False, 'error': 'Mot de passe actuel incorrect'}), 400

    new_hash = hash_password(new_pw)
    cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', (new_hash, g.user_id))
    cur.close()

    return jsonify({'success': True, 'message': 'Mot de passe modifié'}), 200


@app.route('/api/history', methods=['GET'])
@require_auth
def get_history():
    """GET /api/history — analysis history for current user"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        '''SELECT id, address, risk_score, created_at
           FROM analysis_history
           WHERE user_id = %s
           ORDER BY created_at DESC
           LIMIT 50''',
        (g.user_id,)
    )
    rows = cur.fetchall()
    cur.close()

    history = [
        {
            'id': r[0],
            'address': r[1],
            'risk_score': r[2],
            'created_at': r[3].isoformat(),
        }
        for r in rows
    ]
    return jsonify({'success': True, 'history': history}), 200


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_list_users():
    """GET /api/admin/users — list all users"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        '''SELECT id, email, name, status, is_admin, created_at
           FROM users ORDER BY created_at DESC'''
    )
    rows = cur.fetchall()
    cur.close()

    users = [
        {
            'id': r[0],
            'email': r[1],
            'name': r[2],
            'status': r[3],
            'is_admin': r[4],
            'created_at': r[5].isoformat(),
        }
        for r in rows
    ]
    return jsonify({'success': True, 'users': users}), 200


@app.route('/api/admin/users', methods=['POST'])
@require_admin
def admin_create_user():
    """POST /api/admin/users — create a new user account"""
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()
    password = data.get('password') or ''
    is_admin = bool(data.get('is_admin', False))

    if not email or not name or not password:
        return jsonify({'success': False, 'error': 'email, name et password sont requis'}), 400

    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Le mot de passe doit faire au moins 8 caractères'}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            '''INSERT INTO users (email, name, password_hash, is_admin, created_by)
               VALUES (%s, %s, %s, %s, %s) RETURNING id''',
            (email, name, hash_password(password), is_admin, g.user_id)
        )
        new_id = cur.fetchone()[0]
        cur.close()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        return jsonify({'success': False, 'error': 'Cet email existe déjà'}), 409

    return jsonify({'success': True, 'user': {'id': new_id, 'email': email, 'name': name}}), 201


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@require_admin
def admin_update_user(user_id):
    """PUT /api/admin/users/<id> — update status or is_admin"""
    data = request.get_json(force=True, silent=True) or {}

    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE id = %s', (user_id,))
    if cur.fetchone() is None:
        cur.close()
        return jsonify({'success': False, 'error': 'Utilisateur introuvable'}), 404

    updates = []
    params = []

    if 'status' in data:
        if data['status'] not in ('active', 'suspended'):
            cur.close()
            return jsonify({'success': False, 'error': 'Statut invalide (active ou suspended)'}), 400
        updates.append('status = %s')
        params.append(data['status'])

    if 'is_admin' in data:
        updates.append('is_admin = %s')
        params.append(bool(data['is_admin']))

    if not updates:
        cur.close()
        return jsonify({'success': False, 'error': 'Aucun champ à modifier'}), 400

    params.append(user_id)
    cur.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = %s', params)
    cur.close()

    return jsonify({'success': True, 'message': 'Utilisateur mis à jour'}), 200


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_admin
def admin_delete_user(user_id):
    """DELETE /api/admin/users/<id> — delete a user"""
    if user_id == g.user_id:
        return jsonify({'success': False, 'error': 'Impossible de supprimer son propre compte'}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE id = %s RETURNING id', (user_id,))
    deleted = cur.fetchone()
    cur.close()

    if deleted is None:
        return jsonify({'success': False, 'error': 'Utilisateur introuvable'}), 404

    return jsonify({'success': True, 'message': 'Utilisateur supprimé'}), 200


# ---------------------------------------------------------------------------
# Main analyze route — protected
# ---------------------------------------------------------------------------

@app.route('/api/analyze', methods=['POST'])
@require_auth
@limiter.limit("20 per minute")
def analyze_address():
    """POST /api/analyze — analyse une adresse (authentification requise)"""
    if g.user.get('status') != 'active':
        return jsonify({'success': False, 'error': 'Compte suspendu'}), 403

    try:
        data = request.get_json(force=True, silent=True)
        logger.info(f"📥 Requête reçue pour l'adresse: {data.get('address', 'Non spécifiée')}")

        if not data or 'address' not in data:
            return jsonify({
                'success': False,
                'error': 'Adresse manquante',
                'message': 'Le champ "address" est requis'
            }), 400

        address = data['address']
        logger.info(f"🔍 Début de l'analyse pour: {address}")

        geocode_result = geocode_address(address)
        if not geocode_result['success']:
            return jsonify({
                'success': False,
                'error': 'Géocodage échoué',
                'message': geocode_result.get('error', 'Impossible de localiser cette adresse')
            }), 404

        lat = geocode_result['latitude']
        lng = geocode_result['longitude']
        formatted_address = geocode_result['formatted_address']

        flood_data = check_flood_zones(lat, lng, geocode_result.get('municipality', ''))
        contamination_data = get_contaminated_sites(lat, lng, radius_m=500,
                                                    municipality=geocode_result.get('municipality', ''))
        services_data = get_nearby_services(lat, lng, radius_m=500,
                                            municipality=geocode_result.get('municipality', ''))
        hydrants_data = get_fire_hydrants(lat, lng, radius_m=500)
        seismic_data = get_seismic_data(lat, lng)
        air_quality_data = get_air_quality(lat, lng)
        disaster_data = get_disaster_history(lat, lng, radius_km=25)
        property_data = get_property_assessment(lat, lng, address=address)
        crime_data_result = get_crime_data(lat, lng)
        risk_score = calculate_risk_assessment(
            flood_data, contamination_data, services_data,
            hydrants_data=hydrants_data,
            seismic_data=seismic_data,
            air_quality_data=air_quality_data,
            disaster_data=disaster_data,
            crime_data=crime_data_result
        )

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
            'hydrants': hydrants_data,
            'seismic': seismic_data,
            'air_quality': air_quality_data,
            'disaster_history': disaster_data,
            'property_assessment': property_data,
            'crime': crime_data_result,
            'risk_assessment': risk_score
        }

        # Sauvegarder dans l'historique
        try:
            score_val = None
            if isinstance(risk_score, dict):
                score_val = risk_score.get('overall_score') or risk_score.get('score')

            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                '''INSERT INTO analysis_history (user_id, address, risk_score, result_json)
                   VALUES (%s, %s, %s, %s)''',
                (g.user_id, formatted_address, score_val, json.dumps(response))
            )
            cur.close()
        except Exception as hist_err:
            logger.warning(f"⚠️ Impossible de sauvegarder l'historique: {hist_err}")

        logger.info(f"✅ Analyse complétée pour {address}")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"💥 ERREUR CRITIQUE: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Erreur serveur',
            'message': "Une erreur s'est produite lors de l'analyse"
        }), 500


# ---------------------------------------------------------------------------
# Utility routes
# ---------------------------------------------------------------------------

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    return jsonify({
        'success': True,
        'message': 'API Vigie-Immo - Fonctionnelle',
        'version': '3.0.0',
        'status': 'OK',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Vigie-Immo',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


# ---------------------------------------------------------------------------
# Init admin script helper — run once: python app.py --init-admin
# ---------------------------------------------------------------------------

def _init_admin():
    """Create initial admin account from environment variables."""
    import psycopg2 as pg
    email = os.environ.get('ADMIN_EMAIL', 'admin@vigie-immo.ca')
    password = os.environ.get('ADMIN_PASSWORD', '')
    if not password:
        print("ADMIN_PASSWORD non défini dans .env")
        return

    conn = pg.connect(DB_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(
            '''INSERT INTO users (email, name, password_hash, is_admin)
               VALUES (%s, %s, %s, TRUE)
               ON CONFLICT (email) DO NOTHING''',
            (email, 'Admin', hash_password(password))
        )
        print(f"✅ Admin créé : {email}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    import sys
    if '--init-admin' in sys.argv:
        _init_admin()
        sys.exit(0)

    logger.info("🚀 Démarrage du serveur API Vigie-Immo v3.0")
    logger.info("📋 Endpoints: /api/auth/login | /api/analyze | /api/history | /api/admin/users")
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode, threaded=True)
