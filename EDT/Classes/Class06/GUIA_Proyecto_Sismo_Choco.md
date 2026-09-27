# Guía paso a paso – Proyecto Sismo Chocó / Eje Cafetero (Mw 7.4, 10‑ago‑2026)

> Herramientas (las mismas de los labs): **QGIS 3.x**, CRS **EPSG:9377** (Lab01), Raster Calculator (Lab02),
> plugin **SCP – Semi‑Automatic Classification** (Lab03), Copernicus Data Space (Lab03), Print Layout (Lab01).

## 0. Datos del evento (para la Introducción/ROI)
- Fecha/hora: **10 de agosto de 2026, 12:34 UTC (07:34 hora local)**; Mw 7.4; profundidad ~110 km (intermedia).
- Epicentro: San José del Palmar (Chocó), Cordillera Occidental.
- Impacto: deslizamientos que bloquearon las vías a San José del Palmar; daños urbanos en Pereira, Manizales, Cali.
- Copernicus EMS activó el mapeo **EMSR916** (7 AOIs, AOI02 = Pereira) → **úsalo para validar**.
- Fuentes: SGC (sgc.gov.co/detallesismo/SGC2026pqqmro), USGS, ReliefWeb, CEMS EMSR916.
- Contexto histórico para el storytelling: sismos de profundidad intermedia que ya golpearon el Eje Cafetero:
  23‑nov‑1979 (Mw ~7.2) y Calima 8‑feb‑1995 (Mw ~6.4, daños en Pereira). Verifica cifras antes de citarlas.

## Estrategia recomendada (dos sub‑áreas)
| Sub‑área | Qué detectas | Método principal | Complemento |
|---|---|---|---|
| **A. Cordillera Occidental** (San José del Palmar, Pueblo Rico, El Cairo, Argelia…) | Deslizamientos cosísmicos | **ΔNDVI** + umbral ±2σ + filtro de pendiente | Diferencia de NIR (B08) |
| **B. Pereira** (urbano) | Daño urbano | **Coherencia SAR Sentinel‑1 (pérdida de coherencia)** | Clasificación supervisada t1/t2 + matriz From‑To |

Así cubres las combinaciones que piden: *Índices espectrales + cambio de uso* y *diferenciación de imágenes + cambio de uso*.

---

## FASE 1 – Definición y adquisición de datos

### 1.1 Fechas
> **Elegidas (zona San José del Palmar): t1 = 24‑jul‑2026, t2 = 18‑ago‑2026** (AOI ≈ 44.75 km², cañón del Río Ingará – San José del Palmar; el 10‑ago, 3 h después del sismo, tenía nubes sobre la zona).

- **t1 (antes):** la imagen Sentinel‑2 más limpia entre **jun y el 9 de ago de 2026**.
- **t2 (después):** la imagen más limpia **entre el 11 de agosto y hoy**.
- El Chocó es muy nublado: filtra por nubosidad < 30–40 %; puede que tengas que usar fechas distintas para A y B.
  Justifica la elección en el informe (fechas cercanas y de la misma temporada, para reducir el efecto fenológico).

### 1.2 ROI en GeoPackage
1. `Project > Properties > CRS` → **EPSG:9377**.
2. Carga un mapa base (XYZ Tiles → OpenStreetMap / Google Satellite).
3. `Layer > Create Layer > New GeoPackage Layer…` → archivo `roi.gpkg`, tabla `roi_deslizamientos`, tipo Polygon, EPSG:9377.
   Dibuja el polígono (≈ 30×30 km alrededor del epicentro y de las vías a San José del Palmar).
4. Repite con la tabla `roi_pereira` (casco urbano de Pereira y Dosquebradas).
5. Exporta la ROI como GeoJSON/KML (clic derecho > Export > Save Features As, **EPSG:4326**) para subirla a los portales.
6. Límites municipales: `colombia.gpkg` del Lab01 (departamentos) o GADM nivel 2 / DANE MGN (municipios).

