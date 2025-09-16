from django.urls import path
from . import views

app_name = 'reporting_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/status/', views.api_status, name='api_status'),
]
