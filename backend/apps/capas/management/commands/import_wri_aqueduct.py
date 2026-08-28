import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from django.db import transaction
from shapely import force_2d
from shapely.geometry import MultiPolygon, mapping

from apps.capas.models import WaterStressBasin
from apps.catalogo.models import Department

WRI_ZIP_URL = "https://files.wri.org/aqueduct/aqueduct-4-0-water-risk-data.zip"

STRESS_CATEGORIES = {
    1: "Bajo Uso y Aridez (Demanda Muy Baja / Oferta Muy Baja)",
    2: "Demanda Muy Baja / Oferta Media-Baja",
    3: "Demanda Muy Baja / Oferta Media-Alta",
    4: "Abundancia Hídrica (Demanda Muy Baja / Oferta Muy Alta)",
    
    5: "Demanda Media-Baja / Oferta Muy Baja",
    6: "Demanda Media-Baja / Oferta Media-Baja",
    7: "Demanda Media-Baja / Oferta Media-Alta",
    8: "Favorable (Demanda Media-Baja / Oferta Alta)",
    
    9: "Demanda Media-Alta / Oferta Muy Baja",
    10: "Demanda Media-Alta / Oferta Media-Baja",
    11: "Demanda Media-Alta / Oferta Media-Alta",
    12: "Equilibrado (Demanda Media-Alta / Oferta Alta)",
    
    13: "Estrés Hídrico Crítico (Demanda Muy Alta / Oferta Muy Baja)",
    14: "Estrés Hídrico Alto (Demanda Muy Alta / Oferta Media-Baja)",
    15: "Demanda Alta / Oferta Media-Alta",
    16: "Alto Caudal y Uso (Demanda Muy Alta / Oferta Muy Alta)",
}

def clean_val(v):
    if v is None or pd.isna(v):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

