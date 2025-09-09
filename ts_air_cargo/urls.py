from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

def home_redirect(request):
    """Redirect to authentication by default"""
    return redirect('authentication:login')

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Home redirect
    path('', home_redirect, name='home'),
    
    # Application URLs
    path('', home_redirect, name='home'),
    path('authentication/', include('authentication.urls')),
    path('admin-chine/', include('admin_chine_app.urls')),
    path('admin-mali/', include('admin_mali_app.urls')),
    path('agent-chine/', include('agent_chine_app.urls')),
    path('agent-mali/', include('agent_mali_app.urls')),
    path('client/', include('client_app.urls')),
    path('notifications/', include('notifications_app.urls')),
    path('reporting/', include('reporting_app.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
