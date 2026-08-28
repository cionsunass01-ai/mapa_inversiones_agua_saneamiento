from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.capas.views import (
    ServiceAreaViewSet, ContinuityPointViewSet, ContinuityAreaViewSet, 
    WaterStressBasinViewSet, CentroPobladoViewSet
)

router = DefaultRouter()
router.register(r'service-areas', ServiceAreaViewSet, basename='servicearea')
router.register(r'continuity-points', ContinuityPointViewSet, basename='continuitypoint')
router.register(r'continuity-areas', ContinuityAreaViewSet, basename='continuityarea')
router.register(r'water-stress-basins', WaterStressBasinViewSet, basename='waterstressbasin')
router.register(r'centros-poblados', CentroPobladoViewSet, basename='centropoblado')

urlpatterns = [
    path('', include(router.urls)),
]
