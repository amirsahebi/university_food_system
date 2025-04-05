from django.http import HttpResponse
from django.db import connection
from django.core.cache import cache

def health_check(request):
    """
    Health check view to verify database and cache connectivity
    """
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        return HttpResponse("Database connection failed", status=500)
    
    # Check cache connectivity (if using cache)
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') != 'ok':
            return HttpResponse("Cache connection failed", status=500)
    except Exception as e:
        return HttpResponse("Cache connection failed", status=500)
    
    return HttpResponse("OK", status=200)
