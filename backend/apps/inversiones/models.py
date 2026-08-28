from django.contrib.gis.db import models
from apps.catalogo.models import District

class Project(models.Model):
    cui = models.CharField(max_length=20, unique=True, verbose_name="Código Único")
    name = models.TextField(verbose_name="Nombre de inversión")
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects', verbose_name="Distrito (UBIGEO)")
    geometry = models.PointField(srid=4326, null=True, blank=True, verbose_name="Ubicación espacial")
    
    # Finances
    cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Costo actualizado")
    monto_viable = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Monto viable")
    executed = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Devengado acumulado")
    
    # Programmation
    pim = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="PIM")
    prog_year_1 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Monto Año 1")
    prog_year_2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Monto Año 2")
    prog_year_3 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Monto Año 3")
    prog_year_4 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Monto Año 4")
    
    # Execution & Tracking
    start_date = models.DateField(null=True, blank=True, verbose_name="Fecha Inicio")
    end_date = models.DateField(null=True, blank=True, verbose_name="Fecha Fin")
    physical_advance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Avance Físico %")
    general_advance = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Avance General %")
    report_date = models.DateField(null=True, blank=True, verbose_name="Fecha Reporte Avance")
    status = models.CharField(max_length=50, null=True, blank=True, verbose_name="Estado")

    # Extra MEF attributes
    beneficiaries = models.IntegerField(null=True, blank=True, verbose_name="Habitantes beneficiarios")
    entity = models.CharField(max_length=255, null=True, blank=True, verbose_name="Entidad")
    snip_code = models.CharField(max_length=50, null=True, blank=True, verbose_name="Código SNIP")
    typology = models.CharField(max_length=255, null=True, blank=True, verbose_name="Tipología")

    class Meta:
        db_table = 'inversiones_project'
        verbose_name = "Proyecto de Inversión"
        verbose_name_plural = "Proyectos de Inversión"
        
    def __str__(self):
        return f"{self.cui} - {self.name[:50]}"
