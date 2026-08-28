from django.contrib.gis.db import models

class Department(models.Model):
    code = models.CharField(max_length=2, unique=True, verbose_name="Código de Departamento")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    geometry = models.MultiPolygonField(srid=4326, null=True, blank=True, verbose_name="Geometría")

    class Meta:
        db_table = 'catalogo_department'
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

class Province(models.Model):
    code = models.CharField(max_length=4, unique=True, verbose_name="Código de Provincia")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='provinces', verbose_name="Departamento")
    geometry = models.MultiPolygonField(srid=4326, null=True, blank=True, verbose_name="Geometría")

    class Meta:
        db_table = 'catalogo_province'
        verbose_name = 'Provincia'
        verbose_name_plural = 'Provincias'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

class District(models.Model):
    ubigeo = models.CharField(max_length=6, primary_key=True, verbose_name="UBIGEO")
    name = models.CharField(max_length=100, verbose_name="Nombre")
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='districts', verbose_name="Provincia")
    
    # spatial field
    geometry = models.MultiPolygonField(srid=4326, verbose_name="Geometría")

    class Meta:
        db_table = 'catalogo_district'
        verbose_name = 'Distrito'
        verbose_name_plural = 'Distritos'
        ordering = ['ubigeo']

    def __str__(self):
        return f"{self.ubigeo} - {self.name}"
