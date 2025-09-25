# 🚀 DEVBOOK - Gestion Asynchrone des Colis & Amélioration des Lots

## 📋 Vue d'ensemble

**Objectif principal :** Transformer la création/modification de colis en processus asynchrone pour améliorer drastiquement les performances dans un environnement de connexion lente.

**Impact attendu :** 
- ⚡ Temps de réponse : 15 minutes → 0.2 secondes
- 📈 Productivité agent : +400%
- 🎯 Capacité de traitement : 4 colis/heure → 70+ colis/heure

---

## 🎯 PHASE 1 : Modèles et Infrastructure

### 1.1 Nouveau modèle pour les tâches de colis

```python
# agent_chine_app/models.py

class ColisCreationTask(models.Model):
    """
    Tâche de création/modification de colis en arrière-plan
    """
    TASK_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En traitement'),
        ('image_uploading', 'Upload image...'),
        ('price_calculating', 'Calcul prix...'),
        ('notification_sending', 'Envoi notification...'),
        ('completed', 'Finalisé'),
        ('failed', 'Échec'),
        ('failed_retry', 'Échec - retry programmé'),
        ('failed_final', 'Échec définitif'),
        ('cancelled', 'Annulé'),
    ]
    
    OPERATION_CHOICES = [
        ('create', 'Création'),
        ('update', 'Modification'),
    ]
    
    # Identification de la tâche
    task_id = models.CharField(max_length=50, unique=True)
    celery_task_id = models.CharField(max_length=100, null=True, blank=True)
    operation_type = models.CharField(max_length=10, choices=OPERATION_CHOICES)
    
    # État de la tâche
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='pending')
    current_step = models.CharField(max_length=100, blank=True)
    progress_percentage = models.IntegerField(default=0)
    
    # Données du colis (JSON)
    colis_data = models.JSONField(help_text="Données du formulaire colis")
    original_image_path = models.CharField(max_length=500, blank=True)
    
    # Relations
    colis = models.ForeignKey('Colis', on_delete=models.CASCADE, null=True, blank=True)
    lot = models.ForeignKey('Lot', on_delete=models.CASCADE)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Gestion des erreurs
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Tâche de Colis"
        verbose_name_plural = "Tâches de Colis"
    
    def __str__(self):
        return f"Tâche {self.task_id} - {self.status}"
    
    def can_retry(self):
        return self.retry_count < self.max_retries and self.status in ['failed', 'failed_retry']
    
    def get_estimated_completion_time(self):
        """Estimation du temps restant basée sur l'historique"""
        # Logique d'estimation basée sur les tâches similaires
        pass
```

### 1.2 Extension du modèle Lot

```python
# agent_chine_app/models.py - Modification du modèle Lot existant

class Lot(models.Model):
    # Champs existants...
    
    # NOUVEAU CHAMP
    type_lot = models.CharField(
        max_length=20,
        choices=[
            ('cargo', 'Cargo'),
            ('express', 'Express'),
            ('bateau', 'Bateau'),
        ],
        default='cargo',
        help_text="Type de transport principal du lot"
    )
    
    def save(self, *args, **kwargs):
        if not self.numero_lot:
            # NOUVELLE LOGIQUE avec type
            date_str = timezone.now().strftime('%Y%m%d')
            type_prefix = self.type_lot.upper()
            
            count = Lot.objects.filter(
                numero_lot__startswith=f"{type_prefix}-{date_str}"
            ).count() + 1
            
            self.numero_lot = f"{type_prefix}-{date_str}{count:03d}"
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Lot {self.numero_lot} - {self.statut}"
```

---

## 🎯 PHASE 2 : Tâches Celery

### 2.1 Tâche principale de création de colis

