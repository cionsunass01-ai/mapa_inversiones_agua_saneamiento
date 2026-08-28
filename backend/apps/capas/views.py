from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from apps.capas.models import ServiceArea, ContinuityPoint, ContinuityArea, WaterStressBasin, CentroPoblado
from apps.capas.serializers import (
    ServiceAreaSerializer, ContinuityPointSerializer, ContinuityAreaSerializer, 
    WaterStressBasinSerializer, CentroPobladoSerializer
)

class ServiceAreaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceArea.objects.select_related('provider', 'department').all()
    serializer_class = ServiceAreaSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'department__slug']

class ContinuityPointViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContinuityPoint.objects.select_related('department').all()
    serializer_class = ContinuityPointSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'department__slug']

class ContinuityAreaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ContinuityArea.objects.select_related('provider', 'department').all()
    serializer_class = ContinuityAreaSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'department__slug']

class WaterStressBasinViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WaterStressBasin.objects.all()
    serializer_class = WaterStressBasinSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['bivar_cls', 'demand_cls', 'supply_cls']

class CentroPobladoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CentroPoblado.objects.select_related('department').all()
    serializer_class = CentroPobladoSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'department__slug', 'district_ubigeo', 'cod_ccpp']



