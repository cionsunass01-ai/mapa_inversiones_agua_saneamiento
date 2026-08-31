/**
 * Plataforma Territorial · Inversiones de Agua y Saneamiento
 * Script principal de interacción cartográfica y analítica GIS
 */

const api = (path) => `/api${path}`;

// DOM Elements
const select = document.getElementById("department-select");
const statusMessage = document.getElementById("map-status");
const statusMessageText = document.getElementById("map-status-text");
const detail = document.getElementById("detail");
const summary = document.getElementById("summary");
const statusList = document.getElementById("status-list");
const selectionHeader = document.getElementById("selection-header");
const selectionTitle = document.getElementById("selection-title");
const selectionSubtitle = document.getElementById("selection-subtitle");
const mapInfoDepartment = document.getElementById("map-info-department");
const mapInfoProjects = document.getElementById("map-info-projects");
const mapInfoInvestment = document.getElementById("map-info-investment");
const mapInfoExecuted = document.getElementById("map-info-executed");

// Layer Toggles & Washout
const washoutSlider = document.getElementById("washout-slider");
const washoutVal = document.getElementById("washout-val");
const projectToggle = document.getElementById("project-toggle");
const districtToggle = document.getElementById("district-toggle");
const serviceAreaToggle = document.getElementById("service-area-toggle");
const continuityPointToggle = document.getElementById("continuity-point-toggle");
const continuityAreaToggle = document.getElementById("continuity-area-toggle");
const waterStressToggle = document.getElementById("water-stress-toggle");
const bivariateLegendBox = document.getElementById("bivariate-legend-box");
const ccppToggle = document.getElementById("ccpp-toggle");
const btnFitBounds = document.getElementById("btn-fit-bounds");
const projectFilterContainer = document.getElementById("project-filter-container");
const projectSearchInput = document.getElementById("project-search-input");

// Map Initialization (Default SVG renderer for pixel-accurate polygon click & hover detection)
const map = L.map("map", { 
  zoomControl: true
}).setView([-9.19, -75.01], 6);

// Basemap: MapTiler Custom Vector Map (sunass_inversiones)
const maptilerStyleUrl = "https://api.maptiler.com/maps/01a0457a-7a32-757d-97da-4481f0ebff0e/style.json?key=T0uSC7asFt6CVtV5GbKO";

if (typeof L.maplibreGL === "function") {
  L.maplibreGL({
    style: maptilerStyleUrl,
    attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap</a> · SUNASS'
  }).addTo(map);
} else {
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · SUNASS',
    maxZoom: 19,
    className: "osm-clean-tiles",
  }).addTo(map);
}

// -------------------------------------------------------------
// LEAFLET CUSTOM PANES (Strict Stacking & Visual Hierarchy)
// -------------------------------------------------------------
map.createPane('maskPane');
map.getPane('maskPane').style.zIndex = 380; // Tableau/CARTO Canvas Washout
map.getPane('maskPane').style.pointerEvents = 'none';

map.createPane('districtsPane');
map.getPane('districtsPane').style.zIndex = 400;

map.createPane('waterStressPane');
map.getPane('waterStressPane').style.zIndex = 420; // WRI Aqueduct 4.0 Bivariate Basins

map.createPane('ccppPane');
map.getPane('ccppPane').style.zIndex = 430; // Polígonos de Centros Poblados (siempre interactivos y visibles sobre distritos)

map.createPane('continuityAreasPane');
map.getPane('continuityAreasPane').style.zIndex = 450;

map.createPane('serviceAreasPane');
map.getPane('serviceAreasPane').style.zIndex = 500;

map.createPane('deptBoundaryPane');
map.getPane('deptBoundaryPane').style.zIndex = 550; // Clean department outline
map.getPane('deptBoundaryPane').style.pointerEvents = 'none';

map.createPane('continuityPointsPane');
map.getPane('continuityPointsPane').style.zIndex = 600;

map.createPane('projectsPane');
map.getPane('projectsPane').style.zIndex = 650;

if (map.getPane('tooltipPane')) {
  map.getPane('tooltipPane').style.zIndex = 700; // Tooltips always visible on top!
}

// Tableau / CARTO Style Geographic Mask (Washout)
let currentWashout = 0.85;

let maskLayer = L.geoJSON(null, { 
  pane: 'maskPane',
  interactive: false,
  style: {
    stroke: false,
    fillColor: '#ffffff',
    fillOpacity: currentWashout,
    interactive: false
  }
}).addTo(map);

let deptBoundaryLayer = L.geoJSON(null, { 
  pane: 'deptBoundaryPane',
  interactive: false,
  style: {
    color: '#0284c7',
    weight: 2,
    opacity: 0.85,
    fill: false,
    interactive: false
  }
}).addTo(map);

let districtLayer = L.geoJSON(null, { 
  pane: 'districtsPane',
  style: districtStyle, 
  onEachFeature: onDistrict 
}).addTo(map);

let continuityAreaLayer = L.geoJSON(null, { 
  pane: 'continuityAreasPane',
  style: continuityAreaStyle, 
  onEachFeature: onContinuityArea 
});

let serviceAreaLayer = L.geoJSON(null, { 
  pane: 'serviceAreasPane',
  style: serviceAreaStyle, 
  onEachFeature: onServiceArea 
});

let continuityPointLayer = L.geoJSON(null, { 
  pane: 'continuityPointsPane',
  pointToLayer: continuityPointMarker, 
  onEachFeature: onContinuityPoint 
});

