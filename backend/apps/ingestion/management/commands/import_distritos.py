import os
from django.core.management.base import BaseCommand
from django.contrib.gis.gdal import DataSource, SpatialReference, CoordTransform
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.utils.text import slugify
from django.db import transaction
from apps.catalogo.models import Department, Province, District

class Command(BaseCommand):
    help = 'Importar distritos desde un Shapefile a la base de datos nacional.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Ruta al archivo .shp')
        parser.add_argument('--source-version', type=str, required=True, help='Versión de la fuente (ej: INEI_2024)')
        parser.add_argument('--dry-run', action='store_true', help='Ejecutar sin guardar en la BD')

    def handle(self, *args, **options):
        file_path = options['file']
        source_version = options['source_version']
        dry_run = options['dry_run']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'El archivo no existe: {file_path}'))
            return

        try:
            ds = DataSource(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al leer el archivo con GDAL: {e}'))
            return

        layer = ds[0]
        self.stdout.write(self.style.SUCCESS(f'Cargando layer "{layer.name}" con {len(layer)} registros (Fuente: {source_version})'))

        # Check CRS
        srs = layer.srs
        target_srs = SpatialReference(4326)
        coord_trans = None
        if srs and srs.srid != 4326:
            self.stdout.write(self.style.WARNING(f'Transformando CRS desde SRID {srs.srid} a 4326'))
            coord_trans = CoordTransform(srs, target_srs)
        elif not srs:
            self.stdout.write(self.style.WARNING('El Shapefile no tiene CRS definido, asumiendo 4326.'))

        stats = {
            'dep_created': 0, 'dep_updated': 0,
            'prov_created': 0, 'prov_updated': 0,
            'dist_created': 0, 'dist_updated': 0,
            'errors': 0
        }

        try:
            with transaction.atomic():
                for feature in layer:
                    try:
                        # Extract attributes
                        coddep = str(feature.get('CODDEP')).strip().zfill(2)
                        nomdep = str(feature.get('DEPARTAMEN')).strip()
                        codprov = coddep + str(feature.get('CODPROV')).strip().zfill(2)
                        nomprov = str(feature.get('PROVINCIA')).strip()
                        ubigeo = str(feature.get('UBIGEO')).strip().zfill(6)
                        nomdist = str(feature.get('DISTRITO')).strip()

                        # Geometry
                        geom = feature.geom
                        if coord_trans:
                            geom.transform(coord_trans)
                        
                        geos_geom = geom.geos
                        if isinstance(geos_geom, Polygon):
                            geos_geom = MultiPolygon(geos_geom)
                        elif not isinstance(geos_geom, MultiPolygon):
                            self.stdout.write(self.style.ERROR(f'Geometría inválida para UBIGEO {ubigeo}. Ignorando.'))
                            stats['errors'] += 1
                            continue
                            

                        # Update or Create Department
                        dep, dep_created = Department.objects.update_or_create(
                            code=coddep,
                            defaults={'name': nomdep, 'slug': slugify(nomdep)}
                        )
                        if dep_created:
                            stats['dep_created'] += 1
                        else:
                            stats['dep_updated'] += 1

                        # Update or Create Province
                        prov, prov_created = Province.objects.update_or_create(
                            code=codprov,
                            defaults={'name': nomprov, 'department': dep}
                        )
                        if prov_created:
                            stats['prov_created'] += 1
                        else:
                            stats['prov_updated'] += 1

                        # Update or Create District
                        dist, dist_created = District.objects.update_or_create(
                            ubigeo=ubigeo,
                            defaults={'name': nomdist, 'province': prov, 'geometry': geos_geom}
                        )
                        if dist_created:
                            stats['dist_created'] += 1
                        else:
                            stats['dist_updated'] += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error en feature (posiblemente CUI/UBIGEO inválido): {e}'))
                        stats['errors'] += 1

                if dry_run:
                    self.stdout.write(self.style.NOTICE('Modo --dry-run activo. Deshaciendo cambios...'))
                    raise Exception('Dry run rollback')

        except Exception as e:
            if str(e) != 'Dry run rollback':
                self.stdout.write(self.style.ERROR(f'Error crítico en la transacción: {e}'))
                return

        self.stdout.write(self.style.SUCCESS(
            f'Finalizado. '
            f'Departamentos: {stats["dep_created"]} creados, {stats["dep_updated"]} actualizados. '
            f'Provincias: {stats["prov_created"]} creados, {stats["prov_updated"]} actualizados. '
            f'Distritos: {stats["dist_created"]} creados, {stats["dist_updated"]} actualizados. '
            f'Errores: {stats["errors"]}'
        ))