```python
# agent_chine_app/tasks.py (nouveau fichier)

from celery import shared_task
from django.core.files.base import ContentFile
import base64
import json
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def create_colis_async(self, task_id):
    """
    Tâche principale de création asynchrone de colis
    """
    from .models import ColisCreationTask, Colis, Client
    from notifications_app.tasks import notify_colis_created
    
    try:
        # Récupérer la tâche
        task = ColisCreationTask.objects.get(task_id=task_id)
        task.status = 'processing'
        task.celery_task_id = self.request.id
        task.started_at = timezone.now()
        task.current_step = "Démarrage de la création"
        task.progress_percentage = 10
        task.save()
        
        # Étape 1: Validation des données
        task.current_step = "Validation des données"
        task.progress_percentage = 20
        task.save()
        
        colis_data = task.colis_data
        client = Client.objects.get(id=colis_data['client_id'])
        
        # Étape 2: Traitement de l'image
        task.current_step = "Traitement de l'image"
        task.status = 'image_uploading'
        task.progress_percentage = 40
        task.save()
        
        image_file = None
        if task.original_image_path:
            # Traiter l'image stockée temporairement
            image_file = process_temp_image(task.original_image_path)
        
        # Étape 3: Création du colis
        task.current_step = "Création du colis en base"
        task.progress_percentage = 60
        task.save()
        
        colis = Colis.objects.create(
            client=client,
            lot=task.lot,
            type_transport=colis_data['type_transport'],
            image=image_file,
            longueur=float(colis_data.get('longueur', 0)),
            largeur=float(colis_data.get('largeur', 0)),
            hauteur=float(colis_data.get('hauteur', 0)),
            poids=float(colis_data.get('poids', 0)),
            mode_paiement=colis_data.get('mode_paiement', 'non_paye'),
            statut=colis_data.get('statut', 'receptionne_chine'),
            description=colis_data.get('description', '')
        )
        
        task.colis = colis
        
        # Étape 4: Calcul du prix
        task.current_step = "Calcul du prix automatique"
        task.status = 'price_calculating'
        task.progress_percentage = 80
        task.save()
        
        # Le prix est calculé automatiquement dans Colis.save()
        colis.refresh_from_db()
        
        # Étape 5: Envoi des notifications
        task.current_step = "Envoi des notifications"
        task.status = 'notification_sending'
        task.progress_percentage = 90
        task.save()
        
        notify_colis_created.delay(colis.id, initiated_by_id=task.initiated_by.id)
        
        # Finalisation
        task.status = 'completed'
        task.current_step = "Terminé avec succès"
        task.progress_percentage = 100
        task.completed_at = timezone.now()
        task.save()
        
        logger.info(f"✅ Colis {colis.numero_suivi} créé avec succès via tâche {task_id}")
        
        return {
            'success': True,
            'colis_id': colis.id,
            'numero_suivi': colis.numero_suivi,
            'task_id': task_id
        }
        
    except Exception as e:
        # Gestion des erreurs avec retry
        error_msg = f"Erreur création colis: {str(e)}"
        logger.error(f"❌ Tâche {task_id}: {error_msg}")
        
        try:
            task = ColisCreationTask.objects.get(task_id=task_id)
            task.status = 'failed_retry' if task.can_retry() else 'failed_final'
            task.error_message = error_msg
            task.retry_count += 1
            
            if task.can_retry():
                task.next_retry_at = timezone.now() + timezone.timedelta(minutes=5)
                logger.info(f"🔄 Retry programmé pour tâche {task_id} dans 5 minutes")
            
            task.save()
        except:
            pass
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)  # Retry dans 5 minutes
        
        return {
            'success': False,
            'error': error_msg,
            'task_id': task_id
        }


def process_temp_image(temp_path):
    """
    Traiter une image temporaire et la préparer pour le modèle
    """
    # Logique de compression, redimensionnement, validation
    # Retourner un objet File Django
    pass
```

### 2.2 Tâche de modification de colis

```python
@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def update_colis_async(self, task_id):
    """
    Tâche principale de modification asynchrone de colis
    """
    # Logique similaire à create_colis_async mais pour modification
    pass
```

---

## 🎯 PHASE 3 : Vues et Interface

### 3.1 Vue de création de colis asynchrone