// -------------------------------------------------------------
// CENTROS POBLADOS (POLÍGONOS VECTORIALES)
// -------------------------------------------------------------
function isPointInPolygonRing(point, ring) {
  const x = point[0], y = point[1];
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function isPointInFeatureGeometry(point, geom) {
  if (!point || !geom || !geom.coordinates) return false;
  if (geom.type === "Polygon") {
    if (!isPointInPolygonRing(point, geom.coordinates[0])) return false;
    for (let h = 1; h < geom.coordinates.length; h++) {
      if (isPointInPolygonRing(point, geom.coordinates[h])) return false;
    }
    return true;
  } else if (geom.type === "MultiPolygon") {
    for (let p = 0; p < geom.coordinates.length; p++) {
      const poly = geom.coordinates[p];
      if (isPointInPolygonRing(point, poly[0])) {
        let inHole = false;
        for (let h = 1; h < poly.length; h++) {
          if (isPointInPolygonRing(point, poly[h])) {
            inHole = true;
            break;
          }
        }
        if (!inHole) return true;
      }
    }
  }
  return false;
}

function ccppInvestmentColor(value) {
  if (!value || value <= 0) return "#f8fafc";
  if (!maxCcppInvestment || maxCcppInvestment <= 0) return "#bae6fd";
  const ratio = Math.sqrt(Math.max(0, value) / maxCcppInvestment);
  const index = Math.min(concentrationColors.length - 1, Math.max(1, Math.floor(ratio * concentrationColors.length)));
  return concentrationColors[index];
}

function ccppPolygonStyle(feature) {
  const inv = Number(feature.properties?.total_investment ?? feature.properties?.monto_planificado ?? 0);
  const projs = feature.properties?.total_projects || 0;
  return {
    color: "#0369a1",
    weight: 1.2,
    opacity: 0.75,
    fillColor: projs > 0 && inv > 0 ? ccppInvestmentColor(inv) : "#f8fafc",
    fillOpacity: projs > 0 && inv > 0 ? 0.65 : 0.20
  };
}

let selectedCcppLayer = null;

function onCentroPoblado(feature, layer) {
  const p = feature.properties;
  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 2.8, color: "#0f172a", fillOpacity: 0.85 });
      layer.bringToFront();
    },
    mouseout: () => {
      if (layer === selectedCcppLayer) {
        layer.setStyle({ weight: 3.2, color: "#0f172a", fillOpacity: 0.85 });
      } else {
        ccppLayer.resetStyle(layer);
      }
    },
    click: (e) => {
      L.DomEvent.stopPropagation(e);
      selectCentroPobladoPolygon(feature, layer);
    }
  });

  const agua = p.pvs_agua_red != null ? `${Number(p.pvs_agua_red).toFixed(1)}%` : "—";
  const saneamiento = p.pvs_sin_saneamiento != null ? `${Number(p.pvs_sin_saneamiento).toFixed(1)}%` : "—";
  const invertido = money(p.monto_invertido ?? p.total_executed);
  const planificado = money(p.monto_planificado ?? p.total_investment);
  const projs = p.total_projects || 0;

  const content = `
    <div class="map-tooltip">
      <div class="tooltip-title">
        <span>${escapeHtml(p.name || "Centro Poblado")}</span>
        <span class="badge-status-pill ${projs > 0 ? 'good' : 'muted'}">${projs > 0 ? `${projs} Proy.` : 'CCPP'}</span>
      </div>
      <div class="tooltip-row"><span>Distrito:</span><strong>${escapeHtml(p.district_name || "—")}</strong></div>
      <div class="tooltip-row"><span>Provincia:</span><strong>${escapeHtml(p.province_name || "—")}</strong></div>
      <div class="tooltip-row"><span>Población:</span><strong>${number(p.pob_total)} hab.</strong></div>
      <div class="tooltip-row"><span>Viviendas:</span><strong>${number(p.num_viv)}</strong></div>
      <div class="tooltip-row"><span>Agua Red Pública:</span><strong class="text-primary">${agua}</strong></div>
      <div class="tooltip-row"><span>Sin Saneamiento:</span><strong class="text-danger">${saneamiento}</strong></div>
      <div class="tooltip-row"><span>Monto Invertido:</span><strong class="text-success">${invertido}</strong></div>
      <div class="tooltip-row"><span>Monto Planificado:</span><strong class="text-primary">${planificado}</strong></div>
      <div class="tooltip-click-hint">👆 Haz clic para filtrar y rankear proyectos</div>
    </div>
  `;
  layer.bindTooltip(content, { sticky: true, direction: "top", className: "rich-tooltip" });
}

function selectCentroPobladoPolygon(feature, layer) {
  if (selectedDistrictLayer) {
    districtLayer.resetStyle(selectedDistrictLayer);
    selectedDistrictLayer = null;
  }
  if (selectedCcppLayer && selectedCcppLayer !== layer) {
    ccppLayer.resetStyle(selectedCcppLayer);
  }
  selectedCcppLayer = layer;
  layer.setStyle({ weight: 3.2, color: "#0f172a", fillOpacity: 0.90 });
  layer.bringToFront();

  const p = feature.properties;
  const ccppName = (p.name || "").trim().toLowerCase();
  const districtName = (p.district_name || "").trim().toLowerCase();
  const ccppGeom = feature.geometry;
  const isCapitalOrHomonymous = ccppName.length >= 3 && (ccppName === districtName || districtName.includes(ccppName));

  // Filtrado EXCLUSIVO para este Centro Poblado (Intersección Espacial o Mención Textual Protegida)
  const matchedProjects = currentProjects.filter(item => {
    // 1. Intersección espacial exacta: Coordenada del proyecto dentro del polígono del CCPP
    if (item.geometry && item.geometry.coordinates) {
      const pt = item.geometry.coordinates; // [lon, lat]
      if (isPointInFeatureGeometry(pt, ccppGeom)) {
        return true;
      }
    }
    // 2. Mención textual directa protegida al nombre del Centro Poblado
    if (ccppName.length >= 4) {
      const projName = (item.properties?.name || "").toLowerCase();
      if (isCapitalOrHomonymous) {
        // En capitales distritales homónimas (ej. CP Arancay en Distrito Arancay), 
        // no buscar la palabra suelta porque coincide con "distrito de arancay".
        // Exigir mención explícita a la entidad local o centro poblado:
        const explicitPatterns = [
          `centro poblado de ${ccppName}`,
          `centro poblado ${ccppName}`,
          `c.p. de ${ccppName}`,
          `c.p. ${ccppName}`,
          `cp ${ccppName}`,
          `c.p.m. ${ccppName}`,
          `localidad de ${ccppName}`,
          `localidad ${ccppName}`,
          `ciudad de ${ccppName}`,
          `pueblo de ${ccppName}`,
          `barrio ${ccppName}`,
          `sector ${ccppName}`
        ];
        return explicitPatterns.some(pat => projName.includes(pat));
      } else {
        // En centros poblados rurales / no capitales (ej. Huayllacancha, Querobamba, Huampoy)
        return projName.includes(ccppName);
      }
    }
    return false;
  });

  // Rank / Sort projects strictly by investment cost descending (Mayor a menor inversión)
  matchedProjects.sort((a, b) => Number(b.properties?.updated_cost || 0) - Number(a.properties?.updated_cost || 0));

  const values = matchedProjects.map(proj => proj.properties);
  currentSelectedDistrictProjects = values;

  const ccppStats = {
    projects: values.length,
    total_investment: values.reduce((total, item) => total + Number(item.updated_cost || 0), 0),
    total_executed: values.reduce((total, item) => total + Number(item.executed_budget || 0), 0),
    projects_with_geometry: matchedProjects.filter(proj => proj.geometry).length,
    physical_status: values.reduce((result, item) => {
      const status = item.physical_status || "SIN_ESTADO";
      result[status] = (result[status] || 0) + 1;
      return result;
    }, {}),
  };

  selectionHeader.hidden = false;
  selectionTitle.textContent = `CP: ${p.name}`;
  const agua = p.pvs_agua_red != null ? `${Number(p.pvs_agua_red).toFixed(1)}%` : "—";
  
  if (values.length > 0) {
    selectionSubtitle.textContent = `Distrito: ${p.district_name} · Pob: ${number(p.pob_total)} hab. · Agua: ${agua} · 🏆 ${values.length} proyecto${values.length > 1 ? 's' : ''} en este CCPP`;
  } else {
    selectionSubtitle.textContent = `Distrito: ${p.district_name} · Pob: ${number(p.pob_total)} hab. · Agua: ${agua} · 0 proyectos registrados`;
  }

  if (projectFilterContainer) projectFilterContainer.hidden = values.length === 0;
  if (projectSearchInput) projectSearchInput.value = "";

  updateSummary(ccppStats, values);
  
  if (values.length > 0) {
    renderProjectList(values);
  } else {
    const sinSaneamiento = p.pvs_sin_saneamiento != null ? `${Number(p.pvs_sin_saneamiento).toFixed(1)}%` : "—";
    detail.innerHTML = `
      <div class="empty-state ccpp-empty-card">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" stroke-width="1.8">
          <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
          <polyline points="2 17 12 22 22 17"></polyline>
          <polyline points="2 12 12 17 22 12"></polyline>
        </svg>
        <p class="empty-title">Sin Proyectos en ${escapeHtml(p.name)}</p>
        <p class="empty-desc">No se registran proyectos de inversión pública en agua y saneamiento localizados dentro de este Centro Poblado.</p>
        <div class="ccpp-diagnostico-box">
          <div class="diagnostico-row"><span>Población censal:</span><strong>${number(p.pob_total)} hab.</strong></div>
          <div class="diagnostico-row"><span>Total viviendas:</span><strong>${number(p.num_viv)}</strong></div>
          <div class="diagnostico-row"><span>Cobertura red pública:</span><strong class="text-primary">${agua}</strong></div>
          <div class="diagnostico-row"><span>Déficit saneamiento:</span><strong class="text-danger">${sinSaneamiento}</strong></div>
          <div class="diagnostico-row"><span>Monto invertido:</span><strong class="text-success">${money(p.monto_invertido ?? p.total_executed)}</strong></div>
          <div class="diagnostico-row"><span>Monto planificado:</span><strong class="text-primary">${money(p.monto_planificado ?? p.total_investment)}</strong></div>
        </div>
      </div>
    `;
  }

  // Scroll sidebar smoothly to top
  const sb = document.querySelector('.sidebar') || document.getElementById('sidebar');
  if (sb) sb.scrollTo({ top: 0, behavior: 'smooth' });
}