class Command(BaseCommand):
    help = "Descarga, recorta estrictamente al territorio del Perú y procesa las cuencas de WRI Aqueduct 4.0 con clasificación bivariada 4x4."

    def add_arguments(self, parser):
        parser.add_argument("--zip-path", type=str, help="Ruta al archivo ZIP de Aqueduct 4.0 si ya fue descargado")
        parser.add_argument("--gdb-path", type=str, help="Ruta a la carpeta .gdb de Aqueduct 4.0 si ya fue extraída")

    def handle(self, *args, **options):
        staging_dir = Path("data/staging")
        staging_dir.mkdir(parents=True, exist_ok=True)

        gdb_path = options.get("gdb_path")
        zip_path = options.get("zip_path")

        # 1. Obtener el límite oficial de la República del Perú
        self.stdout.write(self.style.NOTICE("Construyendo polígono oficial del territorio del Perú..."))
        depts = Department.objects.filter(geometry__isnull=False)
        dept_geoms = [shapely.from_geojson(d.geometry.geojson) for d in depts]
        peru_boundary = shapely.unary_union(dept_geoms)
        if not peru_boundary.is_valid:
            peru_boundary = shapely.make_valid(peru_boundary)
        self.stdout.write(self.style.SUCCESS(f"Límite de Perú consolidado ({len(dept_geoms)} departamentos)."))

        # 2. Localizar o Descargar el dataset
        if not gdb_path:
            target_zip = Path(zip_path) if zip_path else staging_dir / "aqueduct_4_0.zip"
            if not target_zip.exists():
                self.stdout.write(self.style.NOTICE(f"Descargando WRI Aqueduct 4.0 desde: {WRI_ZIP_URL}..."))
                urllib.request.urlretrieve(WRI_ZIP_URL, target_zip)
                self.stdout.write(self.style.SUCCESS("Descarga completada."))
            else:
                self.stdout.write(f"Archivo ZIP existente en: {target_zip}")

            # Extraer ZIP
            extract_dir = staging_dir / "aqueduct_gdb"
            if not extract_dir.exists() or not any(extract_dir.glob("*.gdb")):
                self.stdout.write(f"Extrayendo archivo ZIP en {extract_dir}...")
                with zipfile.ZipFile(target_zip, 'r') as zf:
                    zf.extractall(extract_dir)
                self.stdout.write(self.style.SUCCESS("Extracción completada."))

            gdb_candidates = list(extract_dir.rglob("*.gdb"))
            if not gdb_candidates:
                raise FileNotFoundError("No se encontró ninguna carpeta .gdb dentro del archivo extraído.")
            gdb_path = gdb_candidates[0]

        self.stdout.write(self.style.NOTICE(f"Leyendo Geodatabase desde: {gdb_path}"))
        layers = pyogrio.list_layers(str(gdb_path))

        layer_name = None
        for l in layers:
            lname = l[0]
            if "future_annual" in lname.lower() or "a0000000b" in lname.lower():
                layer_name = lname
                break
        if not layer_name:
            layer_name = layers[0][0]

        self.stdout.write(self.style.NOTICE(f"Cargando capa: '{layer_name}'..."))
        
        # Bounding box amplio de Perú
        bbox_peru = (-82.0, -19.0, -68.0, 0.5)
        gdf = gpd.read_file(str(gdb_path), layer=layer_name, bbox=bbox_peru)
        self.stdout.write(f"Registros leídos inicialmente en el área circundante: {len(gdf)}")

        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # 3. RECORTE ESTRICTO A LAS FRONTERAS DEL PERÚ
        self.stdout.write(self.style.NOTICE("Recortando geometrías estrictamente al límite nacional del Perú (eliminando áreas fuera de frontera)..."))
        
        clipped_rows = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            
            # Intersección geométrica con el límite de Perú
            if not geom.intersects(peru_boundary):
                continue

            clipped_geom = geom.intersection(peru_boundary)
            if clipped_geom.is_empty or clipped_geom.area < 1e-8:
                continue

            row_dict = row.to_dict()
            row_dict["geometry"] = clipped_geom
            clipped_rows.append(row_dict)

        gdf_peru = gpd.GeoDataFrame(clipped_rows, crs="EPSG:4326")
        self.stdout.write(self.style.SUCCESS(f"Cuencas dentro del territorio peruano tras recorte: {len(gdf_peru)}"))

        # 4. Variables de Demanda y Oferta BAU 2050 (Escenario Business-As-Usual)
        demand_col = "bau50_ww_x_r" if "bau50_ww_x_r" in gdf_peru.columns else "bau50_ww_x_l"
        supply_col = "bau50_ba_x_r" if "bau50_ba_x_r" in gdf_peru.columns else "bau50_ba_x_l"

        self.stdout.write(self.style.SUCCESS(f"Variables seleccionadas -> Demanda BAU: '{demand_col}' | Oferta BAU: '{supply_col}'"))

        gdf_peru["demand_clean"] = gdf_peru[demand_col].apply(clean_val).fillna(0.0)
        gdf_peru["supply_clean"] = gdf_peru[supply_col].apply(clean_val).fillna(0.0)

        # 5. Calcular Cuartiles (1 al 4) y Clase Bivariada (1 al 16) sobre cuencas peruanas
        self.stdout.write("Calculando cuantiles para Demanda y Oferta en el territorio nacional...")
        
        try:
            gdf_peru["demand_cls"] = pd.qcut(gdf_peru["demand_clean"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
        except Exception:
            gdf_peru["demand_cls"] = 1

        try:
            gdf_peru["supply_cls"] = pd.qcut(gdf_peru["supply_clean"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
        except Exception:
            gdf_peru["supply_cls"] = 1

        # Fórmula bivariada: (demand_cls - 1) * 4 + supply_cls
        gdf_peru["bivar_cls"] = (gdf_peru["demand_cls"] - 1) * 4 + gdf_peru["supply_cls"]

        # 6. Guardar en Base de Datos PostGIS
        self.stdout.write(self.style.NOTICE("Guardando cuencas exclusivamente peruanas en PostGIS..."))
        
        created_count = 0
        with transaction.atomic():
            WaterStressBasin.objects.all().delete()

            for idx, row in gdf_peru.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue

                geom_2d = force_2d(geom)
                if geom_2d.geom_type == "Polygon":
                    geom_2d = MultiPolygon([geom_2d])
                elif geom_2d.geom_type == "GeometryCollection":
                    polys = [g for g in geom_2d.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
                    if not polys: continue
                    geom_2d = MultiPolygon(polys)
                elif geom_2d.geom_type != "MultiPolygon":
                    continue

                geos_geom = GEOSGeometry(json.dumps(mapping(geom_2d)), srid=4326)
                
                basin_code = str(row.get("string_id") or row.get("pfaf_id") or row.get("hybas_id") or f"basin-{idx:04d}")
                bivar = int(row["bivar_cls"])
                category = STRESS_CATEGORIES.get(bivar, "Sin categoría")

                WaterStressBasin.objects.create(
                    basin_id=basin_code,
                    name=str(row.get("name") or row.get("basin_name") or f"Cuenca {basin_code}"),
                    demand_val=float(row["demand_clean"]),
                    supply_val=float(row["supply_clean"]),
                    demand_cls=int(row["demand_cls"]),
                    supply_cls=int(row["supply_cls"]),
                    bivar_cls=bivar,
                    stress_category=category,
                    geometry=geos_geom,
                    source_data={
                        "demand_raw": clean_val(row.get(demand_col)),
                        "supply_raw": clean_val(row.get(supply_col)),
                        "ws_score": clean_val(row.get("bau50_ws_x_r")),
                        "pfaf_id": str(row.get("pfaf_id", "")),
                    }
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"¡Éxito! Se importaron {created_count} cuencas de WRI Aqueduct 4.0 recortadas estrictamente al Perú."
        ))