```python
# agent_chine_app/views.py - Remplacement de colis_create_view

@agent_chine_required
def colis_create_async_view(request, lot_id):
    """
    Création asynchrone d'un colis - Réponse instantanée
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    if lot.statut != 'ouvert':
        messages.error(request, "Impossible d'ajouter des colis à un lot fermé.")
        return redirect('agent_chine:lot_detail', lot_id=lot_id)
    
    if request.method == 'POST':
        try:
            # Validation rapide des données essentielles
            client_id = request.POST.get('client')
            type_transport = request.POST.get('type_transport')
            image = request.FILES.get('image')
            
            if not client_id or not type_transport:
                messages.error(request, "❌ Données obligatoires manquantes.")
                raise ValueError("Validation échouée")
            
            # Stockage temporaire de l'image si fournie
            temp_image_path = None
            if image:
                temp_image_path = store_temp_image(image)
            
            # Génération de l'ID de tâche
            task_id = f"colis_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Création de la tâche
            creation_task = ColisCreationTask.objects.create(
                task_id=task_id,
                operation_type='create',
                lot=lot,
                initiated_by=request.user,
                colis_data={
                    'client_id': client_id,
                    'type_transport': type_transport,
                    'longueur': request.POST.get('longueur', 0),
                    'largeur': request.POST.get('largeur', 0),
                    'hauteur': request.POST.get('hauteur', 0),
                    'poids': request.POST.get('poids', 0),
                    'mode_paiement': request.POST.get('mode_paiement', 'non_paye'),
                    'statut': request.POST.get('statut', 'receptionne_chine'),
                    'description': request.POST.get('description', '')
                },
                original_image_path=temp_image_path or ''
            )
            
            # Lancement de la tâche Celery
            from .tasks import create_colis_async
            create_colis_async.delay(task_id)
            
            # Réponse instantanée à l'agent
            messages.success(
                request, 
                f"✅ Colis ajouté à la file de traitement ! "
                f"ID de tâche: {task_id}. "
                f"Vérifiez le tableau de bord pour le suivi."
            )
            
            return redirect('agent_chine:lot_detail', lot_id=lot_id)
            
        except Exception as e:
            messages.error(request, f"❌ Erreur: {str(e)}")
    
    # Récupérer tous les clients pour la sélection
    clients = Client.objects.all().order_by('user__first_name', 'user__last_name')
    
    context = {
        'lot': lot,
        'clients': clients,
        'title': f'Nouveau Colis - Lot {lot.numero_lot}',
        'submit_text': 'Ajouter à la file',
        'is_async': True
    }
    return render(request, 'agent_chine_app/colis_form_async.html', context)


def store_temp_image(image_file):
    """
    Stocker temporairement une image uploadée
    """
    import tempfile
    import os
    
    # Créer un fichier temporaire
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_filename = f"temp_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{image_file.name}"
    temp_path = os.path.join(temp_dir, temp_filename)
    
    with open(temp_path, 'wb') as temp_file:
        for chunk in image_file.chunks():
            temp_file.write(chunk)
    
    return temp_path
```

### 3.2 Vue de création de lot avec type

```python
@agent_chine_required
def lot_create_view(request):
    """
    Création d'un nouveau lot avec type
    """
    if request.method == 'POST':
        try:
            type_lot = request.POST.get('type_lot', 'cargo')
            
            # Créer le lot avec type
            lot = Lot.objects.create(
                agent_createur=request.user,
                type_lot=type_lot,
                statut='ouvert'
            )
            
            messages.success(request, f"✅ Lot {lot.numero_lot} créé avec succès.")
            return redirect('agent_chine:lot_detail', lot_id=lot.id)
            
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la création du lot: {str(e)}")
    
    context = {
        'title': 'Nouveau Lot',
        'submit_text': 'Créer',
        'transport_choices': Colis.TRANSPORT_CHOICES,
    }
    return render(request, 'agent_chine_app/lot_form_with_type.html', context)
```

### 3.3 Dashboard de suivi des tâches