let ccppLayer = L.geoJSON(null, {
  pane: 'ccppPane',
  style: ccppPolygonStyle,
  onEachFeature: onCentroPoblado
});

// -------------------------------------------------------------
// WRI AQUEDUCT 4.0 BIVARIATE WATER STRESS (4x4 MATRIX)
// -------------------------------------------------------------
const BIVARIATE_4X4_COLORS = {
  // Fila 1: Demanda Baja (D1)
  1:  "#e8e8e8",
  2:  "#b8d6be",
  3:  "#73b3a3",
  4:  "#2a5674",

  // Fila 2: Demanda Media-Baja (D2)
  5:  "#dfb0d6",
  6:  "#b5b0be",
  7:  "#6c94a3",
  8:  "#225474",

  // Fila 3: Demanda Media-Alta (D3)
  9:  "#be64ac",
  10: "#9c64a3",
  11: "#5a648b",
  12: "#1b4c6e",

  // Fila 4: Demanda Muy Alta (D4)
  13: "#8c0172",
  14: "#780172",
  15: "#492664",
  16: "#0f2f55"
};

function getBivariateColor(cls) {
  return BIVARIATE_4X4_COLORS[cls] || "#cbd5e1";
}

function waterStressStyle(feature) {
  const bivar = feature.properties?.bivar_cls || 1;
  return {
    color: "#334155",
    weight: 1.2,
    opacity: 0.65,
    fillColor: getBivariateColor(bivar),
    fillOpacity: 0.55
  };
}

function onWaterStressBasin(feature, layer) {
  const p = feature.properties;
  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 2.5, color: "#ffffff", fillOpacity: 0.85 });
      layer.bringToFront();
    },
    mouseout: () => {
      waterStressLayer.resetStyle(layer);
    },
    click: (e) => {
      L.DomEvent.stopPropagation(e);
    }
  });

  const demandVal = p.demand_val != null ? `${Number(p.demand_val).toFixed(2)} m³/año` : "—";
  const supplyVal = p.supply_val != null ? `${Number(p.supply_val).toFixed(2)} m³/año` : "—";
  const badgeClass = p.bivar_cls === 13 ? "danger" : p.bivar_cls === 4 ? "good" : "warning";
  
  const content = `
    <div class="map-tooltip">
      <div class="tooltip-title">
        <span>${escapeHtml(p.name || `Cuenca ${p.basin_id}`)}</span>
        <span class="badge-status-pill ${badgeClass}">Clase ${p.bivar_cls}/16</span>
      </div>
      <div class="tooltip-row"><span>Diagnóstico 2050:</span><strong>${escapeHtml(p.stress_category || "—")}</strong></div>
      <div class="tooltip-row"><span>Demanda Proyectada (Q${p.demand_cls || 1}):</span><strong>${demandVal}</strong></div>
      <div class="tooltip-row"><span>Oferta / Disponibilidad (Q${p.supply_cls || 1}):</span><strong>${supplyVal}</strong></div>
      <div class="tooltip-row"><span>Modelo:</span><strong>WRI Aqueduct 4.0 (BAU 2050)</strong></div>
    </div>
  `;
  layer.bindTooltip(content, { sticky: true, direction: "top", className: "rich-tooltip" });
}

let waterStressLayer = L.geoJSON(null, { 
  pane: 'waterStressPane',
  style: waterStressStyle, 
  onEachFeature: onWaterStressBasin 
});

let projectLayer = L.layerGroup().addTo(map);

