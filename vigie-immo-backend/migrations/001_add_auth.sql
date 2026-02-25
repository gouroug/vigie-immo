-- Migration 001: Authentification et contrôle d'accès
-- Vigie-Immo

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, suspended
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by    INTEGER REFERENCES users(id)
);

-- Table de l'historique des analyses
CREATE TABLE IF NOT EXISTS analysis_history (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    address     VARCHAR(500) NOT NULL,
    risk_score  INTEGER,
    result_json JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_history_user ON analysis_history(user_id);

-- Table de blacklist des refresh tokens (pour logout)
CREATE TABLE IF NOT EXISTS token_blacklist (
    id         SERIAL PRIMARY KEY,
    token_jti  VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(token_jti);
CREATE INDEX IF NOT EXISTS idx_token_blacklist_expires ON token_blacklist(expires_at);

-- Note: Créer l'admin initial via la commande:
-- python3 -c "from auth import hash_password; print(hash_password('VOTRE_MOT_DE_PASSE'))"
-- puis INSERT INTO users (email, name, password_hash, is_admin) VALUES ('admin@vigie-immo.ca', 'Admin', '<hash>', TRUE);
