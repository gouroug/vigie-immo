#!/usr/bin/env bash
# deploy.sh — Déploiement idempotent de Vigie-Immo sur porthos
# Usage : bash /var/www/vigie-immo/deploy/deploy.sh
set -euo pipefail

REPO_DIR="/var/www/vigie-immo"
BACKEND_DIR="$REPO_DIR/vigie-immo-backend"
FRONTEND_DIR="$REPO_DIR/frontend"
DEPLOY_DIR="$REPO_DIR/deploy"
SERVICE_NAME="vigie-immo"
SERVICE_FILE="$DEPLOY_DIR/vigie-immo.service"
NGINX_CONF="$DEPLOY_DIR/nginx-vigie-immo.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/$SERVICE_NAME"
NGINX_AVAILABLE="/etc/nginx/sites-available/$SERVICE_NAME"

ok()  { echo "  [OK] $*"; }
info(){ echo "==> $*"; }
warn(){ echo "  [!] $*"; }

# ---------------------------------------------------------------------------
# Étape 1 — Environnement Python
# ---------------------------------------------------------------------------
info "1/6 — Environnement Python + dépendances"
if [ ! -d "$BACKEND_DIR/venv" ]; then
    python3 -m venv "$BACKEND_DIR/venv"
    ok "venv créé"
fi
"$BACKEND_DIR/venv/bin/pip" install -q --upgrade pip
"$BACKEND_DIR/venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
ok "dépendances installées"

# Vérifier le fichier .env
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo ""
    warn "ATTENTION : $BACKEND_DIR/.env est absent."
    warn "Copiez $DEPLOY_DIR/.env.example vers $BACKEND_DIR/.env et renseignez les valeurs."
    echo ""
    exit 1
fi

# Avertissement si .gpkg manquant
GPKG_COUNT=$(find "$BACKEND_DIR/data" -name "*.gpkg" 2>/dev/null | wc -l)
if [ "$GPKG_COUNT" -eq 0 ]; then
    warn "Aucun fichier .gpkg trouvé dans $BACKEND_DIR/data/"
    warn "Transférez le fichier depuis athos : scp athos:/var/www/vigie-immo/vigie-immo-backend/data/*.gpkg $BACKEND_DIR/data/"
fi

# ---------------------------------------------------------------------------
# Étape 2 — Base de données
# ---------------------------------------------------------------------------
info "2/6 — Base de données PostgreSQL"
if ! psql -lqt | cut -d'|' -f1 | grep -qw vigie_immo; then
    createdb vigie_immo
    ok "base vigie_immo créée"
else
    ok "base vigie_immo existante"
fi
psql vigie_immo -f "$BACKEND_DIR/migrations/001_add_auth.sql" -q
ok "migration appliquée (idempotente)"

# ---------------------------------------------------------------------------
# Étape 3 — Admin initial
# ---------------------------------------------------------------------------
info "3/6 — Compte admin initial"
source "$BACKEND_DIR/.env"
ADMIN_COUNT=$(psql vigie_immo -tAc "SELECT COUNT(*) FROM users WHERE is_admin = true;" 2>/dev/null || echo "0")
if [ "$ADMIN_COUNT" -eq 0 ]; then
    "$BACKEND_DIR/venv/bin/python" "$BACKEND_DIR/app.py" --init-admin
    ok "admin créé ($ADMIN_EMAIL)"
else
    ok "admin existant — création ignorée"
fi

# ---------------------------------------------------------------------------
# Étape 4 — Systemd
# ---------------------------------------------------------------------------
info "4/6 — Service systemd $SERVICE_NAME"
sudo cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
ok "service démarré"

# ---------------------------------------------------------------------------
# Étape 5 — Frontend (build Vite)
# ---------------------------------------------------------------------------
info "5/6 — Frontend React (npm ci + build)"
cd "$FRONTEND_DIR"
npm ci --silent
npm run build --silent
ok "frontend compilé dans $FRONTEND_DIR/dist"

# ---------------------------------------------------------------------------
# Étape 6 — Nginx
# ---------------------------------------------------------------------------
info "6/6 — Configuration nginx"
sudo cp "$NGINX_CONF" "$NGINX_AVAILABLE"
if [ ! -L "$NGINX_ENABLED" ]; then
    sudo ln -s "$NGINX_AVAILABLE" "$NGINX_ENABLED"
fi
# Désactiver le site default si présent
if [ -L "/etc/nginx/sites-enabled/default" ]; then
    sudo rm "/etc/nginx/sites-enabled/default"
    warn "site 'default' nginx désactivé"
fi
sudo nginx -t
sudo systemctl reload nginx
ok "nginx rechargé"

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  Déploiement terminé"
echo "========================================"
sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -5
echo ""
echo "Vérifications :"
echo "  curl http://localhost/api/health"
echo "  journalctl -u $SERVICE_NAME -f"