// App State
let departmentStats = { projects: 0 };
let currentProjects = [];
let currentSelectedDistrictProjects = [];
let maxDistrictInvestment = 0;
let maxCcppInvestment = 0;
let selectedDistrictLayer = null;
let currentDepartmentBounds = null;

// Calibrated 6-step Hydro Blue Palette
const concentrationColors = ["#f8fafc", "#e0f2fe", "#bae6fd", "#7dd3fc", "#38bdf8", "#0284c7"];

// Event Listeners for Layer Toggles & Washout Slider
if (washoutSlider) {
  washoutSlider.addEventListener("input", (e) => {
    const val = parseInt(e.target.value, 10);
    currentWashout = val / 100.0;
    if (washoutVal) washoutVal.textContent = `${val}%`;
    
    maskLayer.setStyle({ fillOpacity: currentWashout });
    if (currentWashout === 0) {
      if (map.hasLayer(maskLayer)) map.removeLayer(maskLayer);
      if (map.hasLayer(deptBoundaryLayer)) map.removeLayer(deptBoundaryLayer);
    } else {
      if (!map.hasLayer(maskLayer)) maskLayer.addTo(map);
      if (!map.hasLayer(deptBoundaryLayer)) deptBoundaryLayer.addTo(map);
    }
  });
}

if (waterStressToggle) {
  waterStressToggle.addEventListener("change", () => {
    toggleLayer(waterStressToggle, waterStressLayer);
    if (bivariateLegendBox) {
      bivariateLegendBox.hidden = !waterStressToggle.checked;
    }
  });
}

serviceAreaToggle.addEventListener("change", () => toggleLayer(serviceAreaToggle, serviceAreaLayer));
continuityPointToggle.addEventListener("change", () => toggleLayer(continuityPointToggle, continuityPointLayer));
continuityAreaToggle.addEventListener("change", () => toggleLayer(continuityAreaToggle, continuityAreaLayer));
projectToggle.addEventListener("change", () => toggleLayer(projectToggle, projectLayer));
districtToggle.addEventListener("change", () => toggleLayer(districtToggle, districtLayer));
ccppToggle.addEventListener("change", () => toggleLayer(ccppToggle, ccppLayer));

if (btnFitBounds) {
  btnFitBounds.addEventListener("click", () => {
    if (districtLayer.getLayers().length > 0) {
      map.fitBounds(districtLayer.getBounds(), { padding: [24, 24], animate: true });
    }
  });
}

if (projectSearchInput) {
  projectSearchInput.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase().trim();
    filterAndRenderProjects(query);
  });
}

// -------------------------------------------------------------
// TABLEAU / CARTO STYLE INVERTED MASK GENERATOR
// -------------------------------------------------------------
function createInvertedMask(geometry) {
  if (!geometry || !geometry.coordinates) return null;
  
  const worldOuter = [
    [-180, 90],
    [180, 90],
    [180, -90],
    [-180, -90],
    [-180, 90]
  ];

  let holes = [];
  if (geometry.type === 'Polygon') {
    if (geometry.coordinates[0]) holes.push(geometry.coordinates[0]);
  } else if (geometry.type === 'MultiPolygon') {
    geometry.coordinates.forEach(poly => {
      if (poly && poly[0]) {
        holes.push(poly[0]);
      }
    });
  }

  if (holes.length === 0) return null;

  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'Polygon',
      coordinates: [worldOuter, ...holes]
    }
  };
}

// Formatting Utilities
const money = (value) => {
  if (!value) return "S/ 0";
  const num = Number(value);
  if (num >= 1000000000) return `S/ ${(num / 1000000000).toFixed(2)} mil M`;
  if (num >= 1000000) return `S/ ${(num / 1000000).toFixed(2)} M`;
  if (num >= 1000) return `S/ ${(num / 1000).toFixed(1)} k`;
  return `S/ ${new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 }).format(num)}`;
};

const mapMoney = (value) => {
  const amount = Number(value || 0);
  if (amount >= 1000000000) return `S/ ${(amount / 1000000000).toFixed(2)} mil M`;
  if (amount >= 1000000) return `S/ ${(amount / 1000000).toFixed(2)} M`;
  if (amount >= 1000) return `S/ ${(amount / 1000).toFixed(1)} k`;
  return `S/ ${amount.toFixed(0)}`;
};

const formatDate = (value, fallback = "Sin fecha") => {
  if (!value) return fallback;
  const parts = String(value).split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : String(value);
};

const formatDateTime = (value, fallback = "Sin fecha") => {
  if (!value) return fallback;
  return formatDate(String(value).slice(0, 10), fallback);
};

const number = (value) => new Intl.NumberFormat("es-PE").format(value || 0);

// District Styling & Interactivity
function districtStyle(feature) {
  const projects = feature.properties?.projects || 0;
  const investment = Number(feature.properties?.total_investment || 0);
  return {
    color: "#0369a1",
    weight: 0.8,
    opacity: 0.6,
    fillColor: projects ? investmentColor(investment) : "#f8fafc",
    fillOpacity: projects ? 0.50 : 0.20
  };
}

function investmentColor(value) {
  if (!value || !maxDistrictInvestment) return "#f8fafc";
  const ratio = Math.sqrt(Math.max(0, value) / maxDistrictInvestment);
  const index = Math.min(concentrationColors.length - 1, Math.floor(ratio * concentrationColors.length));
  return concentrationColors[index];
}

function onDistrict(feature, layer) {
  const p = feature.properties;
  const inv = Number(p.total_investment || 0);
  const projs = p.total_projects || 0;
  
  const content = `
    <div class="map-tooltip">
      <div class="tooltip-title">
        <span>${escapeHtml(p.name || "Distrito")}</span>
        <span class="badge-status-pill ${projs > 0 ? 'good' : 'muted'}">${projs} Proy.</span>
      </div>
      <div class="tooltip-row"><span>Provincia:</span><strong>${escapeHtml(p.province_name || p.province || "—")}</strong></div>
      <div class="tooltip-row"><span>UBIGEO:</span><strong>${escapeHtml(p.ubigeo || "—")}</strong></div>
      <div class="tooltip-row"><span>Inversión Total:</span><strong class="text-primary">${money(inv)}</strong></div>
      <div class="tooltip-click-hint" style="color: #0284c7; border-color: rgba(2, 132, 199, 0.3);">👆 Haz clic para filtrar y rankear proyectos distritales</div>
    </div>
  `;
  layer.bindTooltip(content, { sticky: true, direction: "top", className: "rich-tooltip" });

  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 2.5, color: "#0f172a", fillColor: "#38bdf8", fillOpacity: 0.75 });
      layer.bringToFront();
    },
    mouseout: () => {
      if (layer === selectedDistrictLayer) {
        selectedDistrictStyle(layer);
      } else {
        districtLayer.resetStyle(layer);
      }
    },
    click: (e) => {
      L.DomEvent.stopPropagation(e);
      selectDistrict(feature, layer);
    },
  });
}

