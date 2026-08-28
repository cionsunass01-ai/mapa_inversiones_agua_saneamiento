from django.core.management.base import BaseCommand
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from apps.catalogo.models import Department
from apps.capas.models import Provider, ServiceArea

class Command(BaseCommand):
    help = 'Importa la capa de EPS desde un Shapefile'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, default='data/staging/Periurb_PrestadoresEPS.shp')

    def handle(self, *args, **options):
        path = options['path']
        self.stdout.write(f'Leyendo shapefile: {path}')
        
        try:
            ds = DataSource(path)
            layer = ds[0]
            self.stdout.write(f'Features encontrados: {len(layer)}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error leyendo {path}: {e}'))
            return
            
        created = 0
        updated = 0
        
        for feat in layer:
            # Clean values
            nomdep = str(feat.get('nomdep')).strip().upper() if 'nomdep' in layer.fields else ''
            nomeps = str(feat.get('NOMEPS')).strip() if 'NOMEPS' in layer.fields else ''
            id_eps = str(feat.get('id_eps')).strip() if 'id_eps' in layer.fields else ''
            tipss = str(feat.get('tipss')).strip() if 'tipss' in layer.fields else ''
            
            loc1 = str(feat.get('Localidad')).strip() if 'Localidad' in layer.fields else ''
            loc2 = str(feat.get('NOMCCPP')).strip() if 'NOMCCPP' in layer.fields else ''
            locality = loc1 if loc1 else loc2
            
            if not nomeps:
                continue
                
            # Find department
            try:
                dept = Department.objects.get(name__iexact=nomdep)
            except Department.DoesNotExist:
                # If cannot match, skip or assign to a generic? The old script skipped or failed.
                # We will log it but continue
                # self.stdout.write(self.style.WARNING(f'Departamento no encontrado: {nomdep}'))
                continue
                
            # Create/Get Provider
            provider, _ = Provider.objects.get_or_create(
                name=nomeps,
                defaults={'provider_type': tipss}
            )
            
            # Get geometry
            geom = feat.geom.geos
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon(geom)
                
            if geom.srid is None:
                geom.srid = 4326
            elif geom.srid != 4326:
                geom.transform(4326)
                
            # Create ServiceArea
            _, is_created = ServiceArea.objects.update_or_create(
                department=dept,
                external_id=id_eps if id_eps else f"gen-{created+updated}",
                defaults={
                    'provider': provider,
                    'system_name': nomeps,
                    'locality': locality,
                    'geometry': geom,
                }
            )
            
            if is_created:
                created += 1
            else:
                updated += 1
                
        self.stdout.write(self.style.SUCCESS(f'EPS importadas: {created} nuevas, {updated} actualizadas.'))