```python
@agent_chine_required
def colis_tasks_dashboard(request):
    """
    Dashboard de suivi des tâches de colis pour l'agent
    """
    # Tâches actives (en cours)
    active_tasks = ColisCreationTask.objects.filter(
        initiated_by=request.user,
        status__in=['pending', 'processing', 'image_uploading', 'price_calculating', 'notification_sending']
    ).order_by('-created_at')
    
    # Tâches en échec pouvant être retentées
    failed_tasks = ColisCreationTask.objects.filter(
        initiated_by=request.user,
        status__in=['failed', 'failed_retry']
    ).order_by('-created_at')[:10]
    
    # Tâches complétées récemment
    completed_tasks = ColisCreationTask.objects.filter(
        initiated_by=request.user,
        status='completed',
        completed_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).order_by('-completed_at')[:20]
    
    # Statistiques du jour
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    stats = {
        'total_today': ColisCreationTask.objects.filter(
            initiated_by=request.user,
            created_at__gte=today_start
        ).count(),
        'completed_today': ColisCreationTask.objects.filter(
            initiated_by=request.user,
            status='completed',
            completed_at__gte=today_start
        ).count(),
        'failed_today': ColisCreationTask.objects.filter(
            initiated_by=request.user,
            status__in=['failed', 'failed_final'],
            created_at__gte=today_start
        ).count(),
        'active_now': active_tasks.count()
    }
    
    # Calcul du taux de succès
    if stats['total_today'] > 0:
        stats['success_rate'] = round((stats['completed_today'] / stats['total_today']) * 100, 1)
    else:
        stats['success_rate'] = 0
    
    context = {
        'active_tasks': active_tasks,
        'failed_tasks': failed_tasks,
        'completed_tasks': completed_tasks,
        'stats': stats,
    }
    return render(request, 'agent_chine_app/colis_tasks_dashboard.html', context)
```

---

## 🎯 PHASE 4 : Gestion des Échecs

### 4.1 Vues de gestion des échecs

```python
@agent_chine_required
def retry_failed_task(request, task_id):
    """
    Relancer manuellement une tâche échouée
    """
    task = get_object_or_404(ColisCreationTask, task_id=task_id, initiated_by=request.user)
    
    if not task.can_retry():
        messages.error(request, "Cette tâche ne peut plus être relancée.")
        return redirect('agent_chine:colis_tasks_dashboard')
    
    if request.method == 'POST':
        # Permettre à l'agent de modifier certaines données avant retry
        updated_data = task.colis_data.copy()
        
        # Mise à jour des données si fournies
        for field in ['client_id', 'type_transport', 'poids', 'longueur', 'largeur', 'hauteur']:
            if request.POST.get(field):
                updated_data[field] = request.POST.get(field)
        
        task.colis_data = updated_data
        task.status = 'pending'
        task.error_message = ''
        task.current_step = 'Prêt pour retry'
        task.save()
        
        # Relancer la tâche
        from .tasks import create_colis_async
        create_colis_async.delay(task_id)
        
        messages.success(request, f"✅ Tâche {task_id} relancée avec succès.")
        return redirect('agent_chine:colis_tasks_dashboard')
    
    context = {
        'task': task,
        'colis_data': task.colis_data,
    }
    return render(request, 'agent_chine_app/retry_task.html', context)


@agent_chine_required
def cancel_task(request, task_id):
    """
    Annuler une tâche en cours ou échouée
    """
    task = get_object_or_404(ColisCreationTask, task_id=task_id, initiated_by=request.user)
    
    if task.status == 'completed':
        messages.error(request, "Impossible d'annuler une tâche terminée.")
        return redirect('agent_chine:colis_tasks_dashboard')
    
    if request.method == 'POST':
        # Annuler la tâche Celery si en cours
        if task.celery_task_id:
            from celery import current_app
            current_app.control.revoke(task.celery_task_id, terminate=True)
        
        task.status = 'cancelled'
        task.current_step = 'Annulé par l\'agent'
        task.save()
        
        # Nettoyer les fichiers temporaires
        if task.original_image_path and os.path.exists(task.original_image_path):
            os.remove(task.original_image_path)
        
        messages.success(request, f"✅ Tâche {task_id} annulée.")
        return redirect('agent_chine:colis_tasks_dashboard')
    
    context = {'task': task}
    return render(request, 'agent_chine_app/cancel_task.html', context)
```

---

## 🎯 PHASE 5 : Templates et Interface

### 5.1 Template du dashboard des tâches

