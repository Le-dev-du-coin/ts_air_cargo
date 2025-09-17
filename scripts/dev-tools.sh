#!/bin/bash

# Scripts utilitaires pour TS Air Cargo
# Usage: ./scripts/dev-tools.sh [commande]

case $1 in
    "logs")
        echo "📋 Logs Gunicorn (dernières 20 lignes):"
        tail -20 /var/www/ts_air_cargo/logs/gunicorn_supervisor.log
        echo -e "\n📋 Logs Celery (dernières 20 lignes):"
        tail -20 /var/www/ts_air_cargo/logs/celery.log
        ;;
    
    "status")
        echo "🔍 Status des services:"
        supervisorctl status
        echo -e "\n🌐 Test HTTPS:"
        curl -I https://ts-aircargo.com
        ;;
    
    "restart")
        echo "🔄 Redémarrage des services..."
        supervisorctl restart ts_air_cargo:
        echo "✅ Services redémarrés"
        ;;
    
    "backup")
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_DIR="/var/backups/ts_air_cargo"
        mkdir -p "$BACKUP_DIR"
        echo "💾 Sauvegarde de la base de données..."
        sudo -u postgres pg_dump ts_air_cargo > "$BACKUP_DIR/manual_backup_$TIMESTAMP.sql"
        echo "✅ Sauvegarde créée: $BACKUP_DIR/manual_backup_$TIMESTAMP.sql"
        ;;
    
    "migrate")
        cd /var/www/ts_air_cargo
        source venv/bin/activate
        echo "🗄️ Création des migrations..."
        python manage.py makemigrations
        echo "🗄️ Application des migrations..."
        python manage.py migrate
        echo "✅ Migrations terminées"
        ;;
    
    "shell")
        cd /var/www/ts_air_cargo
        source venv/bin/activate
        echo "🐍 Shell Django..."
        python manage.py shell
        ;;
    
    "collect")
        cd /var/www/ts_air_cargo
        source venv/bin/activate
        echo "📁 Collection des fichiers statiques..."
        python manage.py collectstatic --noinput
        echo "✅ Fichiers statiques collectés"
        ;;
    
    *)
        echo "🛠️ Scripts utilitaires TS Air Cargo"
        echo ""
        echo "Commandes disponibles:"
        echo "  logs     - Afficher les logs des services"
        echo "  status   - Status des services et test HTTPS"
        echo "  restart  - Redémarrer tous les services"
        echo "  backup   - Sauvegarde manuelle de la DB"
        echo "  migrate  - Créer et appliquer les migrations"
        echo "  shell    - Shell Django interactif"
        echo "  collect  - Collecter les fichiers statiques"
        echo ""
        echo "Usage: ./scripts/dev-tools.sh [commande]"
        ;;
esac
