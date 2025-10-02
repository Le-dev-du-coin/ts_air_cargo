from django.apps import AppConfig


class WhatsappMonitoringAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'whatsapp_monitoring_app'
    verbose_name = 'Monitoring WhatsApp'
    
    def ready(self):
        # Import des signals si nécessaire
        try:
            from . import signals
        except ImportError:
            pass
