# Déploiement Vigie-Immo sur Porthos

## Architecture

```
Internet → nginx (port 80)
              ├── /api/*  → gunicorn (127.0.0.1:5000) → Flask
              └── /*      → frontend/dist/ (SPA statique)
```

## Prérequis sur porthos

- Ubuntu 24.04
- Python 3.12 + `python3-venv`
- Node.js ≥ 18 + npm
- PostgreSQL 18 (peer auth pour l'utilisateur gouroug)
- nginx
- sudo pour gouroug (commandes systemd et nginx)

## 1. Cloner le dépôt

```bash
sudo mkdir -p /var/www/vigie-immo
sudo chown gouroug:gouroug /var/www/vigie-immo
cd /var/www/vigie-immo
git clone git@github.com:OWNER/REPO.git .
```

## 2. Créer le fichier `.env`

```bash
cp deploy/.env.example vigie-immo-backend/.env
nano vigie-immo-backend/.env
```

Valeurs à renseigner :
- `JWT_SECRET` — générer avec `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — compte admin initial (≥ 12 caractères)
- `VIGIE_DB_DSN` — laisser `dbname=vigie_immo` si peer auth PostgreSQL
- `ALLOWED_ORIGINS` — laisser vide (même domaine via nginx)

## 3. Configurer nginx

Remplacer `PORTHOS_DOMAIN` par le vrai nom de domaine ou l'IP :

```bash
sed -i 's/PORTHOS_DOMAIN/mon.domaine.ca/' /var/www/vigie-immo/deploy/nginx-vigie-immo.conf
```

## 4. Transférer les fichiers de données depuis athos

Les fichiers `.gpkg` (données géospatiales, ~12,5 Mo) ne sont pas dans git :

```bash
scp athos:/var/www/vigie-immo/vigie-immo-backend/data/*.gpkg \
    /var/www/vigie-immo/vigie-immo-backend/data/
```

Créer le dossier si absent :
```bash
mkdir -p /var/www/vigie-immo/vigie-immo-backend/data
```

## 5. (Optionnel) Migrer la base de données depuis athos

```bash
# Sur athos
pg_dump vigie_immo | gzip > /tmp/vigie_immo.sql.gz

# Transfert
scp athos:/tmp/vigie_immo.sql.gz /tmp/

# Sur porthos — restaurer après avoir créé la DB (deploy.sh le fait)
createdb vigie_immo
gunzip -c /tmp/vigie_immo.sql.gz | psql vigie_immo
```

Si la migration est faite avant `deploy.sh`, le script détectera qu'un admin existe
et ne recrééra pas le compte.

## 6. Lancer le déploiement

```bash
bash /var/www/vigie-immo/deploy/deploy.sh
```

Le script est idempotent : il peut être relancé sans risque.

## 7. Vérification

```bash
sudo systemctl status vigie-immo
curl http://localhost/api/health
# Navigateur : http://PORTHOS_DOMAIN/ → page /login
journalctl -u vigie-immo -f
```

## Déploiements suivants

```bash
cd /var/www/vigie-immo
git pull
bash deploy/deploy.sh
```

## HTTPS (Certbot — étape future)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d mon.domaine.ca
```

Certbot modifie la config nginx pour rediriger HTTP → HTTPS automatiquement.

## Structure des fichiers de déploiement

```
deploy/
├── gunicorn.conf.py      # Configuration gunicorn (workers, timeout, logs)
├── vigie-immo.service    # Unité systemd
├── nginx-vigie-immo.conf # Config nginx (proxy + SPA routing)
├── .env.example          # Template variables d'environnement
├── deploy.sh             # Script de déploiement idempotent
└── README.md             # Ce fichier
```
