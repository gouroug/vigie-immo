"""
auth.py — JWT + bcrypt authentication helpers for Vigie-Immo
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import request, jsonify, g

JWT_SECRET = os.environ.get('JWT_SECRET', 'changeme-set-in-env')
JWT_ACCESS_EXPIRE = int(os.environ.get('JWT_ACCESS_EXPIRE', 3600))       # 1h
JWT_REFRESH_EXPIRE = int(os.environ.get('JWT_REFRESH_EXPIRE', 2592000))  # 30j
ALGORITHM = 'HS256'


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if password matches the stored hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: int) -> str:
    """Create a signed JWT access token (expires in JWT_ACCESS_EXPIRE seconds)."""
    now = datetime.now(timezone.utc)
    payload = {
        'sub': user_id,
        'iat': now,
        'exp': now + timedelta(seconds=JWT_ACCESS_EXPIRE),
        'type': 'access',
        'jti': str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a signed JWT refresh token (expires in JWT_REFRESH_EXPIRE seconds)."""
    now = datetime.now(timezone.utc)
    payload = {
        'sub': user_id,
        'iat': now,
        'exp': now + timedelta(seconds=JWT_REFRESH_EXPIRE),
        'type': 'refresh',
        'jti': str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Returns the payload dict or raises jwt.PyJWTError on failure.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# Flask decorators
# ---------------------------------------------------------------------------

def _get_db():
    """Import get_db lazily to avoid circular imports."""
    from app import get_db
    return get_db()


def require_auth(f):
    """
    Flask decorator — validates JWT access token in Authorization header.
    Sets g.user_id and g.user on success.
    Returns 401 on missing/invalid token.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token manquant'}), 401

        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token expiré'}), 401
        except jwt.PyJWTError:
            return jsonify({'success': False, 'error': 'Token invalide'}), 401

        if payload.get('type') != 'access':
            return jsonify({'success': False, 'error': 'Type de token invalide'}), 401

        user_id = payload['sub']
        conn = _get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT id, email, name, status, is_admin FROM users WHERE id = %s',
            (user_id,)
        )
        row = cur.fetchone()
        cur.close()

        if row is None:
            return jsonify({'success': False, 'error': 'Utilisateur introuvable'}), 401

        g.user_id = row[0]
        g.user = {
            'id': row[0],
            'email': row[1],
            'name': row[2],
            'status': row[3],
            'is_admin': row[4],
        }
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """
    Flask decorator — requires authenticated admin user.
    Must be used AFTER @require_auth (or includes its logic).
    """
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not g.user.get('is_admin'):
            return jsonify({'success': False, 'error': 'Accès réservé aux administrateurs'}), 403
        return f(*args, **kwargs)

    return decorated
