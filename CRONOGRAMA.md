# 📅 Cronograma de Actividades del Proyecto (4 Días)
**Proyecto:** Plataforma Territorial · Mapa de Inversiones de Agua y Saneamiento (SUNASS)  
**Periodo:** 4 días  
**Stack:** Django GeoDjango 4.2 + PostGIS 15 + Leaflet GIS + Docker Compose

---

## 📊 Resumen Ejecutivo por Día

| Día | Fase Principal | Entregables Clave |
| :--- | :--- | :--- |
| **Día 1** | **Infraestructura Base y Catálogo Espacial** | Docker Compose, PostGIS, catálogo territorial (Departamentos, Provincias, Distritos con geometrías WGS84). |
| **Día 2** | **Ingestión e Integración API MEF** | Comando de sincronización API Datos Abiertos MEF, modelo `inversiones_project`, carga de 19,373 proyectos y coordenadas espaciales. |
| **Día 3** | **Capas Sectoriales EPS y Modelado Voronoi** | Ingesta de shapefiles EPS, carga de ~13,440 puntos de continuidad y generación algorítmica de polígonos Voronoi (`ContinuityArea`). |
| **Día 4** | **Frontend UI/UX, Paneles y Cartografía Tableau** | Rediseño con skill `frontend-design`, jerarquía de Leaflet Custom Panes, eventos aislados y máscara de atenuación (*Washout Tableau/CARTO*). |

---

## 🗓️ Detalle Cronológico de Actividades

### 🔹 Día 1: Configuración de Infraestructura y Catálogo Geoespacial
- **Actividad 1.1:** Configuración del entorno de contenedores Docker (`docker-compose.yml`) con servicios `web` (Python 3.11 / GeoDjango) y `db` (PostgreSQL 15 + extensión espacial PostGIS 3.3).
- **Actividad 1.2:** Diseño del modelo de datos territorial en la app `catalogo` (`Department`, `Province`, `District`) con campos `MultiPolygonField` en `EPSG:4326`.
- **Actividad 1.3:** Ingestión de la cartografía base distrital y provincial del Perú (límites oficiales del INEI / UBIGEOs).
- **Actividad 1.4:** Creación de los primeros endpoints REST espaciales con `django-rest-framework-gis` para consultar geometrías en formato GeoJSON.

---

### 🔹 Día 2: Ingestión de Inversiones (API MEF) y Lógica de Negocio
- **Actividad 2.1:** Conexión e integración con la API de Datos Abiertos del MEF (Recurso `f9cc4ba0-931a-4b70-86c9-eacbd8c68596` de Inversiones de Saneamiento).
- **Actividad 2.2:** Creación del comando de importación masiva `import_mef_inversiones.py` con mapeo de 68 variables:
  - Códigos CUI y SNIP.
  - Costo viable y costo actualizado.
  - Presupuesto ejecutado (devengado acumulado y PIM).
  - Programación Multianual de Inversiones (PMI Años 0 a 3).
  - Avance físico (%) y estado de situación.
- **Actividad 2.3:** Geocodificación y asignación espacial:
  - Procesamiento de coordenadas `Point` exactas del MEF (15,216 proyectos).
  - Asignación territorial mediante cruce de código UBIGEO a nivel distrital (19,247 proyectos asignados).
- **Actividad 2.4:** Implementación de paginación GeoJSON personalizada (`CustomGeoJsonPagination`) y optimización de índices espaciales en PostGIS.

---

### 🔹 Día 3: Capas Sectoriales EPS, Puntos de Monitoreo y Voronoi
- **Actividad 3.1:** Estructuración de modelos de prestación en la app `capas` (`Provider`, `ServiceArea`, `ContinuityPoint`, `ContinuityArea`).
- **Actividad 3.2:** Ingestión de Shapefiles de prestadores EPS (`EPS_Arequipa.shp`, `EPS_Puno.shp`, `Periurb_PrestadoresEPS.shp`) para delimitar ámbitos de administración.
- **Actividad 3.3:** Procesamiento de registros de monitoreo horario y dataloggers desde hojas Excel (`Horario Arequipa.xlsx` con 8,904 puntos y `Horario Puno.xlsx` con 4,536 puntos).
- **Actividad 3.4:** Implementación del algoritmo de interpolación espacial de Voronoi:
  - Generación de polígonos con `shapely.ops.voronoi_diagram`.
  - Recorte espacial (*intersection*) contra el límite del departamento.
  - Cálculo del índice relativo de horas promedio de servicio diario (semaforización hídrica).

---

### 🔹 Día 4: Rediseño Frontend, Corrección de Eventos y Cartografía Avanzada
- **Actividad 4.1:** Creación e integración de la skill especializada `frontend-design` (tokens de diseño hídrico, tipografías *Plus Jakarta Sans* y *JetBrains Mono*, layout de 3 columnas).
- **Actividad 4.2:** Corrección de superposición de capas mediante **Leaflet Custom Panes**:
  - Separación en planos Z independientes (`projectsPane`, `continuityPointsPane`, `serviceAreasPane`, `districtsPane`, `maskPane`).
  - Aislamiento de propagación de clics (`L.DomEvent.stopPropagation`), permitiendo interactuar con puntos y áreas sin bloqueo por parte de los distritos.
- **Actividad 4.3:** Implementación de la **Máscara de Atenuación Territorial (*Map Washout & Clipping Mask*)** estilo Tableau/CARTO:
  - Construcción de polígono inverso mundial con recorte del departamento activo.
  - Incorporación del control deslizante en vivo (Slider de Atenuación 0% a 100%) para ajustar la visibilidad del entorno externo.
- **Actividad 4.4:** Implementación de herramientas analíticas de usuario:
  - Buscador y filtrado en tiempo real por CUI / Nombre.
  - Función de copiado rápido de CUI al portapapeles.
  - Tarjetas de KPIs de inversión y reporte de avance físico.