function selectedDistrictStyle(layer) {
  layer.setStyle({ weight: 3, color: "#0f172a", fillOpacity: 0.80, fillColor: "#0284c7" });
}

// -------------------------------------------------------------
// EPS SERVICE AREAS
// -------------------------------------------------------------
function serviceAreaStyle() {
  return { 
    color: "#0d9488", 
    weight: 1.6, 
    fillColor: "#0d9488", 
    fillOpacity: 0.15, 
    dashArray: "4, 4" 
  };
}

function onServiceArea(feature, layer) {
  const p = feature.properties;
  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 2.5, color: "#042f2e", fillOpacity: 0.30 });
      layer.bringToFront();
    },
    mouseout: () => {
      serviceAreaLayer.resetStyle(layer);
    },
    click: (e) => {
      L.DomEvent.stopPropagation(e);
    }
  });
  const content = `
    <div class="map-tooltip">
      <div class="tooltip-title">
        <span>${escapeHtml(p.provider_name || p.provider || "Ámbito EPS")}</span>
        <span class="badge-status-pill good">EPS</span>
      </div>
      <div class="tooltip-row"><span>Sistema:</span><strong>${escapeHtml(p.system_name || "—")}</strong></div>
      <div class="tooltip-row"><span>Localidad:</span><strong>${escapeHtml(p.locality || "—")}</strong></div>
      <div class="tooltip-row"><span>ID Sector:</span><strong>${escapeHtml(p.external_id || "—")}</strong></div>
    </div>
  `;
  layer.bindTooltip(content, { sticky: true, direction: "top", className: "rich-tooltip" });
}

// -------------------------------------------------------------
// CONTINUITY POINTS
// -------------------------------------------------------------
function continuityPointMarker(feature, latlng) {
  return L.circleMarker(latlng, { 
    pane: 'continuityPointsPane',
    radius: 4, 
    color: "#0f172a", 
    fillColor: "#eab308", 
    fillOpacity: 0.85, 
    weight: 1 
  });
}

function onContinuityPoint(feature, layer) {
  const p = feature.properties;
  layer.on({
    click: (e) => {
      L.DomEvent.stopPropagation(e);
    }
  });
  const content = `
    <div class="map-tooltip">
      <div class="tooltip-title">
        <span>${escapeHtml(p.name || "Punto de Monitoreo")}</span>
        <span class="badge-status-pill warning">${escapeHtml(p.hour || "Continuidad")}</span>
      </div>
      <div class="tooltip-row"><span>Grupo / Sector:</span><strong>${escapeHtml(p.group || p.sector || "—")}</strong></div>
      <div class="tooltip-row"><span>Distrito:</span><strong>${escapeHtml(p.district_name || p.district || "—")}</strong></div>
      <div class="tooltip-row"><span>Localidad:</span><strong>${escapeHtml(p.locality || "—")}</strong></div>
      <div class="tooltip-row"><span>Día / Horario:</span><strong>${escapeHtml(p.day || "—")} ${escapeHtml(p.hour || "")}</strong></div>
      <div class="tooltip-row"><span>Servicio Prometido:</span><strong>${escapeHtml(p.promised_service || "—")}</strong></div>
    </div>
  `;
  layer.bindTooltip(content, { sticky: true, direction: "top", className: "rich-tooltip" });
}

// -------------------------------------------------------------
// CONTINUITY AREAS (VORONOI)
// -------------------------------------------------------------
function continuityColor(val) {
  const num = Number(val || 0);
  if (num >= 0.8) return "#10b981"; // > 19h
  if (num >= 0.6) return "#84cc16"; // 14-19h
  if (num >= 0.4) return "#eab308"; // 9-14h
  if (num >= 0.2) return "#f97316"; // 5-9h
  return "#ef4444"; // 0-5h
}

function continuityAreaStyle(feature) {
  const rel = feature.properties?.relative_value != null ? Number(feature.properties.relative_value) : 0.5;
  return { 
    color: "#334155", 
    weight: 1, 
    opacity: 0.5,
    fillColor: continuityColor(rel), 
    fillOpacity: 0.28 
  };
}

function onContinuityArea(feature, layer) {
  const p = feature.properties;
  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 2, color: "#ffffff", fillOpacity: 0.50 });
      layer.bringToFront();
    },
    mouseout: () => {
      continuityAreaLayer.resetStyle(layer);
    },
    click: (e) => {
      L.DomEvent.stopPropagation(e);
    }
  });
  const hours = p.average_hours != null ? `${p.average_hours} h/día` : "Sin dato";
  const relPercent = p.relative_value != null ? `${(Number(p.relative_value) * 100).toFixed(0)}%` : "—";
  const content = `
    <div class="map-tooltip">
      <div class="tooltip-title">Área de Continuidad (Voronoi)</div>
      <div class="tooltip-row"><span>Prestador EPS:</span><strong>${escapeHtml(p.provider_name || "EPS")}</strong></div>
      <div class="tooltip-row"><span>Horas Promedio:</span><strong class="text-primary">${hours}</strong></div>
      <div class="tooltip-row"><span>Nivel de Continuidad:</span><strong>${relPercent}</strong></div>
      <div class="tooltip-row"><span>Algoritmo:</span><strong>${escapeHtml(p.method || "VORONOI")}</strong></div>
    </div>
  `;
  layer.bindTooltip(content, { sticky: true, direction: "top", className: "rich-tooltip" });
}

function toggleLayer(toggle, layer) {
  if (toggle.checked) layer.addTo(map);
  else map.removeLayer(layer);
}

// -------------------------------------------------------------
// PROJECTS (POINTS)
// -------------------------------------------------------------
function addProjects(collection) {
  const located = collection.features.filter((item) => item.geometry);
  located.forEach((item) => {
    const p = item.properties;
    
    // Tiny jitter to visually separate overlapping points
    const jitterLat = (Math.random() - 0.5) * 0.008;
    const jitterLng = (Math.random() - 0.5) * 0.008;
    
    const marker = L.circleMarker([item.geometry.coordinates[1] + jitterLat, item.geometry.coordinates[0] + jitterLng], {
      pane: 'projectsPane',
      radius: 5.5, 
      color: "#ffffff", 
      weight: 1.5, 
      fillColor: "#f97316", 
      fillOpacity: 0.95,
      className: "project-point-marker"
    });
    
    marker.on("click", (e) => {
      L.DomEvent.stopPropagation(e);
      renderSingleProjectDetail(p);
    });
    
    marker.bindTooltip(projectTooltip(p), {
      sticky: true,
      direction: "top",
      className: "rich-tooltip",
    });
    marker.addTo(projectLayer);
  });
  return located.length;
}

