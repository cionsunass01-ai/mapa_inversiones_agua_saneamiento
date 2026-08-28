from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from apps.catalogo.models import Department, Province, District

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'slug', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)

@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department')
    search_fields = ('code', 'name', 'department__name')
    list_filter = ('department',)

@admin.register(District)
class DistrictAdmin(GISModelAdmin):
    list_display = ('ubigeo', 'name', 'province')
    search_fields = ('ubigeo', 'name', 'province__name')
    list_filter = ('province__department',)
