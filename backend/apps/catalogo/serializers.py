from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from apps.catalogo.models import Department, Province, District

class DepartmentSerializer(GeoFeatureModelSerializer):
    total_projects = serializers.IntegerField(read_only=True)
    total_investment = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    class Meta:
        model = Department
        geo_field = 'geometry'
        fields = ('id', 'code', 'name', 'slug', 'is_active', 'total_projects', 'total_investment')

class ProvinceSerializer(GeoFeatureModelSerializer):
    total_projects = serializers.IntegerField(read_only=True)
    total_investment = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    class Meta:
        model = Province
        geo_field = 'geometry'
        fields = ('id', 'code', 'name', 'department', 'total_projects', 'total_investment')

class DistrictSerializer(GeoFeatureModelSerializer):
    province_name = serializers.CharField(source='province.name', read_only=True, allow_null=True)
    total_projects = serializers.IntegerField(read_only=True)
    total_investment = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    class Meta:
        model = District
        geo_field = 'geometry'
        fields = ('ubigeo', 'name', 'province', 'province_name', 'total_projects', 'total_investment')