function projectTooltip(project) {
  const progress = project.physical_progress == null ? "Sin reporte" : `${project.physical_progress}%`;
  return `
    <div class="map-tooltip">
      <div class="tooltip-title">
        <span>CUI: ${escapeHtml(project.cui)}</span>
        <span class="badge-status-pill ${getStatusClass(project.physical_status)}">${escapeHtml(project.physical_status || "PENDIENTE")}</span>
      </div>
      <div class="tooltip-name">${escapeHtml(project.name)}</div>
      <div class="tooltip-row"><span>Distrito:</span><strong>${escapeHtml(project.district || "—")}</strong></div>
      <div class="tooltip-row"><span>Inversión:</span><strong>${money(project.updated_cost)}</strong></div>
      <div class="tooltip-row"><span>Ejecutado:</span><strong>${money(project.executed_budget)}</strong></div>
      <div class="tooltip-row"><span>Avance Físico:</span><strong>${progress}</strong></div>
      <div class="tooltip-row"><span>EPS:</span><strong>${escapeHtml(project.provider_name || "Sin EPS identificada")}</strong></div>
    </div>
  `;
}

function getStatusClass(status) {
  if (status === "ACTUALIZADO") return "good";
  if (status === "DESACTUALIZADO") return "warning";
  return "muted";
}

// Summary & KPI updates
function updateSummary(data, districtProjects = null) {
  const districtMode = districtProjects !== null;
  const values = [
    number(data.projects), 
    money(data.total_investment), 
    money(data.total_executed), 
    number(data.projects_with_geometry)
  ];
  
  summary.querySelectorAll("strong").forEach((node, index) => { 
    node.textContent = values[index]; 
  });
  
  statusList.innerHTML = districtMode 
    ? districtStatusCards(districtProjects) 
    : Object.entries(data.physical_status || {}).map(([label, count]) => `
        <div class="status-row">
          <span>${escapeHtml(label)}</span>
          <strong>${number(count)}</strong>
        </div>
      `).join("");
}

function districtStatusCards(projects) {
  const actualizados = projects.filter((item) => item.physical_status === "ACTUALIZADO").length;
  const desactualizados = projects.filter((item) => item.physical_status === "DESACTUALIZADO").length;
  const sinFecha = projects.filter((item) => !item.physical_report_date).length;
  const sinAvance = projects.filter((item) => item.physical_progress == null || item.physical_progress === 0).length;

  return `
    <div class="status-cards">
      <div class="status-card status-good">
        <span>Actualizados</span>
        <strong>${number(actualizados)}</strong>
      </div>
      <div class="status-card status-warning">
        <span>Desactualizados</span>
        <strong>${number(desactualizados)}</strong>
      </div>
      <div class="status-card status-muted">
        <span>Sin Fecha</span>
        <strong>${number(sinFecha)}</strong>
      </div>
      <div class="status-card status-danger">
        <span>Sin Avance</span>
        <strong>${number(sinAvance)}</strong>
      </div>
    </div>
  `;
}

// District selection handling
function selectDistrict(feature, layer) {
  if (selectedCcppLayer) {
    ccppLayer.resetStyle(selectedCcppLayer);
    selectedCcppLayer = null;
  }
  if (selectedDistrictLayer && selectedDistrictLayer !== layer) {
    districtLayer.resetStyle(selectedDistrictLayer);
  }
  selectedDistrictLayer = layer;
  selectedDistrictStyle(layer);
  layer.bringToFront();
  
  const district = feature.properties;
  const targetUbigeo = String(district.ubigeo || feature.id || "").trim();
  const distName = (district.name || "").trim().toLowerCase();

  const rows = currentProjects.filter((project) => {
    const pUbi = String(project.properties?.ubigeo || project.properties?.district || "").trim();
    if (targetUbigeo && pUbi) {
      if (pUbi === targetUbigeo || pUbi.padStart(6, "0") === targetUbigeo.padStart(6, "0")) {
        return true;
      }
    }
    const pDistName = (project.properties?.district_name || "").trim().toLowerCase();
    if (distName && pDistName && distName === pDistName) {
      return true;
    }
    return false;
  });
  
  // Sort projects strictly by investment cost descending (Mayor a menor inversión)
  rows.sort((a, b) => Number(b.properties?.updated_cost || 0) - Number(a.properties?.updated_cost || 0));

  const values = rows.map((project) => project.properties);
  currentSelectedDistrictProjects = values;
  
  const districtStats = {
    projects: values.length,
    total_investment: values.reduce((total, item) => total + Number(item.updated_cost || 0), 0),
    total_executed: values.reduce((total, item) => total + Number(item.executed_budget || 0), 0),
    projects_with_geometry: rows.filter((project) => project.geometry).length,
    physical_status: values.reduce((result, item) => {
      const status = item.physical_status || "SIN_ESTADO";
      result[status] = (result[status] || 0) + 1;
      return result;
    }, {}),
  };
  
  selectionHeader.hidden = false;
  selectionTitle.textContent = `Distrito: ${district.name}`;
  const provText = district.province_name || district.province || "—";
  
  if (values.length > 0) {
    selectionSubtitle.textContent = `Provincia: ${provText} · UBIGEO: ${district.ubigeo} · 🏆 ${values.length} proyecto${values.length > 1 ? 's' : ''} rankeados por inversión`;
  } else {
    selectionSubtitle.textContent = `Provincia: ${provText} · UBIGEO: ${district.ubigeo} · 0 proyectos registrados`;
  }
  
  if (projectFilterContainer) projectFilterContainer.hidden = values.length === 0;
  if (projectSearchInput) projectSearchInput.value = "";
  
  updateSummary(districtStats, values);
  
  if (values.length > 0) {
    renderProjectList(values);
  } else {
    detail.innerHTML = `
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="1.8">
          <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
          <polyline points="2 17 12 22 22 17"></polyline>
          <polyline points="2 12 12 17 22 12"></polyline>
        </svg>
        <p class="empty-title">Sin Proyectos en ${escapeHtml(district.name)}</p>
        <p class="empty-desc">Actualmente no se registran proyectos de inversión pública en agua y saneamiento en el distrito de ${escapeHtml(district.name)} (UBIGEO: ${district.ubigeo}).</p>
      </div>
    `;
  }

  // Scroll sidebar smoothly to top
  const sb = document.querySelector('.sidebar') || document.getElementById('sidebar');
  if (sb) sb.scrollTo({ top: 0, behavior: 'smooth' });
}

