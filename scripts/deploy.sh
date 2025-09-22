#!/bin/bash

# Script de déploiement TS Air Cargo
# Usage: ./scripts/deploy.sh [branch]

set -Eeuo pipefail

BRANCH=${1:-master}
PROJECT_DIR="/var/www/ts_air_cargo"
BACKUP_DIR="/var/backups/ts_air_cargo"
VENV_PATH="/var/www/ts_air_cargo/venv"
PYTHON_BIN="$VENV_PATH/bin/python"
PIP_BIN="$VENV_PATH/bin/pip"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🚀 Démarrage du déploiement de TS Air Cargo..."
echo "📂 Répertoire: $PROJECT_DIR"
echo "🌿 Branche: $BRANCH"
echo "🐍 Virtualenv: $VENV_PATH"

# Fonction de sauvegarde
backup_database() {
    echo "💾 Sauvegarde de la base de données..."
    mkdir -p "$BACKUP_DIR"
    sudo -u postgres pg_dump ts_air_cargo > "$BACKUP_DIR/ts_air_cargo_$TIMESTAMP.sql"
    echo "✅ Base de données sauvegardée: $BACKUP_DIR/ts_air_cargo_$TIMESTAMP.sql"
}

# Fonction de rollback (sans modifier l'historique Git)
rollback() {
    echo "❌ Erreur détectée! Rollback services en cours..."
    # Tenter de relancer les services avec la dernière version stable
    supervisorctl restart ts_air_cargo:ts_air_cargo_gunicorn || true
    supervisorctl restart ts_air_cargo:ts_air_cargo_celery || true
    echo "⚠️ Services relancés avec l'état précédent (si disponible)"
    exit 1
}

# Trap pour rollback automatique en cas d'erreur
trap rollback ERR

cd "$PROJECT_DIR"

# Sauvegarde avant déploiement
backup_database

# Arrêt des services
echo "⏸️ Arrêt temporaire des services..."
supervisorctl stop ts_air_cargo:ts_air_cargo_celery || true
supervisorctl stop ts_air_cargo:ts_air_cargo_gunicorn || true

# Mise à jour du code
echo "📥 Récupération des modifications..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# Création/activation de l'environnement virtuel (PEP 668 compliant)
echo "🐍 Préparation de l'environnement virtuel..."
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

echo "📦 Mise à jour des dépendances..."
"$PIP_BIN" install --upgrade pip
"$PIP_BIN" install -r requirements.txt

# Migrations de base de données
echo "🗄️ Application des migrations..."
"$PYTHON_BIN" manage.py migrate --noinput

# Collection des fichiers statiques
echo "📁 Collection des fichiers statiques..."
"$PYTHON_BIN" manage.py collectstatic --noinput --clear

# Test de configuration
echo "🔧 Vérification de la configuration..."
"$PYTHON_BIN" manage.py check --deploy

# Redémarrage des services
echo "🔄 Redémarrage des services..."
supervisorctl restart ts_air_cargo:ts_air_cargo_gunicorn
supervisorctl restart ts_air_cargo:ts_air_cargo_celery

# Test de santé
echo "🏥 Test de santé de l'application..."
sleep 5
if curl -f -s https://ts-aircargo.com/ > /dev/null; then
    echo "✅ Application déployée avec succès!"
    echo "🌐 Accessible à: https://ts-aircargo.com/"
    echo "🔐 Admin: https://ts-aircargo.com/ts-cargo/secure-admin/"
else
    echo "❌ Test de santé échoué!"
    rollback
fi

# Nettoyage des anciennes sauvegardes (garde les 7 dernières)
find "$BACKUP_DIR" -name "ts_air_cargo_*.sql" -mtime +7 -delete 2>/dev/null || true

echo "🎉 Déploiement terminé avec succès!"
