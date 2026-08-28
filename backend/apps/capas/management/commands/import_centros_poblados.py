import json
import urllib.request
from pathlib import Path
import geopandas as gpd
import numpy as np
import shapely
from django.contrib.gis.geos import GEOSGeometry, Point as GeosPoint
from django.core.management.base import BaseCommand
from django.db import transaction
from shapely import force_2d
from shapely.geometry import MultiPolygon, Point, Polygon, mapping
from shapely.ops import voronoi_diagram

from apps.capas.models import CentroPoblado
from apps.catalogo.models import Department, District, Province

def parse_float(v):
    if v is None: return None
    try: return float(v)
    except: return None

def parse_int(v):
    if v is None: return 0
    try: return int(float(v))
    except: return 0

class Command(BaseCommand):
    help = "Descarga y genera los polígonos territoriales de Centros Poblados para los departamentos desde GeoPerú / INEI."

    def add_arguments(self, parser):
        parser.add_argument("--department", type=str, default="", help="Slug del departamento a procesar (ej: arequipa, puno). Si está vacío, procesa todos los activos.")

    def handle(self, *args, **options):
        dept_slug = options.get("department")
        if dept_slug:
            departments = Department.objects.filter(slug=dept_slug)
        else:
            departments = Department.objects.filter(geometry__isnull=False)

        if not departments.exists():
            self.stdout.write(self.style.ERROR("No se encontraron departamentos para procesar."))
            return

        for dept in departments:
            self.process_department(dept)

    def process_department(self, department):
        self.stdout.write(self.style.NOTICE(f"\n=================================================="))
        self.stdout.write(self.style.NOTICE(f"Procesando Centros Poblados para: {department.name}"))
        self.stdout.write(self.style.NOTICE(f"=================================================="))

        provinces = Province.objects.filter(department=department)
        all_features = []

        # 1. Descargar puntos censales de CCPP por provincia desde GeoPerú
        for prov in provinces:
            url = f"https://espacialg.geoperu.gob.pe/geoserver/geoperu/wfs?request=GetFeature&typeName=geoperu:peru_ccpp_mayor_&cql_filter=cod_prov='{prov.code}'&outputFormat=application/json"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    features = data.get("features", [])
                    all_features.extend(features)
                    self.stdout.write(f"  • Prov. {prov.name} ({prov.code}): {len(features)} centros poblados descargados.")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ Error consultando prov {prov.name}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Total CCPP descargados para {department.name}: {len(all_features)}"))

        # Agrupar CCPP por distrito (UBIGEO)
        by_district = {}
        for f in all_features:
            p = f.get("properties", {})
            ubigeo = str(p.get("cod_dist") or "").strip()
            if not ubigeo: continue
            by_district.setdefault(ubigeo, []).append(f)

        districts = District.objects.filter(province__department=department, geometry__isnull=False)
        self.stdout.write(f"Generando polígonos sobre {districts.count()} distritos...")

        total_saved = 0
        with transaction.atomic():
            CentroPoblado.objects.filter(department=department).delete()

            for dist in districts:
                dist_geom = shapely.from_geojson(dist.geometry.geojson)
                if not dist_geom.is_valid:
                    dist_geom = shapely.make_valid(dist_geom)

                ccpp_list = by_district.get(dist.ubigeo, [])
                if not ccpp_list:
                    # Si no hay CCPP específicos de GeoPerú, crear el CCPP Capital Distrital
                    centroid = dist_geom.centroid
                    poly_2d = force_2d(dist_geom)
                    if poly_2d.geom_type == "Polygon":
                        poly_2d = MultiPolygon([poly_2d])

                    geos_geom = GEOSGeometry(json.dumps(mapping(poly_2d)), srid=4326)
                    geos_point = GeosPoint(centroid.x, centroid.y, srid=4326)

                    CentroPoblado.objects.create(
                        cod_ccpp=f"{dist.ubigeo}0001",
                        name=dist.name,
                        department=department,
                        province_name=dist.province.name,
                        district_name=dist.name,
                        district_ubigeo=dist.ubigeo,
                        pob_total=0,
                        num_viv=0,
                        point=geos_point,
                        geometry=geos_geom,
                        source_data={"tipo": "Capital Distrital"}
                    )
                    total_saved += 1
                    continue

                # Extraer puntos válidos dentro del distrito
                valid_ccpp = []
                for item in ccpp_list:
                    geom = item.get("geometry")
                    if not geom or not geom.get("coordinates"): continue
                    coords = geom["coordinates"]
                    pt = Point(coords[0], coords[1])
                    valid_ccpp.append({"feature": item, "point": pt})

                if len(valid_ccpp) == 1:
                    # 1 CCPP en el distrito: asigna el polígono distrital completo
                    item = valid_ccpp[0]
                    p = item["feature"]["properties"]
                    pt = item["point"]

                    poly_2d = force_2d(dist_geom)
                    if poly_2d.geom_type == "Polygon":
                        poly_2d = MultiPolygon([poly_2d])

                    geos_geom = GEOSGeometry(json.dumps(mapping(poly_2d)), srid=4326)
                    geos_point = GeosPoint(pt.x, pt.y, srid=4326)

                    CentroPoblado.objects.create(
                        cod_ccpp=str(p.get("id_ccpp") or p.get("cod_ccpp") or f"{dist.ubigeo}0001"),
                        name=str(p.get("nom_ccpp") or p.get("ccpp") or dist.name),
                        department=department,
                        province_name=str(p.get("nom_prov") or dist.province.name),
                        district_name=str(p.get("nom_dist") or dist.name),
                        district_ubigeo=dist.ubigeo,
                        pob_total=parse_int(p.get("pob_total")),
                        num_viv=parse_int(p.get("num_viv_pa") or p.get("num_hogare")),
                        pvs_agua_red=parse_float(p.get("pvs_agua_r")),
                        pvs_sin_saneamiento=parse_float(p.get("pvs_sh")),
                        point=geos_point,
                        geometry=geos_geom,
                        source_data=p
                    )
                    total_saved += 1
                else:
                    # Múltiples CCPP: Voronoi territorial particionado y recortado al polígono distrital
                    points_geom = shapely.geometry.MultiPoint([c["point"] for c in valid_ccpp])
                    envelope = dist_geom.buffer(0.05).envelope
                    v_diag = voronoi_diagram(points_geom, envelope=envelope)
                    v_polys = list(v_diag.geoms)

                    for item in valid_ccpp:
                        p = item["feature"]["properties"]
                        pt = item["point"]

                        # Encontrar celda Voronoi que contiene a este punto
                        matched_cell = None
                        for v_poly in v_polys:
                            if v_poly.contains(pt) or v_poly.distance(pt) < 1e-6:
                                matched_cell = v_poly
                                break

                        if matched_cell is None:
                            matched_cell = pt.buffer(0.005)

                        # Recortar celda al límite distrital
                        ccpp_poly = matched_cell.intersection(dist_geom)
                        if ccpp_poly.is_empty:
                            ccpp_poly = pt.buffer(0.002).intersection(dist_geom)

                        poly_2d = force_2d(ccpp_poly)
                        if poly_2d.geom_type == "Polygon":
                            poly_2d = MultiPolygon([poly_2d])
                        elif poly_2d.geom_type == "GeometryCollection":
                            polys = [g for g in poly_2d.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
                            if not polys: continue
                            poly_2d = MultiPolygon(polys)
                        elif poly_2d.geom_type != "MultiPolygon":
                            continue

                        geos_geom = GEOSGeometry(json.dumps(mapping(poly_2d)), srid=4326)
                        geos_point = GeosPoint(pt.x, pt.y, srid=4326)

                        CentroPoblado.objects.create(
                            cod_ccpp=str(p.get("id_ccpp") or p.get("cod_ccpp") or f"{dist.ubigeo}{total_saved:04d}"),
                            name=str(p.get("nom_ccpp") or p.get("ccpp") or f"CCPP {dist.name}"),
                            department=department,
                            province_name=str(p.get("nom_prov") or dist.province.name),
                            district_name=str(p.get("nom_dist") or dist.name),
                            district_ubigeo=dist.ubigeo,
                            pob_total=parse_int(p.get("pob_total")),
                            num_viv=parse_int(p.get("num_viv_pa") or p.get("num_hogare")),
                            pvs_agua_red=parse_float(p.get("pvs_agua_r")),
                            pvs_sin_saneamiento=parse_float(p.get("pvs_sh")),
                            point=geos_point,
                            geometry=geos_geom,
                            source_data=p
                        )
                        total_saved += 1

        self.stdout.write(self.style.SUCCESS(f"¡Éxito! Se guardaron {total_saved} polígonos de Centros Poblados para {department.name} en PostGIS."))