### 1.3 Sentinel‑2 L2A (óptico) – Copernicus Browser (browser.dataspace.copernicus.eu)
1. Inicia sesión → sube tu ROI (icono de subir geometría) → colección **Sentinel‑2 L2A** → rango de fechas → nubosidad.
2. Elige la fecha → **Download > Analytical**:
   - Image format: **TIFF (32‑bit float)**, Resolution: **10 m**, Coordinate system: **UTM 18N (EPSG:32618)** (luego reproyectas a 9377).
   - Layers → *Raw*: **B02, B03, B04, B08, B11, B12, SCL**.
   - Así descargas ya recortado y en reflectancia (0–1) → ahorras horas.
3. Alternativa: el producto completo `.SAFE`. En ese caso, reflectancia = **(DN − 1000) / 10000** (offset de la baseline ≥ 04.00).

### 1.4 Sentinel‑1 (SAR) – para Pereira
**Opción recomendada, sin SNAP: ASF HyP3 (coherencia ya calculada)**
1. Cuenta NASA Earthdata → search.asf.alaska.edu (Vertex).
2. Dataset **Sentinel‑1**, File type **L1 SLC**, dibuja el AOI de Pereira, fechas jul–sep 2026.
3. Usa la misma órbita (mismo *Path/Frame*, misma dirección). Arma dos pares:
   - **Par pre‑evento:** dos SLC antes del 10‑ago (ej. 17‑jul y 29‑jul).
   - **Par co‑evento:** uno antes y otro después (ej. 29‑jul y 22‑ago).
   (Usa la herramienta *Baseline* o *SBAS* de Vertex para ver las fechas disponibles.)
4. Agrega cada par a **On Demand > InSAR GAMMA** (looks 10x2 → 40 m; marca incluir coherencia). Tarda unos minutos a horas.
5. Descarga el zip; el archivo que te interesa es `*_corr.tif` (coherencia 0–1).

**Opción B (más fácil y más débil):** diferencia de retrodispersión VV (GRD) desde Copernicus Browser (Sentinel‑1 GRD, VV, dB), t1 vs t2.

### 1.5 Datos auxiliares
- **DEM Copernicus GLO‑30** (en Copernicus Browser: DEM > Copernicus 30 m, Analytical TIFF) → pendiente.
- **EMSR916** (mapping.emergency.copernicus.eu/activations/EMSR916) → descarga los productos vectoriales (daño en Pereira, deslizamientos) → **datos de referencia para validar**.

---

## FASE 2 – Preprocesamiento

| Requisito | Qué haces en QGIS | Qué escribes en el informe |
|---|---|---|
| Corrección atmosférica | Nada: usas **L2A = BOA** (Sen2Cor) | "Se usaron productos L2A (BOA, Sen2Cor)" |
| Corregistro | `Raster > Align Rasters` (o recortar ambas fechas con la misma máscara y el mismo tamaño de píxel). Verifica en 3–4 puntos (cruces de vías, puentes) activando y desactivando capas | "Desfase < 1 píxel (S2 multitemporal < 0.5 px según ESA); verificación visual en N puntos de control" |
| Remuestreo | B11, B12 y SCL (20 m) → 10 m. SCL con **Nearest neighbour**, bandas con **Bilinear**. La coherencia SAR (40 m) se deja a 40 m, o se remuestrea a 10 m para superponerla | Métodos y resoluciones |
| Máscara de nubes | Banda **SCL** (siguiente paso) | Clases enmascaradas |

### 2.1 Reproyectar y recortar (cada banda y cada fecha)
`Raster > Extraction > Clip Raster by Mask Layer`
- Mask: `roi_deslizamientos` (o `roi_pereira`) · Target CRS: **EPSG:9377** · marca *Set output file resolution*: **10 / 10**
- Resampling: Bilinear (Nearest para SCL) · NoData: −9999.
- Tip: usa *Run as Batch Process* para hacer todas las bandas de una vez.
- Nombra los archivos así: `t1_B04.tif`, `t2_B08.tif`, `t1_SCL.tif`, …

### 2.2 Máscara de nubes (SCL)
Clases de SCL que debes eliminar: 0 NoData, 1 saturado, **3 sombra de nube, 8 nube media, 9 nube alta, 10 cirro**.
Raster Calculator (`Raster > Raster Calculator`), por cada fecha:
```
("t1_SCL@1" != 0) AND ("t1_SCL@1" != 1) AND ("t1_SCL@1" != 3) AND ("t1_SCL@1" != 8) AND ("t1_SCL@1" != 9) AND ("t1_SCL@1" != 10)
```
→ `t1_clear.tif` (1 = despejado). Haz lo mismo para t2 y luego calcula la máscara común:
```
"t1_clear@1" * "t2_clear@1"
```
→ `valid.tif`

