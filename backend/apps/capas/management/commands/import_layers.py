import json
import re
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import shapely
from shapely import force_2d
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, mapping
from shapely.ops import voronoi_diagram

from apps.capas.models import ContinuityArea, ContinuityPoint, Provider, ServiceArea
from apps.catalogo.models import Department

DEFAULT_EPS_BY_DEPT = {
    "AMAZONAS": "EMAPAB S.A. / EPS EMUSAP",
    "ANCASH": "EPS SEDACHIMBOTE S.A.",
    "APURIMAC": "EMUSAP ABANCAY S.A.",
    "AREQUIPA": "SEDAPAR S.A.",
    "AYACUCHO": "SEDA AYACUCHO S.A.",
    "CAJAMARCA": "SEDACAJ S.A.",
    "CALLAO": "SEDAPAL",
    "CUSCO": "SEDACUSCO S.A.",
    "HUANCAVELICA": "EMAPA HUANCAVELICA S.A.",
    "HUANUCO": "SEDA HUANUCO S.A.",
    "ICA": "EMAPAVICA S.A.",
    "JUNIN": "EPS SEDAM HUANCAYO S.A.",
    "LA LIBERTAD": "SEDALIB S.A.",
    "LAMBAYEQUE": "EPSEL S.A.",
    "LIMA": "SEDAPAL",
    "LORETO": "EPS SEDALORETO S.A.",
    "MADRE DE DIOS": "EPS EMAPAT S.A.",
    "MOQUEGUA": "EPS ILO S.A. / EPS MOQUEGUA",
    "PASCO": "EMAPA PASCO S.A.",
    "PIURA": "EPS GRAU S.A.",
    "PUNO": "EMSAPUNO S.A.",
    "SAN MARTIN": "EMAPA SAN MARTIN S.A.",
    "TACNA": "EPS TACNA S.A.",
    "TUMBES": "UNIDAD EJECUTORA AGUA TUMBES",
    "UCAYALI": "EMAPACOP S.A."
}

def clean(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()

def geometry_value(geometry):
    if geometry is None or geometry.is_empty:
        return None
    geometry = force_2d(geometry)
    if geometry.geom_type == "Polygon":
        geometry = MultiPolygon([geometry])
    return GEOSGeometry(json.dumps(mapping(geometry)), srid=4326)

def point_value(row):
    try:
        lat = float(clean(row.get("latitud")))
        lon = float(clean(row.get("longitud")))
    except (TypeError, ValueError):
        return None
    if lat == 0 or lon == 0:
        return None
    return GEOSGeometry(json.dumps({"type": "Point", "coordinates": [lon, lat]}), srid=4326)

def parse_hours(hour_str, service_str):
    text = f"{clean(hour_str)} {clean(service_str)}"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:h|horas|hr|hrs)', text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    
    r = re.findall(r'(\d{1,2}):\d{2}', text)
    if len(r) >= 2:
        try:
            h1 = int(r[0])
            h2 = int(r[1])
            diff = (h2 - h1) if h2 >= h1 else (h2 + 24 - h1)
            return float(diff)
        except:
            pass
    return None

