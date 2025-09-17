#!/bin/bash

# Script de déploiement TS Air Cargo
# Usage: ./scripts/deploy.sh [branch]

set -e

BRANCH=${1:-master}
PROJECT_DIR="/var/www/ts_air_cargo"
BACKUP_DIR="/var/backups/ts_air_cargo"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🚀 Démarrage du déploiement de TS Air Cargo..."
echo "📂 Répertoire: $PROJECT_DIR"
echo "🌿 Branche: $BRANCH"

# Fonction de sauvegarde
backup_database() {
    echo "💾 Sauvegarde de la base de données..."
    mkdir -p "$BACKUP_DIR"
    sudo -u postgres pg_dump ts_air_cargo > "$BACKUP_DIR/ts_air_cargo_$TIMESTAMP.sql"
    echo "✅ Base de données sauvegardée: $BACKUP_DIR/ts_air_cargo_$TIMESTAMP.sql"
}

# Fonction de rollback
rollback() {
    echo "❌ Erreur détectée! Rollback en cours..."
    git checkout HEAD~1
    supervisorctl restart ts_air_cargo:ts_air_cargo_gunicorn
    echo "⚠️ Rollback effectué vers le commit précédent"
    exit 1
}

# Trap pour rollback automatique en cas d'erreur
trap rollback ERR

cd "$PROJECT_DIR"

# Sauvegarde avant déploiement
backup_database

# Arrêt des services
echo "⏸️ Arrêt temporaire des services..."
supervisorctl stop ts_air_cargo:ts_air_cargo_gunicorn

# Mise à jour du code
echo "📥 Récupération des modifications..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# Activation de l'environnement virtuel
echo "🐍 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installation/mise à jour des dépendances
echo "📦 Mise à jour des dépendances..."
pip install -r requirements.txt --upgrade

# Migrations de base de données
echo "🗄️ Application des migrations..."
python manage.py migrate --noinput

# Collection des fichiers statiques
echo "📁 Collection des fichiers statiques..."
python manage.py collectstatic --noinput --clear

# Test de configuration
echo "🔧 Vérification de la configuration..."
python manage.py check --deploy

# Redémarrage des services
echo "🔄 Redémarrage des services..."
supervisorctl start ts_air_cargo:ts_air_cargo_gunicorn
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
