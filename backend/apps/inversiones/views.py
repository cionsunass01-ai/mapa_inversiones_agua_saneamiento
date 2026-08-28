from rest_framework import viewsets
from rest_framework_gis.pagination import GeoJsonPagination
from django_filters.rest_framework import DjangoFilterBackend
from apps.inversiones.models import Project
from apps.inversiones.serializers import ProjectSerializer

class CustomGeoJsonPagination(GeoJsonPagination):
    page_size = 1000
    page_size_query_param = 'limit'
    max_page_size = 5000

class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Project.objects.select_related('district', 'district__province', 'district__province__department').all().order_by('-cost')
    serializer_class = ProjectSerializer
    pagination_class = CustomGeoJsonPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['district', 'district__province', 'district__province__department', 'district__province__department__slug']

