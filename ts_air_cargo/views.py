from django.shortcuts import render


def bad_request(request, exception=None):
    """Custom handler for 400 Bad Request."""
    return render(request, '400.html', status=400)


def permission_denied(request, exception=None):
    """Custom handler for 403 Permission Denied."""
    return render(request, '403.html', status=403)


def page_not_found(request, exception=None):
    """Custom handler for 404 Not Found."""
    return render(request, '404.html', status=404)


def server_error(request):
    """Custom handler for 500 Internal Server Error."""
    return render(request, '500.html', status=500)