```html
<!-- agent_chine_app/templates/agent_chine_app/colis_tasks_dashboard.html -->

{% extends 'components/base_agent.html' %}

{% block title %}Dashboard des Tâches - TS Air Cargo{% endblock %}
{% block page_title %}Suivi des Tâches de Colis{% endblock %}

{% block content %}
<!-- Statistiques du jour -->
<div class="row mb-4">
    <div class="col-md-3">
        <div class="stat-card">
            <h3 class="stat-value">{{ stats.total_today }}</h3>
            <p class="stat-label">Tâches créées aujourd'hui</p>
        </div>
    </div>
    <div class="col-md-3">
        <div class="stat-card">
            <h3 class="stat-value text-success">{{ stats.completed_today }}</h3>
            <p class="stat-label">Colis finalisés</p>
        </div>
    </div>
    <div class="col-md-3">
        <div class="stat-card">
            <h3 class="stat-value text-primary">{{ stats.active_now }}</h3>
            <p class="stat-label">En cours de traitement</p>
        </div>
    </div>
    <div class="col-md-3">
        <div class="stat-card">
            <h3 class="stat-value">{{ stats.success_rate }}%</h3>
            <p class="stat-label">Taux de succès</p>
        </div>
    </div>
</div>

<!-- Tâches en cours -->
{% if active_tasks %}
<div class="modern-card mb-4">
    <div class="modern-card-header">
        <h5 class="modern-card-title">
            <i class="bi bi-clock"></i>
            Tâches en cours ({{ active_tasks.count }})
        </h5>
    </div>
    <div class="modern-card-body">
        {% for task in active_tasks %}
        <div class="task-item border-bottom pb-3 mb-3">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h6 class="mb-1">{{ task.task_id }}</h6>
                    <p class="text-muted small mb-1">{{ task.current_step }}</p>
                    <div class="progress mb-2" style="height: 6px;">
                        <div class="progress-bar" role="progressbar" 
                             style="width: {{ task.progress_percentage }}%"
                             aria-valuenow="{{ task.progress_percentage }}" 
                             aria-valuemin="0" aria-valuemax="100">
                        </div>
                    </div>
                    <small class="text-muted">
                        Créé il y a {{ task.created_at|timesince }}
                        {% if task.colis_data.client_name %}
                        - Client: {{ task.colis_data.client_name }}
                        {% endif %}
                    </small>
                </div>
                <span class="badge bg-primary">{{ task.get_status_display }}</span>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

<!-- Tâches en échec -->
{% if failed_tasks %}
<div class="modern-card mb-4">
    <div class="modern-card-header">
        <h5 class="modern-card-title">
            <i class="bi bi-exclamation-triangle text-warning"></i>
            Tâches en échec ({{ failed_tasks.count }})
        </h5>
    </div>
    <div class="modern-card-body">
        {% for task in failed_tasks %}
        <div class="task-item border-bottom pb-3 mb-3">
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <h6 class="mb-1">{{ task.task_id }}</h6>
                    <p class="text-danger small mb-2">
                        <i class="bi bi-x-circle"></i>
                        {{ task.error_message|truncatechars:80 }}
                    </p>
                    <small class="text-muted">
                        Tentative {{ task.retry_count }}/{{ task.max_retries }}
                        {% if task.next_retry_at %}
                        - Prochain retry: {{ task.next_retry_at|timeuntil }}
                        {% endif %}
                    </small>
                </div>
                <div class="d-flex gap-2">
                    {% if task.can_retry %}
                    <a href="{% url 'agent_chine:retry_task' task.task_id %}" 
                       class="btn btn-sm btn-warning">
                        <i class="bi bi-arrow-clockwise"></i>
                        Retry
                    </a>
                    {% endif %}
                    <a href="{% url 'agent_chine:cancel_task' task.task_id %}" 
                       class="btn btn-sm btn-outline-danger">
                        <i class="bi bi-x"></i>
                        Annuler
                    </a>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

<!-- Tâches complétées récentes -->
{% if completed_tasks %}
<div class="modern-card">
    <div class="modern-card-header">
        <h5 class="modern-card-title">
            <i class="bi bi-check-circle text-success"></i>
            Complétées récemment (24h)
        </h5>
    </div>
    <div class="modern-card-body">
        {% for task in completed_tasks %}
        <div class="task-item border-bottom pb-2 mb-2">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <span class="fw-bold">{{ task.colis.numero_suivi }}</span>
                    <small class="text-muted ms-2">
                        {{ task.completed_at|timesince }} ago
                    </small>
                </div>
                <a href="{% url 'agent_chine:colis_detail' task.colis.id %}" 
                   class="btn btn-sm btn-outline-primary">
                    <i class="bi bi-eye"></i>
                    Voir
                </a>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

<!-- Auto-refresh -->
<script>
// Rafraîchir la page toutes les 30 secondes pour voir les mises à jour
setTimeout(function() {
    location.reload();
}, 30000);
</script>
{% endblock %}
```

