import glob
import pandas as pd
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from apps.catalogo.models import District, Province, Department
from apps.inversiones.models import Project

class Command(BaseCommand):
    help = 'Importa proyectos de inversión de los archivos Cartera_*.xlsx en data/staging/'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Ejecuta todo sin guardar en base de datos')
        parser.add_argument('--path', type=str, default='data/staging/Cartera_*.xlsx', help='Ruta de los archivos Excel')

    def parse_location(self, text):
        """Intenta extraer Distrito, Provincia y Departamento del nombre de la inversión."""
        dist_match = re.search(r'DISTRITO(?:S)? DE (.*?)(?: -|,| Y | PROVINCIA| DEPARTAMENTO|$)', text, re.IGNORECASE)
        prov_match = re.search(r'PROVINCIA DE (.*?)(?: -|,| Y | DEPARTAMENTO|$)', text, re.IGNORECASE)
        
        dist_name = dist_match.group(1).strip() if dist_match else None
        prov_name = prov_match.group(1).strip() if prov_match else None
        
        if dist_name:
            dist_name = dist_name.replace(' LA ', ' ').strip()
        
        return dist_name, prov_name

    def find_district(self, dist_name, prov_name):
        if not dist_name:
            return None
            
        qs = District.objects.all()
        # Clean exact matching
        qs = qs.filter(name__iexact=dist_name)
        if prov_name:
            qs = qs.filter(province__name__iexact=prov_name)
            
        if qs.count() == 1:
            return qs.first()
            
        # Try unaccent / contains if exact fails (basic attempt)
        if qs.count() == 0:
            qs2 = District.objects.filter(name__icontains=dist_name[:10])
            if prov_name:
                qs2 = qs2.filter(province__name__icontains=prov_name[:10])
            if qs2.count() == 1:
                return qs2.first()
                
        return None

    def clean_decimal(self, val):
        if pd.isna(val):
            return None
        try:
            return float(val)
        except:
            return None

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        file_path = options['path']
        
        files = glob.glob(file_path)
        if not files:
            self.stdout.write(self.style.ERROR(f'No se encontraron archivos Excel en {file_path}'))
            return
            
        self.stdout.write(f'Procesando {len(files)} archivos...')
        
        dfs = []
        for f in files:
            # Archivos Cartera_*.xlsx tienen cabeceras en la fila 6 (skiprows=5)
            try:
                df = pd.read_excel(f, skiprows=5)
                dfs.append(df)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error leyendo {f}: {e}'))
                
        if not dfs:
            return
            
        df = pd.concat(dfs, ignore_index=True)
        # Filtrar solo Saneamiento
        df = df[df['Función'].astype(str).str.upper() == 'SANEAMIENTO']
        
        self.stdout.write(self.style.SUCCESS(f'Encontrados {len(df)} proyectos de Saneamiento. Iniciando inserción...'))

        stats = {'created': 0, 'updated': 0, 'errors': 0, 'geocoded': 0}
        
        try:
            with transaction.atomic():
                for _, row in df.iterrows():
                    raw_cui = str(row.get('Código Único', ''))
                    # Normalize CUI (remove .0 and strip)
                    cui = raw_cui.replace('.0', '').strip()
                    if not cui or cui == 'nan':
                        continue
                        
                    name = str(row.get('Nombre de inversión', '')).strip()
                    
                    # Extract Geography
                    dist_name, prov_name = self.parse_location(name)
                    district = self.find_district(dist_name, prov_name)
                    
                    if district:
                        stats['geocoded'] += 1

                    cost = self.clean_decimal(row.get('Costo actualizado (S/)'))
                    executed = self.clean_decimal(row.get('Devengado acumulado (S/) (al 31 dic. 2025)'))
                    pim = self.clean_decimal(row.get('PIM 2026 (S/)'))
                    prog_1 = self.clean_decimal(row.get('Monto Año 2026 (S/)'))
                    prog_2 = self.clean_decimal(row.get('Monto Año 2027 (S/)'))
                    prog_3 = self.clean_decimal(row.get('Monto Año 2028 (S/)'))
                    prog_4 = self.clean_decimal(row.get('Monto Año 2029 (S/)'))

                    try:
                        project, created = Project.objects.update_or_create(
                            cui=cui,
                            defaults={
                                'name': name,
                                'district': district,
                                'cost': cost,
                                'executed': executed,
                                'pim': pim,
                                'prog_year_1': prog_1,
                                'prog_year_2': prog_2,
                                'prog_year_3': prog_3,
                                'prog_year_4': prog_4,
                            }
                        )
                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error guardando CUI {cui}: {e}'))
                        stats['errors'] += 1

                if dry_run:
                    self.stdout.write(self.style.NOTICE('Modo --dry-run activo. Deshaciendo cambios...'))
                    raise Exception('Dry run rollback')
                    
        except Exception as e:
            if str(e) != 'Dry run rollback':
                self.stdout.write(self.style.ERROR(f'Transacción abortada: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f"Finalizado. Creados: {stats['created']}, Actualizados: {stats['updated']}, "
            f"Con UBIGEO Asignado: {stats['geocoded']}, Errores: {stats['errors']}"
        ))
