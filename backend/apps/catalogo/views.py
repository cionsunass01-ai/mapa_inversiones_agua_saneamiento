from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum
from apps.catalogo.models import Department, Province, District
from apps.catalogo.serializers import DepartmentSerializer, ProvinceSerializer, DistrictSerializer

class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.filter(is_active=True).annotate(
        total_projects=Count('provinces__districts__projects', distinct=True),
        total_investment=Sum('provinces__districts__projects__cost')
    ).order_by('code')
    serializer_class = DepartmentSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['code']

class ProvinceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Province.objects.annotate(
        total_projects=Count('districts__projects', distinct=True),
        total_investment=Sum('districts__projects__cost')
    ).order_by('code')
    serializer_class = ProvinceSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'code']

class DistrictViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = District.objects.annotate(
        total_projects=Count('projects', distinct=True),
        total_investment=Sum('projects__cost')
    ).order_by('ubigeo')
    serializer_class = DistrictSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['province', 'ubigeo', 'province__department__slug']