---

## 🎯 PHASE 6 : Migrations et URLs

### 6.1 Migration pour ColisCreationTask

```python
# agent_chine_app/migrations/XXXX_add_async_colis_management.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('agent_chine_app', 'XXXX_previous_migration'),
    ]
    
    operations = [
        migrations.CreateModel(
            name='ColisCreationTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_id', models.CharField(max_length=50, unique=True)),
                ('celery_task_id', models.CharField(blank=True, max_length=100, null=True)),
                ('operation_type', models.CharField(choices=[('create', 'Création'), ('update', 'Modification')], max_length=10)),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('processing', 'En traitement'), ('image_uploading', 'Upload image...'), ('price_calculating', 'Calcul prix...'), ('notification_sending', 'Envoi notification...'), ('completed', 'Finalisé'), ('failed', 'Échec'), ('failed_retry', 'Échec - retry programmé'), ('failed_final', 'Échec définitif'), ('cancelled', 'Annulé')], default='pending', max_length=20)),
                ('current_step', models.CharField(blank=True, max_length=100)),
                ('progress_percentage', models.IntegerField(default=0)),
                ('colis_data', models.JSONField(help_text='Données du formulaire colis')),
                ('original_image_path', models.CharField(blank=True, max_length=500)),
                ('error_message', models.TextField(blank=True)),
                ('retry_count', models.IntegerField(default=0)),
                ('max_retries', models.IntegerField(default=3)),
                ('next_retry_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('colis', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='agent_chine_app.colis')),
                ('initiated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='authentication.customuser')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agent_chine_app.lot')),
            ],
            options={
                'verbose_name': 'Tâche de Colis',
                'verbose_name_plural': 'Tâches de Colis',
                'ordering': ['-created_at'],
            },
        ),
    ]
```

### 6.2 Migration pour le champ type_lot

```python
# agent_chine_app/migrations/XXXX_add_type_lot.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('agent_chine_app', 'XXXX_add_async_colis_management'),
    ]
    
    operations = [
        migrations.AddField(
            model_name='lot',
            name='type_lot',
            field=models.CharField(choices=[('cargo', 'Cargo'), ('express', 'Express'), ('bateau', 'Bateau')], default='cargo', help_text='Type de transport principal du lot', max_length=20),
        ),
    ]
```

### 6.3 URLs

```python
# agent_chine_app/urls.py - Ajouts

urlpatterns = [
    # URLs existantes...
    
    # Gestion asynchrone des colis
    path('lots/<int:lot_id>/colis/create-async/', views.colis_create_async_view, name='colis_create_async'),
    path('colis/<int:colis_id>/edit-async/', views.colis_edit_async_view, name='colis_edit_async'),
    
    # Dashboard et gestion des tâches
    path('colis/tasks/', views.colis_tasks_dashboard, name='colis_tasks_dashboard'),
    path('colis/tasks/<str:task_id>/retry/', views.retry_failed_task, name='retry_task'),
    path('colis/tasks/<str:task_id>/cancel/', views.cancel_task, name='cancel_task'),
    
    # API pour le suivi en temps réel
    path('api/tasks/<str:task_id>/status/', views.task_status_api, name='task_status_api'),
    path('api/tasks/active/', views.active_tasks_api, name='active_tasks_api'),
]
```

---

## 🎯 PHASE 7 : Tests et Validation

### 7.1 Tests unitaires