function filterAndRenderProjects(query) {
  if (!query) {
    renderProjectList(currentSelectedDistrictProjects);
    return;
  }
  const filtered = currentSelectedDistrictProjects.filter(p => 
    (p.name && p.name.toLowerCase().includes(query)) ||
    (p.cui && String(p.cui).toLowerCase().includes(query))
  );
  renderProjectList(filtered);
}

function renderProjectList(projects) {
  if (!projects || projects.length === 0) {
    detail.innerHTML = '<div class="empty-state"><p class="empty-desc">No se encontraron proyectos para este criterio de búsqueda.</p></div>';
    return;
  }
  detail.innerHTML = `
    <div class="project-list-wrapper">
      ${projects.map((p, idx) => projectCard(p, idx)).join("")}
    </div>
  `;
}

function projectCard(project, index = null) {
  const physicalNum = project.physical_progress != null ? Math.min(100, Math.max(0, parseFloat(project.physical_progress))) : 0;
  const statusClass = getStatusClass(project.physical_status);
  const fillClass = statusClass === "good" ? "fill-emerald" : statusClass === "warning" ? "fill-amber" : "fill-slate";
  const start = formatDate(project.start_date, "Sin inicio");
  const end = formatDate(project.end_date, "Sin fin");

  const y0 = money(project.programmed_year_0);
  const y1 = money(project.programmed_year_1);
  const y2 = money(project.programmed_year_2);
  const y3 = money(project.programmed_year_3);

  let rankBadge = "";
  if (index !== null) {
    const rankNum = index + 1;
    const rankClass = rankNum === 1 ? "rank-top-1" : rankNum === 2 ? "rank-top-2" : rankNum === 3 ? "rank-top-3" : "";
    rankBadge = `<span class="rank-badge ${rankClass}" title="Ranking #${rankNum} por costo de inversión">#${rankNum}</span>`;
  }

  const hasGps = project.has_gps !== false && (project.has_gps === true || (project.geometry && project.geometry.coordinates));
  const geoBadge = hasGps 
    ? `<span class="geo-badge geo-badge-gps" title="Proyecto con coordenadas georreferenciadas en el MEF (Punto en mapa)">📍 Geolocalizado</span>`
    : `<span class="geo-badge geo-badge-nogps" title="Este proyecto no tiene coordenadas GPS en la base oficial del MEF (Asignado por UBIGEO)">🏷️ Sin coordenadas GPS</span>`;

  return `
    <article class="project-card">
      <div class="project-card-header">
        <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
          ${rankBadge}
          <span class="cui-chip" onclick="copyCUI('${escapeHtml(project.cui)}', this)" title="Clic para copiar CUI">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            CUI: ${escapeHtml(project.cui)}
          </span>
          ${geoBadge}
        </div>
        <span class="badge-status-pill ${statusClass}">
          ${escapeHtml(project.physical_status || "Sin estado")}
        </span>
      </div>

      <h4 class="project-title">${escapeHtml(project.name)}</h4>

      <div class="progress-container">
        <div class="progress-header">
          <span>Avance Físico</span>
          <strong>${project.physical_progress != null ? `${project.physical_progress}%` : 'Sin reporte'}</strong>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${fillClass}" style="width: ${physicalNum}%"></div>
        </div>
      </div>

      <div class="timeline-pills">
        <div class="timeline-pill">
          <span class="timeline-pill-year">Año 0</span>
          <span class="timeline-pill-val">${y0}</span>
        </div>
        <div class="timeline-pill">
          <span class="timeline-pill-year">Año 1</span>
          <span class="timeline-pill-val">${y1}</span>
        </div>
        <div class="timeline-pill">
          <span class="timeline-pill-year">Año 2</span>
          <span class="timeline-pill-val">${y2}</span>
        </div>
        <div class="timeline-pill">
          <span class="timeline-pill-year">Año 3</span>
          <span class="timeline-pill-val">${y3}</span>
        </div>
      </div>

      <div class="project-details-grid">
        <div><b>Inversión:</b> ${money(project.updated_cost)}</div>
        <div><b>Ejecutado:</b> ${money(project.executed_budget)}</div>
        <div><b>Inicio:</b> ${escapeHtml(start)}</div>
        <div><b>Fin:</b> ${escapeHtml(end)}</div>
        <div style="grid-column: span 2;"><b>EPS:</b> ${escapeHtml(project.provider_name || "Sin EPS asignada")}</div>
      </div>
    </article>
  `;
}

function copyCUI(cui, element) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(cui).then(() => {
      const originalHTML = element.innerHTML;
      element.innerHTML = '<span>¡Copiado!</span>';
      setTimeout(() => { element.innerHTML = originalHTML; }, 1500);
    });
  }
}

function renderSingleProjectDetail(p) {
  detail.innerHTML = `
    <div class="project-list-wrapper">
      ${projectCard(p)}
    </div>
  `;
}

let cachedDepartmentsGeoJSON = null;
let cachedWaterStressGeoJSON = null;

