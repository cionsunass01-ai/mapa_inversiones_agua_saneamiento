from django.contrib import admin
from django.urls import path
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
    path('admin/', admin.site.urls),
    path('health/', health_check),
]
