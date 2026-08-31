from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from apps.capas.models import Provider, ServiceArea, ContinuityPoint, ContinuityArea, WaterStressBasin, CentroPoblado

class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = '__all__'

class ServiceAreaSerializer(GeoFeatureModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True, default=None, allow_null=True)
    
    class Meta:
        model = ServiceArea
        geo_field = 'geometry'
        fields = ('id', 'external_id', 'system_name', 'locality', 'provider_name', 'department')

class ContinuityPointSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = ContinuityPoint
        geo_field = 'geometry'
        fields = ('id', 'name', 'group', 'province_name', 'district_name', 'sector', 'locality', 'day', 'hour', 'promised_service', 'department')

class ContinuityAreaSerializer(GeoFeatureModelSerializer):
    provider_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ContinuityArea
        geo_field = 'geometry'
        fields = ('id', 'method', 'average_hours', 'relative_value', 'provider_name', 'department')

    def get_provider_name(self, obj):
        if obj.provider:
            return obj.provider.name
        return "EPS Departamental"

class WaterStressBasinSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = WaterStressBasin
        geo_field = 'geometry'
        fields = (
            'id', 'basin_id', 'name', 'demand_val', 'supply_val', 
            'demand_cls', 'supply_cls', 'bivar_cls', 'stress_category'
        )

class CentroPobladoSerializer(GeoFeatureModelSerializer):
    monto_planificado = serializers.DecimalField(source='total_investment', max_digits=20, decimal_places=2, read_only=True)
    monto_invertido = serializers.DecimalField(source='total_executed', max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = CentroPoblado
        geo_field = 'geometry'
        fields = (
            'id', 'cod_ccpp', 'name', 'province_name', 'district_name', 
            'district_ubigeo', 'pob_total', 'num_viv', 'pvs_agua_red', 
            'pvs_sin_saneamiento', 'total_projects', 'total_investment', 
            'total_executed', 'monto_planificado', 'monto_invertido', 'department'
        )