// Load Department Data
async function loadDepartment(slug, updateUrl = true) {
  if (statusMessageText) statusMessageText.textContent = "Cargando departamento...";
  select.disabled = true;
  
  try {
    if (!cachedDepartmentsGeoJSON) {
      cachedDepartmentsGeoJSON = await fetch(api(`/v1/catalogo/departments/`)).then(assertResponse).then((r) => r.json());
    }
    if (!cachedWaterStressGeoJSON) {
      cachedWaterStressGeoJSON = await fetch(api(`/v1/capas/water-stress-basins/`)).then(assertResponse).then((r) => r.json()).catch(() => ({ type: "FeatureCollection", features: [] }));
    }

    const [districts, projects, serviceAreas, continuityPoints, continuityAreas, centrosPoblados] = await Promise.all([
      fetch(api(`/v1/catalogo/districts/?province__department__slug=${slug}`)).then(assertResponse).then((r) => r.json()),
      fetch(api(`/v1/inversiones/projects/?district__province__department__slug=${slug}&limit=1000`)).then(assertResponse).then((r) => r.json()),
      fetch(api(`/v1/capas/service-areas/?department__slug=${slug}`)).then(assertResponse).then((r) => r.json()).catch(() => ({ type: "FeatureCollection", features: [] })),
      fetch(api(`/v1/capas/continuity-points/?department__slug=${slug}`)).then(assertResponse).then((r) => r.json()).catch(() => ({ type: "FeatureCollection", features: [] })),
      fetch(api(`/v1/capas/continuity-areas/?department__slug=${slug}`)).then(assertResponse).then((r) => r.json()).catch(() => ({ type: "FeatureCollection", features: [] })),
      fetch(api(`/v1/capas/centros-poblados/?department__slug=${slug}`)).then(assertResponse).then((r) => r.json()).catch(() => ({ type: "FeatureCollection", features: [] })),
    ]);
    
    const departmentFeature = cachedDepartmentsGeoJSON.features 
      ? cachedDepartmentsGeoJSON.features.find((f) => f.properties.slug === slug) 
      : null;
    const department = departmentFeature ? departmentFeature.properties : (cachedDepartmentsGeoJSON.results?.find((item) => item.slug === slug) || null);
    if (!department) throw new Error("Departamento no encontrado");
    
    const stats = {
      projects: department.total_projects || projects.length || projects.features?.length || 0,
      total_investment: department.total_investment || 0,
      total_executed: 0,
      projects_with_geometry: projects.features?.filter(p => p.geometry).length || 0
    };
    
    departmentStats = stats;
    currentProjects = projects.features || [];
    selectionHeader.hidden = true;
    if (projectFilterContainer) projectFilterContainer.hidden = true;
    if (selectedCcppLayer) {
      selectedCcppLayer = null;
    }
    
    detail.innerHTML = `
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
          <line x1="8" y1="2" x2="8" y2="18"></line>
          <line x1="16" y1="6" x2="16" y2="22"></line>
        </svg>
        <p class="empty-title">Exploración Territorial</p>
        <p class="empty-desc">Haz clic en un distrito, polígono de centro poblado o proyecto en el mapa para inspeccionar sus costos, avance de obra y programación multianual.</p>
      </div>
    `;
    
    selectedDistrictLayer = null;
    maxDistrictInvestment = Math.max(0, ...(districts.features || []).map((item) => Number(item.properties?.total_investment || 0)));
    maxCcppInvestment = Math.max(0, ...(centrosPoblados.features || []).map((item) => Number(item.properties?.total_investment || item.properties?.monto_planificado || 0)));
    
    // ---------------------------------------------------------
    // TABLEAU / CARTO STYLE WASHOUT MASK & OUTLINE
    // ---------------------------------------------------------
    maskLayer.clearLayers();
    deptBoundaryLayer.clearLayers();
    
    const deptGeom = departmentFeature ? departmentFeature.geometry : null;
    if (deptGeom) {
      const invertedMask = createInvertedMask(deptGeom);
      if (invertedMask) {
        maskLayer.addData(invertedMask);
        maskLayer.setStyle({ fillOpacity: currentWashout });
      }
      deptBoundaryLayer.addData(departmentFeature);
    }
    
    districtLayer.clearLayers().addData(districts);
    projectLayer.clearLayers();
    const locatedCount = addProjects(projects);
    serviceAreaLayer.clearLayers().addData(serviceAreas);
    continuityPointLayer.clearLayers().addData(continuityPoints);
    continuityAreaLayer.clearLayers().addData(continuityAreas);
    
    if (cachedWaterStressGeoJSON && waterStressLayer.getLayers().length === 0) {
      waterStressLayer.clearLayers().addData(cachedWaterStressGeoJSON);
    }
    
    ccppLayer.clearLayers().addData(centrosPoblados);
    
    toggleLayer(projectToggle, projectLayer);
    toggleLayer(districtToggle, districtLayer);
    toggleLayer(serviceAreaToggle, serviceAreaLayer);
    toggleLayer(continuityPointToggle, continuityPointLayer);
    toggleLayer(continuityAreaToggle, continuityAreaLayer);
    toggleLayer(ccppToggle, ccppLayer);
    if (waterStressToggle) {
      toggleLayer(waterStressToggle, waterStressLayer);
      if (bivariateLegendBox) bivariateLegendBox.hidden = !waterStressToggle.checked;
    }
    
    updateSummary(stats);
    updateMapInfo(department, stats);
    
    if (districtLayer.getLayers().length > 0) {
      currentDepartmentBounds = districtLayer.getBounds();
      map.fitBounds(currentDepartmentBounds, { padding: [24, 24], animate: true });
    } else if (department.center) {
      map.setView([department.center.lat, department.center.lon], department.initial_zoom || 7);
    }
    
    if (statusMessageText) {
      statusMessageText.textContent = `${department.name}: ${number(stats.projects)} proyectos · ${number(locatedCount)} ubicados`;
    }
    
    if (updateUrl) history.replaceState(null, "", `?departamento=${encodeURIComponent(slug)}`);
  } catch (error) {
    if (statusMessageText) statusMessageText.textContent = "Error al sincronizar capas.";
    detail.textContent = error.message;
  } finally {
    select.disabled = false;
  }
}

function updateMapInfo(department, stats) {
  mapInfoDepartment.textContent = department.name.charAt(0) + department.name.slice(1).toLowerCase();
  mapInfoProjects.textContent = number(stats.projects);
  mapInfoInvestment.textContent = mapMoney(stats.total_investment);
  mapInfoExecuted.textContent = mapMoney(stats.total_executed);
}

// App Bootstrap
async function init() {
  const [deptData, basinData] = await Promise.all([
    fetch(api("/v1/catalogo/departments/")).then(assertResponse).then((r) => r.json()),
    fetch(api("/v1/capas/water-stress-basins/")).then(assertResponse).then((r) => r.json()).catch(() => ({ type: "FeatureCollection", features: [] }))
  ]);
  
  cachedDepartmentsGeoJSON = deptData;
  cachedWaterStressGeoJSON = basinData;
  
  const results = deptData.results || deptData.features.map(f => f.properties);
  select.innerHTML = results.map((item) => `<option value="${item.slug}">${escapeHtml(item.name)}</option>`).join("");
  
  const requested = new URLSearchParams(location.search).get("departamento");
  const initial = results.some((item) => item.slug === requested) ? requested : results[0]?.slug;
  select.value = initial;
  select.addEventListener("change", () => loadDepartment(select.value));
  
  if (initial) await loadDepartment(initial, false);
}

function assertResponse(response) {
  if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
  return response;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

init().catch((error) => { 
  if (statusMessageText) statusMessageText.textContent = "No se pudo inicializar la plataforma."; 
  detail.textContent = error.message; 
});