class Command(BaseCommand):
    help = "Importa ámbitos de prestación EPS, puntos de continuidad y calcula áreas Voronoi."

    def add_arguments(self, parser):
        parser.add_argument("--department", type=str, help="Slug del departamento")
        parser.add_argument("--dry-run", action="store_true", help="Ejecutar en modo de prueba")
        parser.add_argument("--generate-voronoi", action="store_true", help="Forzar generación de áreas Voronoi")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        dept_slug = options.get("department")

        if dept_slug:
            departments = Department.objects.filter(slug=dept_slug)
        else:
            departments = Department.objects.filter(geometry__isnull=False)

        for dept in departments:
            slug = dept.slug
            self.stdout.write(self.style.NOTICE(f"\n--- Procesando {dept.name} ({slug}) ---"))

            # 1. Importar EPS Shapefile
            eps_path = Path(f"data/staging/EPS_{slug.capitalize()}.shp")
            if not eps_path.exists():
                eps_path = Path("data/staging/Periurb_PrestadoresEPS.shp")
            
            if eps_path.exists():
                self.import_eps(eps_path, dept, dry_run=dry_run)

            # 2. Importar Puntos de Continuidad (si existen)
            cont_path = Path(f"data/staging/Horario {slug.capitalize()}.xlsx")
            if cont_path.exists():
                self.import_continuity_points(cont_path, dept, dry_run=dry_run)
                # 3. Generar Áreas de Voronoi
                self.generate_voronoi_areas(dept, dry_run=dry_run)

    def import_eps(self, path, department, dry_run=False):
        gdf = gpd.read_file(path)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        if path.name == "Periurb_PrestadoresEPS.shp" and "nomdep" in gdf.columns:
            gdf = gdf[gdf["nomdep"].astype(str).str.upper() == department.name.upper()]

        if gdf.empty:
            return

        self.stdout.write(f"Leyendo EPS Shapefile ({path.name}) para {department.name}: {len(gdf)} áreas encontradas.")

        created = 0
        updated = 0
        if not dry_run:
            with transaction.atomic():
                for source_index, (_, row) in enumerate(gdf.iterrows(), start=1):
                    provider_name = clean(row.get("EPS")) or clean(row.get("NOMEPS")) or clean(row.get("Pres_Sigla")) or clean(row.get("Pres_Nom"))
                    if not provider_name:
                        provider_name = DEFAULT_EPS_BY_DEPT.get(department.name.upper(), f"EPS {department.name}")

                    provider, _ = Provider.objects.get_or_create(
                        name=provider_name,
                        defaults={
                            "acronym": clean(row.get("Pres_Sigla")),
                            "provider_type": clean(row.get("Pres_Tipo")) or clean(row.get("tipss")) or "EPS",
                            "source_data": {str(k): clean(v) for k, v in row.items() if k != "geometry"},
                        },
                    )
                    external_id = clean(row.get("IDCCPP")) or clean(row.get("id_eps")) or clean(row.get("OBJECTID")) or f"eps-{department.slug}-{source_index:05d}"
                    defaults = {
                        "provider": provider,
                        "system_name": clean(row.get("Pres_Siste")) or clean(row.get("Localidad")) or provider_name,
                        "locality": clean(row.get("Localidad")) or clean(row.get("NOMCCPP")) or department.name,
                        "geometry": geometry_value(row.geometry),
                        "source_data": {str(k): clean(v) for k, v in row.items() if k != "geometry"},
                    }
                    if defaults["geometry"] is None:
                        continue

                    _, was_created = ServiceArea.objects.update_or_create(
                        department=department,
                        external_id=external_id,
                        defaults=defaults,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        self.stdout.write(self.style.SUCCESS(f"EPS {department.name}: {created} creadas, {updated} actualizadas."))

    def import_continuity_points(self, path, department, dry_run=False):
        self.stdout.write(f"Leyendo Puntos de Continuidad: {path}")
        df = pd.read_excel(path)
        created = 0
        updated = 0
        rejected = 0

        if not dry_run:
            with transaction.atomic():
                for row_number, (_, row) in enumerate(df.iterrows(), start=2):
                    geometry = point_value(row)
                    if geometry is None:
                        rejected += 1
                        continue
                    base_key = clean(row.get("ClaveHorario"))
                    external_key = "|".join([
                        base_key, clean(row.get("DiaSemana")), clean(row.get("Hora")), clean(row.get("ServicioPrometido"))
                    ]) or f"row-{row_number}"

                    defaults = {
                        "name": clean(row.get("nombre")),
                        "group": clean(row.get("grupo")),
                        "province_name": clean(row.get("PROVINCIA")),
                        "district_name": clean(row.get("DISTRITO")),
                        "sector": clean(row.get("SECTOR")),
                        "locality": clean(row.get("LOCALIDAD")),
                        "day": clean(row.get("DiaSemana")),
                        "hour": clean(row.get("Hora")),
                        "promised_service": clean(row.get("ServicioPrometido")),
                        "geometry": geometry,
                        "source_data": {str(k): clean(v) for k, v in row.items()},
                    }
                    _, was_created = ContinuityPoint.objects.update_or_create(
                        department=department,
                        external_key=external_key,
                        defaults=defaults,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Puntos de Continuidad {department.name}: {created} creados, {updated} actualizados, {rejected} rechazados."
            )
        )

    def generate_voronoi_areas(self, department, dry_run=False):
        points_qs = ContinuityPoint.objects.filter(department=department)
        count = points_qs.count()
        if count < 3:
            return

        self.stdout.write(f"Generando Voronoi para {department.name} sobre {count} puntos...")
        pts = []
        hours_list = []
        for p in points_qs:
            h = parse_hours(p.hour, p.promised_service)
            if h is not None:
                pts.append(Point(p.geometry.x, p.geometry.y))
                hours_list.append(h)

        if len(pts) < 3:
            return

        gdf_pts = gpd.GeoDataFrame({"hours": hours_list, "geometry": pts}, crs="EPSG:4326")
        
        # Agrupar puntos muy cercanos para no saturar Voronoi
        gdf_pts["geom_wkt"] = gdf_pts.geometry.apply(lambda g: f"{g.x:.4f},{g.y:.4f}")
        grouped = gdf_pts.groupby("geom_wkt").agg({"hours": "mean", "geometry": "first"}).reset_index()
        
        uniq_pts = [g for g in grouped.geometry]
        uniq_hours = grouped["hours"].tolist()

        dept_geom = shapely.from_geojson(department.geometry.geojson)
        if not dept_geom.is_valid:
            dept_geom = shapely.make_valid(dept_geom)

        points_geom = MultiPoint(uniq_pts)
        envelope = dept_geom.envelope.buffer(0.1)
        v_diag = voronoi_diagram(points_geom, envelope=envelope)
        v_polys = list(v_diag.geoms)

        areas_to_create = []
        max_h = max(uniq_hours) if uniq_hours else 24.0
        min_h = min(uniq_hours) if uniq_hours else 0.0

        for pt, h in zip(uniq_pts, uniq_hours):
            matched = None
            for poly in v_polys:
                if poly.contains(pt) or poly.distance(pt) < 1e-6:
                    matched = poly
                    break
            if matched is None:
                continue

            clipped = matched.intersection(dept_geom)
            if clipped.is_empty:
                continue

            poly_2d = force_2d(clipped)
            if poly_2d.geom_type == "Polygon":
                poly_2d = MultiPolygon([poly_2d])
            elif poly_2d.geom_type == "GeometryCollection":
                polys = [g for g in poly_2d.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
                if not polys: continue
                poly_2d = MultiPolygon(polys)
            elif poly_2d.geom_type != "MultiPolygon":
                continue

            geos_geom = GEOSGeometry(json.dumps(mapping(poly_2d)), srid=4326)
            rel_val = (h - min_h) / (max_h - min_h) if max_h > min_h else 0.5

            areas_to_create.append(
                ContinuityArea(
                    department=department,
                    method="VORONOI",
                    average_hours=round(h, 2),
                    relative_value=round(rel_val, 4),
                    geometry=geos_geom,
                    source_data={"horas_promedio": h, "pts_cluster": len(grouped)}
                )
            )

        if not dry_run and areas_to_create:
            with transaction.atomic():
                ContinuityArea.objects.filter(department=department, method="VORONOI").delete()
                ContinuityArea.objects.bulk_create(areas_to_create)
            self.stdout.write(self.style.SUCCESS(f"Voronoi {department.name}: {len(areas_to_create)} áreas generadas."))
