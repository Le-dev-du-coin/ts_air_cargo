# This file makes Python treat the directory as a package

# Import Celery app to ensure it's available when Django starts
from .celery import app as celery_app

__all__ = ('celery_app',)
