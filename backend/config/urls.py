from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse

from django.db import connection
from django.db.utils import OperationalError

def health_check(request):
    db_status = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError:
        db_status = "error"
    
    status = "ok" if db_status == "ok" else "error"
    return JsonResponse({"status": status, "database": db_status})

urlpatterns = [
    path('', TemplateView.as_view(template_name='mapa.html'), name='visor'),
    path('admin/', admin.site.urls),
    path('health/', health_check),
    path('api/v1/catalogo/', include('apps.catalogo.urls')),
    path('api/v1/inversiones/', include('apps.inversiones.urls')),
    path('api/v1/capas/', include('apps.capas.urls')),
]
