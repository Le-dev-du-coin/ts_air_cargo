# 🚀 Guide de Déploiement - TS Air Cargo

## 📋 Aperçu

Ce guide décrit la stratégie de déploiement pour l'application TS Air Cargo en production.

## 🔧 Workflow de Développement Recommandé

### 1. Développement Local → Serveur Production

```bash
# 1. Développement en local
git checkout -b feature/nouvelle-fonctionnalite
# ... vos modifications ...
git add .
git commit -m "Nouvelle fonctionnalité"
git push origin feature/nouvelle-fonctionnalite

# 2. Merge vers master (après review)
git checkout master
git merge feature/nouvelle-fonctionnalite
git push origin master

# 3. Déploiement sur le serveur
ssh root@31.97.153.8
cd /var/www/ts_air_cargo
./scripts/deploy.sh
```

### 2. Déploiement Automatisé

Le script `scripts/deploy.sh` effectue automatiquement :

- ✅ Sauvegarde de la base de données
- ✅ Arrêt sécurisé des services
- ✅ Mise à jour du code depuis GitHub
- ✅ Installation des nouvelles dépendances
- ✅ Migrations de base de données
- ✅ Collection des fichiers statiques
- ✅ Tests de santé
- ✅ Rollback automatique en cas d'erreur

### 3. Gestion des Conflits

Si des modifications ont été faites directement sur le serveur :

```bash
# Sauvegarder les changements serveur
git stash push -m "Modifications serveur temporaires"

# Récupérer les changements depuis le repo
git pull origin master

# Appliquer les changements sauvegardés
git stash pop

# Résoudre les conflits si nécessaire
git add .
git commit -m "Résolution des conflits serveur/local"
git push origin master
```

## 🛠️ Scripts Utilitaires

### Script de Déploiement
```bash
./scripts/deploy.sh [branch]    # Déployer une branche (master par défaut)
```

### Scripts de Développement
```bash
./scripts/dev-tools.sh logs     # Afficher les logs
./scripts/dev-tools.sh status   # Status des services
./scripts/dev-tools.sh restart  # Redémarrer les services
./scripts/dev-tools.sh backup   # Sauvegarde manuelle
./scripts/dev-tools.sh migrate  # Migrations Django
./scripts/dev-tools.sh shell    # Shell Django
./scripts/dev-tools.sh collect  # Collecter les statiques
```

## 🔐 URLs de Production

- **Site principal :** https://ts-aircargo.com
- **Interface admin :** https://ts-aircargo.com/ts-cargo/secure-admin/
- **Admin credentials :** `+22370000000` / `AdminTSAir2024!`

## 📊 Monitoring

### Logs
```bash
tail -f /var/www/ts_air_cargo/logs/gunicorn_supervisor.log
tail -f /var/www/ts_air_cargo/logs/celery.log
tail -f /var/www/ts_air_cargo/logs/nginx-access.log
tail -f /var/www/ts_air_cargo/logs/nginx-error.log
```

### Services
```bash
supervisorctl status
systemctl status nginx
systemctl status postgresql
systemctl status redis-server
```

### Base de données
```bash
sudo -u postgres psql ts_air_cargo
```

## 🔄 Sauvegardes

### Automatiques
- Les sauvegardes DB sont créées automatiquement avant chaque déploiement
- Localisation : `/var/backups/ts_air_cargo/`
- Rétention : 7 jours

### Manuelles
```bash
./scripts/dev-tools.sh backup
```

### Restauration
```bash
sudo -u postgres psql ts_air_cargo < /var/backups/ts_air_cargo/backup_file.sql
```

## 🚨 Rollback d'Urgence

En cas de problème critique :

```bash
cd /var/www/ts_air_cargo
git log --oneline -5  # Voir les derniers commits
git checkout COMMIT_HASH_PRECEDENT
supervisorctl restart ts_air_cargo:ts_air_cargo_gunicorn
```

## 📱 Configuration Email (Hostinger SMTP)

Variables d'environnement dans `.env` :
```bash
EMAIL_HOST=smtp.hostinger.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@ts-aircargo.com
EMAIL_HOST_PASSWORD=your-hostinger-password
```

## 🔒 SSL/HTTPS

- Certificat Let's Encrypt automatiquement renouvelé
- Redirection HTTP → HTTPS active
- HSTS activé pour la sécurité

## ⚠️ Points d'Attention

1. **Toujours tester en local** avant de déployer
2. **Vérifier les migrations** avant le déploiement
3. **Sauvegarder** avant les modifications importantes
4. **Surveiller les logs** après déploiement
5. **Tester l'interface admin** après mise à jour

## 📞 Support

En cas de problème, vérifier dans l'ordre :

1. Logs des services (`./scripts/dev-tools.sh logs`)
2. Status des services (`./scripts/dev-tools.sh status`)
3. Connectivité HTTPS (`curl -I https://ts-aircargo.com`)
4. Base de données (connexion et intégrité)

---

**🏆 Application déployée avec succès sur ts-aircargo.com**