```python
# agent_chine_app/tests/test_async_colis.py

from django.test import TestCase
from unittest.mock import patch, MagicMock
from agent_chine_app.models import ColisCreationTask, Lot, Client
from agent_chine_app.tasks import create_colis_async

class AsyncColisCreationTest(TestCase):
    def setUp(self):
        # Setup test data
        pass
    
    def test_create_colis_async_success(self):
        """Test création réussie d'un colis en asynchrone"""
        pass
    
    def test_create_colis_async_retry_on_failure(self):
        """Test retry automatique en cas d'échec"""
        pass
    
    def test_task_status_tracking(self):
        """Test suivi de l'état des tâches"""
        pass
```

---

## 🎯 PHASE 8 : Déploiement et Monitoring

### 8.1 Configuration Celery

```python
# ts_air_cargo/celery.py - Ajouts

# Configuration pour les tâches de colis
CELERY_TASK_ROUTES = {
    'agent_chine_app.tasks.create_colis_async': {
        'queue': 'colis_creation',
        'routing_key': 'colis.create'
    },
    'agent_chine_app.tasks.update_colis_async': {
        'queue': 'colis_creation', 
        'routing_key': 'colis.update'
    },
}

# Limits et timeouts
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes max par tâche
CELERY_TASK_SOFT_TIME_LIMIT = 480  # Warning à 8 minutes
```

### 8.2 Monitoring et alertes

```python
# agent_chine_app/management/commands/monitor_colis_tasks.py

from django.core.management.base import BaseCommand
from agent_chine_app.models import ColisCreationTask

class Command(BaseCommand):
    help = 'Monitor les tâches de colis et envoie des alertes'
    
    def handle(self, *args, **options):
        # Détecter les tâches bloquées
        # Envoyer des alertes aux administrateurs
        # Nettoyer les tâches anciennes
        pass
```

---

## ✅ Checklist de Validation

### Phase 1 - Modèles ✓
- [ ] Créer le modèle `ColisCreationTask`
- [ ] Ajouter le champ `type_lot` au modèle `Lot`
- [ ] Créer les migrations
- [ ] Tester les migrations sur DB de dev

### Phase 2 - Tâches Celery ✓
- [ ] Créer `create_colis_async`
- [ ] Créer `update_colis_async` 
- [ ] Tester les tâches en isolation
- [ ] Configurer les queues et routing

### Phase 3 - Vues ✓
- [ ] Remplacer `colis_create_view`
- [ ] Modifier `lot_create_view`
- [ ] Créer le dashboard de suivi
- [ ] Créer les vues de gestion d'échecs

### Phase 4 - Templates ✓
- [ ] Créer les templates de dashboard
- [ ] Adapter les formulaires existants
- [ ] Ajouter les interfaces de retry/cancel

### Phase 5 - Tests ✓
- [ ] Tests unitaires des tâches
- [ ] Tests d'intégration des vues
- [ ] Tests de performance et charge
- [ ] Validation UX avec agents

### Phase 6 - Déploiement ✓
- [ ] Configuration Celery production
- [ ] Monitoring et alertes
- [ ] Documentation utilisateur
- [ ] Formation des agents

---

## 📊 Métriques de Succès

| Métrique | Avant | Objectif | Mesure |
|----------|-------|----------|---------|
| Temps de réponse création colis | 15-30s | <0.5s | Logs serveur |
| Productivité agent | 4 colis/h | 50+ colis/h | Compteurs BD |
| Taux d'échec upload | 15% | <2% | Dashboard tâches |
| Satisfaction agent | 60% | 90%+ | Enquête mensuelle |
| Temps de traitement backend | N/A | 45s avg | Monitoring Celery |

---

## 🚨 Risques et Mitigation

### Risques identifiés :
1. **Surcharge Celery** → Monitoring + scaling horizontal
2. **Perte de tâches** → Persistence Redis + backup
3. **Données temporaires** → Nettoyage automatique
4. **Formation agents** → Documentation + tutoriels vidéo
5. **Rollback complexe** → Feature flags + migration douce

### Plan de rollback :
1. Feature flag pour basculer ancien/nouveau système
2. Migration des données en parallèle
3. Validation sur sous-ensemble d'agents d'abord

---

**Date de création :** 25 septembre 2025
**Estimation effort :** 3-4 semaines développeur senior
**Priorité :** CRITIQUE (impact productivité majeur)