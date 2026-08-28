from django.contrib.gis.db import models


class Provider(models.Model):
    name = models.CharField("nombre", max_length=250, unique=True)
    acronym = models.CharField("sigla", max_length=80, blank=True)
    provider_type = models.CharField("tipo", max_length=80, blank=True)
    source_data = models.JSONField("datos de origen", default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "prestador"
        verbose_name_plural = "prestadores"

    def __str__(self):
        return self.name


class ServiceArea(models.Model):
    department = models.ForeignKey("catalogo.Department", on_delete=models.PROTECT, related_name="service_areas")
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="service_areas")
    external_id = models.CharField("identificador externo", max_length=100, blank=True)
    system_name = models.CharField("sistema", max_length=250, blank=True)
    locality = models.CharField("localidad", max_length=250, blank=True)
    geometry = models.MultiPolygonField("ámbito de prestación", srid=4326)
    source_data = models.JSONField("datos de origen", default=dict, blank=True)

    class Meta:
        ordering = ["department__name", "provider__name", "system_name"]
        indexes = [models.Index(fields=["department", "provider"])]
        verbose_name = "ámbito de prestación"
        verbose_name_plural = "ámbitos de prestación"


class ContinuityPoint(models.Model):
    department = models.ForeignKey("catalogo.Department", on_delete=models.PROTECT, related_name="continuity_points")
    name = models.CharField("nombre", max_length=250, blank=True)
    group = models.CharField("grupo", max_length=150, blank=True)
    province_name = models.CharField("provincia", max_length=100, blank=True)
    district_name = models.CharField("distrito", max_length=100, blank=True)
    sector = models.CharField("sector", max_length=150, blank=True)
    locality = models.CharField("localidad", max_length=150, blank=True)
    day = models.CharField("día", max_length=50, blank=True)
    hour = models.CharField("hora", max_length=50, blank=True)
    promised_service = models.CharField("servicio prometido", max_length=150, blank=True)
    external_key = models.CharField("clave externa", max_length=150, blank=True)
    geometry = models.PointField("ubicación", srid=4326)
    source_data = models.JSONField("datos de origen", default=dict, blank=True)

    class Meta:
        ordering = ["department__name", "district_name", "name"]
        indexes = [models.Index(fields=["department", "district_name"])]
        verbose_name = "punto de continuidad"
        verbose_name_plural = "puntos de continuidad"


class ContinuityArea(models.Model):
    department = models.ForeignKey("catalogo.Department", on_delete=models.PROTECT, related_name="continuity_areas")
    provider = models.ForeignKey(Provider, on_delete=models.SET_NULL, related_name="continuity_areas", null=True, blank=True)
    method = models.CharField("método", max_length=100, default="VORONOI")
    average_hours = models.DecimalField("horas promedio", max_digits=8, decimal_places=2, null=True, blank=True)
    relative_value = models.DecimalField("valor relativo", max_digits=8, decimal_places=4, null=True, blank=True)
    geometry = models.MultiPolygonField("área", srid=4326)
    source_data = models.JSONField("datos de origen", default=dict, blank=True)

    class Meta:
        ordering = ["department__name", "method"]
        indexes = [models.Index(fields=["department", "method"])]
        verbose_name = "área de continuidad"
        verbose_name_plural = "áreas de continuidad"


class WaterStressBasin(models.Model):
    basin_id = models.CharField("código de cuenca", max_length=64, db_index=True)
    name = models.CharField("nombre de cuenca", max_length=150, blank=True)
    demand_val = models.FloatField("demanda 2050 (m3/año)", null=True, blank=True)
    supply_val = models.FloatField("oferta 2050 (m3/año)", null=True, blank=True)
    demand_cls = models.IntegerField("cuartil demanda (1-4)", null=True, blank=True)
    supply_cls = models.IntegerField("cuartil oferta (1-4)", null=True, blank=True)
    bivar_cls = models.IntegerField("clase bivariada (1-16)", db_index=True, null=True, blank=True)
    stress_category = models.CharField("categoría de riesgo", max_length=100, blank=True)
    geometry = models.MultiPolygonField("geometría de cuenca", srid=4326)
    source_data = models.JSONField("datos de origen", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["bivar_cls", "basin_id"]
        indexes = [models.Index(fields=["bivar_cls"])]
        verbose_name = "cuenca de estrés hídrico"
        verbose_name_plural = "cuencas de estrés hídrico"

    def __str__(self):
        return f"Cuenca {self.basin_id} (Clase {self.bivar_cls})"


class CentroPoblado(models.Model):
    cod_ccpp = models.CharField("código CCPP", max_length=20, db_index=True)
    name = models.CharField("nombre centro poblado", max_length=200)
    department = models.ForeignKey("catalogo.Department", on_delete=models.CASCADE, related_name="centros_poblados")
    province_name = models.CharField("provincia", max_length=150, blank=True)
    district_name = models.CharField("distrito", max_length=150, blank=True)
    district_ubigeo = models.CharField("UBIGEO distrito", max_length=10, db_index=True, blank=True)
    
    # Indicadores censales INEI 2017
    pob_total = models.IntegerField("población total", default=0)
    num_viv = models.IntegerField("total viviendas", default=0)
    pvs_agua_red = models.FloatField("% agua red pública", null=True, blank=True)
    pvs_sin_saneamiento = models.FloatField("% sin saneamiento", null=True, blank=True)
    
    # Geometrías
    point = models.PointField("punto centroide", srid=4326, null=True, blank=True)
    geometry = models.MultiPolygonField("polígono de centro poblado", srid=4326)
    source_data = models.JSONField("datos censales completos", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["department__name", "district_name", "-pob_total"]
        indexes = [models.Index(fields=["department", "district_ubigeo"])]
        verbose_name = "Centro Poblado"
        verbose_name_plural = "Centros Poblados"

    def __str__(self):
        return f"{self.name} ({self.district_name})"


