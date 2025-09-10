from django.urls import path
from . import views

app_name = 'admin_chine_app'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
