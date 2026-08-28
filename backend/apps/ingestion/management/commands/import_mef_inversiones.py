import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.db import transaction
from apps.catalogo.models import District, Province, Department
from apps.inversiones.models import Project

logger = logging.getLogger(__name__)

MEF_API_URL = "https://api.datosabiertos.mef.gob.pe/DatosAbiertos/v1/datastore_search"
RESOURCE_ID = "f9cc4ba0-931a-4b70-86c9-eacbd8c68596"

class Command(BaseCommand):
    help = 'Descarga y actualiza proyectos de inversión de Agua y Saneamiento desde la API de Datos Abiertos del MEF'

    def add_arguments(self, parser):
        parser.add_argument('--department', '-d', type=str, default=None, help='Nombre del departamento (ej. AREQUIPA, PUNO, CUSCO). Si no se especifica, procesa todos.')
        parser.add_argument('--level', '-l', type=str, default=None, help='Nivel de gobierno (GN, GR, GL)')
        parser.add_argument('--batch-size', type=int, default=1000, help='Tamaño del lote por consulta (máx 1000)')
        parser.add_argument('--limit', type=int, default=None, help='Límite total de registros a importar')
        parser.add_argument('--dry-run', action='store_true', help='Ejecuta la consulta y procesamiento sin guardar en base de datos')
        parser.add_argument('--clear', action='store_true', help='Elimina los proyectos existentes antes de importar')

    def clean_decimal(self, val):
        if val is None or val == '' or str(val).lower() in ['nan', 'null', 'none']:
            return 0.0
        try:
            return float(str(val).replace(',', '').strip())
        except (ValueError, TypeError):
            return 0.0

    def clean_int(self, val):
        if val is None or val == '' or str(val).lower() in ['nan', 'null', 'none']:
            return None
        try:
            return int(float(str(val).replace(',', '').strip()))
        except (ValueError, TypeError):
            return None

    def clean_date(self, val):
        if not val or str(val).lower() in ['nan', 'null', 'none', '']:
            return None
        s = str(val).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%Y%m'):
            try:
                return datetime.strptime(s[:19], fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    def fetch_mef_records(self, filters, batch_size=1000, max_limit=None):
        offset = 0
        total_fetched = 0

        while True:
            params = {
                'resource_id': RESOURCE_ID,
                'limit': batch_size,
                'offset': offset,
                'include_total': 'true'
            }
            if filters:
                params['filters'] = json.dumps(filters)

            url = f"{MEF_API_URL}?{urllib.parse.urlencode(params)}"
            self.stdout.write(f"Consultando MEF API (offset={offset}, limit={batch_size})...")

            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'SUNASS-Plataforma-Territorial/2.0'}
            )

            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error conectando a MEF API: {e}"))
                break

            records = data.get('records', [])
            total_available = int(data.get('result', {}).get('include_total') or len(records))

            if not records:
                break

            yield records, total_available
            
            total_fetched += len(records)
            offset += len(records)

            if max_limit and total_fetched >= max_limit:
                break

            if offset >= total_available:
                break

    def handle(self, *args, **options):
        department = options['department']
        level = options['level']
        batch_size = options['batch_size']
        max_limit = options['limit']
        dry_run = options['dry_run']
        clear_existing = options['clear']

        filters = {"FUNCION": "SANEAMIENTO"}
        if department:
            filters["DEPARTAMENTO"] = department.upper().strip()
        if level:
            filters["NIVEL"] = level.upper().strip()

        self.stdout.write(self.style.NOTICE(f"Filtros aplicados: {json.dumps(filters)}"))

        # Pre-cargar catálogo de distritos en memoria para búsquedas O(1)
        self.stdout.write("Cargando distritos en memoria para asignación geográfica...")
        districts_by_ubigeo = {d.ubigeo: d for d in District.objects.select_related('province', 'province__department').all()}
        districts_by_name = {}
        for d in districts_by_ubigeo.values():
            key = (d.name.upper().strip(), d.province.name.upper().strip())
            districts_by_name[key] = d
            if d.name.upper().strip() not in districts_by_name:
                districts_by_name[d.name.upper().strip()] = d

        if clear_existing and not dry_run:
            if department:
                del_count, _ = Project.objects.filter(district__province__department__name__iexact=department).delete()
                self.stdout.write(self.style.WARNING(f"Eliminados {del_count} proyectos existentes en {department}."))
            else:
                del_count, _ = Project.objects.all().delete()
                self.stdout.write(self.style.WARNING(f"Eliminados {del_count} proyectos existentes en la BD."))

        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'with_coords': 0,
            'with_district': 0,
            'errors': 0
        }

        try:
            for records, total_available in self.fetch_mef_records(filters, batch_size=batch_size, max_limit=max_limit):
                self.stdout.write(f"Procesando lote de {len(records)} registros (Total estimado: {total_available})...")
                
                projects_to_create = []
                projects_to_update = []

                # Usar transacción por lote para máxima eficiencia
                with transaction.atomic():
                    for r in records:
                        raw_cui = str(r.get('CODIGO_UNICO') or r.get('CODIGO_SNIP') or '').strip()
                        cui = raw_cui.replace('.0', '').strip()
                        if not cui or cui == 'nan':
                            continue

                        name = str(r.get('NOMBRE_INVERSION') or '').strip()
                        ubigeo = str(r.get('UBIGEO') or '').strip().zfill(6) if r.get('UBIGEO') else None

                        # Asignación de distrito
                        district = districts_by_ubigeo.get(ubigeo)
                        if not district:
                            dist_name = str(r.get('DISTRITO') or '').upper().strip()
                            prov_name = str(r.get('PROVINCIA') or '').upper().strip()
                            district = districts_by_name.get((dist_name, prov_name)) or districts_by_name.get(dist_name)

                        if district:
                            stats['with_district'] += 1

                        # Coordenadas exactas del MEF
                        lat = self.clean_decimal(r.get('LATITUD'))
                        lon = self.clean_decimal(r.get('LONGITUD'))
                        geometry = None
                        if lat != 0 and lon != 0 and -19.5 <= lat <= 0.5 and -82.0 <= lon <= -68.0:
                            geometry = Point(lon, lat, srid=4326)
                            stats['with_coords'] += 1

                        # Costos y devengados
                        cost = self.clean_decimal(r.get('COSTO_ACTUALIZADO') or r.get('MONTO_VIABLE'))
                        monto_viable = self.clean_decimal(r.get('MONTO_VIABLE'))
                        dev_acum = self.clean_decimal(r.get('DEVEN_ACUMUL_ANIO_ANT'))
                        dev_actual = self.clean_decimal(r.get('DEV_ANIO_ACTUAL'))
                        executed = dev_acum + dev_actual

                        # Programación multianual
                        pim = self.clean_decimal(r.get('PIM_ANIO_ACTUAL'))
                        prog_1 = self.clean_decimal(r.get('PMI_ANIO_1'))
                        prog_2 = self.clean_decimal(r.get('PMI_ANIO_2'))
                        prog_3 = self.clean_decimal(r.get('PMI_ANIO_3'))
                        prog_4 = self.clean_decimal(r.get('PMI_ANIO_4'))

                        # Avances y fechas
                        phys_val = self.clean_decimal(r.get('AVANCE_FISICO'))
                        gen_val = self.clean_decimal(r.get('AVANCE_EJECUCION'))
                        physical_advance = min(999.99, max(0.0, phys_val)) if r.get('AVANCE_FISICO') not in [None, ''] else None
                        general_advance = min(999.99, max(0.0, gen_val)) if r.get('AVANCE_EJECUCION') not in [None, ''] else None
                        
                        start_date = self.clean_date(r.get('FEC_INI_EJEC_FISICA') or r.get('FEC_INI_EJECUCION'))
                        end_date = self.clean_date(r.get('FEC_FIN_EJEC_FISICA') or r.get('FEC_FIN_EJECUCION'))
                        report_date = self.clean_date(r.get('ULT_FEC_DECLA_ESTIM') or r.get('FECHA_REGISTRO') or r.get('FECHA_VIABILIDAD'))

                        # Estado de avance
                        if r.get('TIENE_AVAN_FISICO') == 'SI' or (physical_advance is not None and physical_advance > 0):
                            status = 'ACTUALIZADO'
                        elif r.get('TIENE_AVAN_FISICO') == 'NO' or not report_date:
                            status = 'DESACTUALIZADO'
                        else:
                            status = str(r.get('ESTADO') or 'ACTIVO')[:50]

                        # Atributos adicionales MEF
                        beneficiaries = self.clean_int(r.get('NUM_HABITANTES_BENEF'))
                        entity = str(r.get('ENTIDAD') or r.get('NOMBRE_UEP') or r.get('NOMBRE_UF') or '')[:255]
                        snip_code = str(r.get('CODIGO_SNIP') or '')[:50]
                        typology = str(r.get('DES_TIPOLOGIA') or r.get('SUBPROGRAMA') or '')[:255]

                        defaults = {
                            'name': name,
                            'district': district,
                            'geometry': geometry,
                            'cost': cost,
                            'monto_viable': monto_viable,
                            'executed': executed,
                            'pim': pim,
                            'prog_year_1': prog_1,
                            'prog_year_2': prog_2,
                            'prog_year_3': prog_3,
                            'prog_year_4': prog_4,
                            'start_date': start_date,
                            'end_date': end_date,
                            'physical_advance': physical_advance,
                            'general_advance': general_advance,
                            'report_date': report_date,
                            'status': status,
                            'beneficiaries': beneficiaries,
                            'entity': entity,
                            'snip_code': snip_code,
                            'typology': typology,
                        }

                        if not dry_run:
                            try:
                                proj, created = Project.objects.update_or_create(
                                    cui=cui,
                                    defaults=defaults
                                )
                                if created:
                                    stats['created'] += 1
                                else:
                                    stats['updated'] += 1
                            except Exception as e:
                                stats['errors'] += 1
                                self.stdout.write(self.style.ERROR(f"Error con CUI {cui}: {e}"))
                        else:
                            stats['created'] += 1

                        stats['processed'] += 1

                self.stdout.write(self.style.SUCCESS(
                    f"Progreso: {stats['processed']} procesados | "
                    f"Creados: {stats['created']} | "
                    f"Actualizados: {stats['updated']} | "
                    f"Con Coordenadas: {stats['with_coords']} | "
                    f"Con Distrito: {stats['with_district']}"
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error general durante la importación: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n========================================\n"
            f"RESULTADO DE IMPORTACIÓN DESDE MEF API\n"
            f"Procesados: {stats['processed']}\n"
            f"Creados: {stats['created']}\n"
            f"Actualizados: {stats['updated']}\n"
            f"Con Coordenadas Exactas MEF: {stats['with_coords']}\n"
            f"Con Distrito Asignado: {stats['with_district']}\n"
            f"Errores: {stats['errors']}\n"
            f"========================================"
        ))