---

## FASE 3 – Procesamiento

### 3.1 NDVI y ΔNDVI (deslizamientos)
```
NDVI_t1 = ("t1_B08@1" - "t1_B04@1") / ("t1_B08@1" + "t1_B04@1")
NDVI_t2 = ("t2_B08@1" - "t2_B04@1") / ("t2_B08@1" + "t2_B04@1")
```
Aplica la máscara y deja las nubes como NoData:
```
dNDVI = ("valid@1" = 1) * ("NDVI_t2@1" - "NDVI_t1@1") + ("valid@1" = 0) * (-9999)
```
Luego en Properties > Transparency pon −9999 como NoData (o usa `Raster > Conversion > Translate` con NoData = −9999).
Simbología: *Singleband pseudocolor*, rampa **RdYlGn**, rango −0.6 a 0.6. **Rojo = pérdida de vegetación = posible deslizamiento.**

### 3.2 Diferenciación de imágenes (NIR)
```
dNIR = "t2_B08@1" - "t1_B08@1"
```
(Opcional: diferencia de SWIR `B12`, que aumenta con el suelo desnudo.) Compárala con el ΔNDVI en el informe.

### 3.3 Clasificación supervisada y matriz From‑To (SCP, igual que en el Lab03)
1. SCP > **Band set**: t1 = B02, B03, B04, B08, B11, B12; crea otro band set para t2.
2. Clases (macroclases): 1 Bosque/vegetación densa · 2 Pastos/cultivos · 3 **Suelo desnudo / deslizamiento** · 4 Urbano · 5 Agua · 6 Nube/sombra.
3. ROIs de entrenamiento: ≥ 15–20 polígonos por clase y por fecha (sepáralos de los de validación).
4. Algoritmo: **Random Forest** (o Maximum Likelihood si RF no está disponible en tu versión de SCP). Clasifica t1 y t2.
5. SCP > Postprocessing > **Cross classification** (referencia = t1, clasificación = t2) → raster y **matriz From‑To** (ej. Bosque → Suelo desnudo = deslizamiento).
6. SCP > Postprocessing > **Accuracy** con ROIs de validación → matriz de confusión, OA, **Kappa**.

### 3.4 Coherencia SAR (Pereira)
1. Carga `pre_corr.tif` y `co_corr.tif`, recórtalos con `roi_pereira` (EPSG:9377) y alinéalos (`Align Rasters`).
2. Pérdida de coherencia:
```
dCoh = "pre_corr@1" - "co_corr@1"
```
3. Solo tiene sentido en zonas urbanas (la vegetación siempre pierde coherencia). Limítalo a la clase Urbano de tu clasificación
   o a un polígono del perímetro urbano: `dCoh_urb = "dCoh@1" * ("clasif_t1@1" = 4)`.
4. Valores altos de dCoh en zona urbana → posible daño estructural. Compáralo con los polígonos de daño de EMSR916.

---

## FASE 4 – Postprocesamiento, validación y reporte

### 4.1 Umbral ±2σ
1. `Processing Toolbox > Raster layer statistics` sobre `dNDVI` → anota la media (μ) y la desviación estándar (σ).
2. Pérdida significativa:
```
loss = "dNDVI@1" < (μ - 2*σ)        ← escribe los números
```
3. **Filtro de pendiente** (clave para separar deslizamientos de cosechas o quemas):
   DEM → recórtalo a 9377/10 m → `Raster > Analysis > Slope` → `slope.tif`
```
landslide = ("dNDVI@1" < (μ - 2*σ)) AND ("slope@1" > 15)
```
4. Quita el ruido (sal y pimienta): `Raster > Analysis > Sieve`, umbral 10 píxeles (0.1 ha), conectividad 8.
5. Haz lo mismo con dCoh (μ + 2σ) en Pereira.

