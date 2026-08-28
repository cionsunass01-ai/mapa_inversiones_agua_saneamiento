from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework_gis.fields import GeometrySerializerMethodField
from apps.inversiones.models import Project
from rest_framework import serializers

class ProjectSerializer(GeoFeatureModelSerializer):
    geometry = GeometrySerializerMethodField()
    province = serializers.CharField(source='district.province.name', read_only=True, allow_null=True)
    district_name = serializers.CharField(source='district.name', read_only=True, allow_null=True)
    department_name = serializers.CharField(source='district.province.department.name', read_only=True, allow_null=True)
    ubigeo = serializers.CharField(source='district.ubigeo', read_only=True, allow_null=True)
    
    # Aliases for frontend compatibility
    updated_cost = serializers.DecimalField(source='cost', max_digits=15, decimal_places=2, read_only=True)
    executed_budget = serializers.DecimalField(source='executed', max_digits=15, decimal_places=2, read_only=True)
    physical_progress = serializers.DecimalField(source='physical_advance', max_digits=5, decimal_places=2, read_only=True)
    physical_status = serializers.CharField(source='status', read_only=True, allow_null=True)
    physical_report_date = serializers.DateField(source='report_date', read_only=True, allow_null=True)
    provider_name = serializers.CharField(source='entity', read_only=True, allow_null=True)
    
    programmed_year_0 = serializers.DecimalField(source='pim', max_digits=15, decimal_places=2, read_only=True)
    programmed_year_1 = serializers.DecimalField(source='prog_year_1', max_digits=15, decimal_places=2, read_only=True)
    programmed_year_2 = serializers.DecimalField(source='prog_year_2', max_digits=15, decimal_places=2, read_only=True)
    programmed_year_3 = serializers.DecimalField(source='prog_year_3', max_digits=15, decimal_places=2, read_only=True)
    has_gps = serializers.SerializerMethodField()
    coordinate_type = serializers.SerializerMethodField()

    class Meta:
        model = Project
        geo_field = 'geometry'
        fields = '__all__'

    def get_geometry(self, obj):
        if obj.geometry:
            return obj.geometry
        return None

    def get_has_gps(self, obj):
        return obj.geometry is not None

    def get_coordinate_type(self, obj):
        if obj.geometry:
            return "Coordenada exacta MEF"
        return "Sin coordenada GPS"