### 4.2 Vectorización y estadísticas
1. `Raster > Conversion > Polygonize` → `landslides.gpkg`.
2. `Extract by attribute`: DN = 1.
3. Field Calculator: nuevo campo `area_ha` = `$area / 10000` (EPSG:9377 está en metros).
4. `Vector > Analysis > Basic statistics for fields` → suma de `area_ha`, número de polígonos, tamaño medio/máximo.
5. Por municipio: `Join attributes by location (summary)` con los municipios (sum de `area_ha`, count).
6. Tabla From‑To: la matriz de Cross classification (píxeles × 100 m² / 10 000 = ha).

### 4.3 Validación (matriz de confusión, Kappa y F1)
1. `Processing > Random points inside polygons` → estratificado: 50 puntos dentro de `landslides` y 50 fuera (dentro de la ROI).
2. Exporta a **KML** y ábrelos en **Google Earth Pro** (imágenes históricas). Si Google Earth aún no tiene imagen posterior al
   evento, usa el color verdadero/falso de S2 t2 (10 m), los polígonos del EMSR916 y el inventario del SGC. **Declara esta limitación.**
3. En la tabla de atributos agrega `ref` (1 = deslizamiento real, 0 = no) según tu interpretación, y
   `Sample raster values` sobre `landslide.tif` para obtener `pred`.
4. Matriz 2×2 (TP, FP, FN, TN), en Excel:
   - OA = (TP+TN)/N
   - Precision = TP/(TP+FP), Recall = TP/(TP+FN), **F1 = 2·P·R/(P+R)**
   - p_e = [(TP+FP)(TP+FN) + (FN+TN)(FP+TN)] / N², **Kappa = (OA − p_e)/(1 − p_e)**
5. Para la clasificación: Kappa sale de SCP Accuracy; F1 por clase = 2·UA·PA/(UA+PA) (UA = user's, PA = producer's accuracy).

### 4.4 Mapas (Print Layout, EPSG:9377, grilla en metros, norte, escala, leyenda, fuente)
1. Localización: epicentro + ROIs + municipios.
2. Antes/después en color verdadero (4‑3‑2) y falso color (8‑4‑3) de la zona de deslizamientos.
3. ΔNDVI (RdYlGn).
4. Deslizamientos detectados (polígonos) sobre hillshade/pendiente + vías.
5. Matriz From‑To / clasificación t1 vs t2.
6. Pérdida de coherencia en Pereira + polígonos del EMSR916.

### 4.5 Storytelling / discusión (ideas)
- Sismo de profundidad intermedia (~110 km) → sacudida muy extendida (Chocó, Risaralda, Caldas, Valle).
- Cordillera Occidental: pendientes fuertes, suelos residuales saturados (temporada de lluvias), deforestación en la
  transición Chocó‑Andes → alta susceptibilidad a deslizamientos. Aislamiento de San José del Palmar por vías bloqueadas.
- Pereira/Manizales: amenaza sísmica alta y antecedentes (1979, 1995); construcciones informales en las laderas.
- Limitaciones: nubes en el Chocó, 10 m no resuelve edificios individuales (por eso SAR), ΔNDVI confunde cosechas/quemas
  (por eso el filtro de pendiente), y la validación no tiene imagen VHR posterior al evento.

---

## Checklist entrega parcial (Fases 1–3)
- [ ] Fechas t1/t2 justificadas + tabla de escenas (ID, fecha, nubosidad, sensor)
- [ ] `roi.gpkg` con 2 ROIs en EPSG:9377 + mapa de localización
- [ ] Bandas recortadas y alineadas + máscara SCL
- [ ] NDVI t1, NDVI t2, ΔNDVI, dNIR (figuras)
- [ ] (Si alcanzas) clasificación t1 y t2, y pares de coherencia pedidos en HyP3
- [ ] Informe en `report_template.tex` (secciones Intro, ROI, Metodología Fases 1–3)

## Checklist entrega final (Fases 3–4)
- [ ] Umbral ±2σ + pendiente + sieve → polígonos, área total en ha/km²
- [ ] Matriz From‑To + matriz de confusión, Kappa, F1
- [ ] Pérdida de coherencia en Pereira vs EMSR916
- [ ] 4–6 mapas en el Print Layout, discusión, conclusiones, bibliografía (`references.bib`)
- [ ] ZIP: `.tex` + `.pdf` + figuras + proyecto QGIS (`.qgz`) + slides
