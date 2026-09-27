"""
Change detection pipeline (reproduces the QGIS Raster Calculator steps).

Inputs : data informe/qgis/aligned/*.tif  (Sentinel-2 L2A, EPSG:9377, 10 m, aligned)
Outputs: data informe/qgis/results/*.tif, landslides.gpkg, stats.json

Steps
 1. Decode SCL (Sentinel Hub RGB visualization) -> classes; clear = not {0,3,8,9,10}
 2. valid = clear_t1 * clear_t2 (inside AOI)
 3. NDVI t1, t2; dNDVI = t2 - t1 ; dNIR = B08_t2 - B08_t1
 4. Threshold: loss = dNDVI < mu - 2 sigma  (and NDVI_t1 >= 0.5 -> vegetated before)
 5. Sieve (min 10 px = 0.1 ha, 8-connectivity) -> polygonize -> area (ha)
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from scipy import ndimage
from shapely.geometry import shape
import pyogrio
import pandas as pd

BASE = Path(__file__).resolve().parents[1] / "qgis"
IN = BASE / "aligned"
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)
NODATA = -9999.0

# Sentinel Hub SCL palette (0-255)
PALETTE = {
    0: (0, 0, 0), 1: (255, 0, 0), 2: (47, 47, 47), 3: (100, 50, 0), 4: (0, 160, 0),
    5: (255, 230, 90), 6: (0, 0, 255), 7: (128, 128, 128), 8: (192, 192, 192),
    9: (255, 255, 255), 10: (100, 200, 255), 11: (255, 150, 255),
}
BAD = [0, 3, 8, 9, 10]


def band(name):
    with rasterio.open(IN / f"{name}.tif") as s:
        return s.read(1).astype("float32")


def scl_classes(t):
    with rasterio.open(IN / f"{t}_Scene_classification_map.tif") as s:
        rgb = np.round(s.read() * 255).astype(int)
    outside = (rgb[0] == 2) & (rgb[1] == 0) & (rgb[2] == 0)  # clip fill value
    cls = np.full(rgb.shape[1:], 255, dtype="uint8")
    for k, (r, g, b) in PALETTE.items():
        cls[(rgb[0] == r) & (rgb[1] == g) & (rgb[2] == b)] = k
    cls[outside] = 255
    return cls, ~outside


with rasterio.open(IN / "t1_B04.tif") as ref:
    profile = ref.profile
    transform = ref.transform
profile.update(dtype="float32", nodata=NODATA, count=1, compress="deflate")


def save(name, arr, dtype="float32", nodata=NODATA):
    p = profile.copy()
    p.update(dtype=dtype, nodata=nodata)
    with rasterio.open(OUT / f"{name}.tif", "w", **p) as d:
        d.write(arr.astype(dtype), 1)


scl1, aoi = scl_classes("t1")
scl2, _ = scl_classes("t2")
clear1 = aoi & ~np.isin(scl1, BAD)
clear2 = aoi & ~np.isin(scl2, BAD)
valid = clear1 & clear2

b4_1, b8_1, b4_2, b8_2 = band("t1_B04"), band("t1_B08"), band("t2_B04"), band("t2_B08")
with np.errstate(divide="ignore", invalid="ignore"):
    ndvi1 = (b8_1 - b4_1) / (b8_1 + b4_1)
    ndvi2 = (b8_2 - b4_2) / (b8_2 + b4_2)
dndvi = np.where(valid, ndvi2 - ndvi1, NODATA)
dnir = np.where(valid, b8_2 - b8_1, NODATA)

v = dndvi[valid]
mu, sd = float(v.mean()), float(v.std())
T = mu - 2 * sd
loss_raw = valid & (dndvi < T)
loss_veg = loss_raw & (ndvi1 >= 0.5)

# sieve: remove connected components < 10 px (8-connectivity)
lab, n = ndimage.label(loss_veg, structure=np.ones((3, 3)))
sizes = ndimage.sum(loss_veg, lab, index=np.arange(1, n + 1))
keep = np.zeros(n + 1, bool)
keep[1:] = sizes >= 10
loss = keep[lab]

save("t1_NDVI", np.where(aoi, ndvi1, NODATA))
save("t2_NDVI", np.where(aoi, ndvi2, NODATA))
save("dNDVI", dndvi)
save("dNIR", dnir)
save("valid", np.where(aoi, valid, 255), dtype="uint8", nodata=255)
save("t1_SCL", scl1, dtype="uint8", nodata=255)
save("t2_SCL", scl2, dtype="uint8", nodata=255)
save("loss_sieve", np.where(aoi, loss, 255), dtype="uint8", nodata=255)

# polygonize
geoms = [shape(g) for g, val in features.shapes(loss.astype("uint8"), mask=loss, transform=transform, connectivity=8) if val == 1]
areas = np.array([g.area / 10000 for g in geoms])
import geopandas  # noqa: E402  (only for writing)
gdf = geopandas.GeoDataFrame({"id": np.arange(1, len(geoms) + 1), "area_ha": areas}, geometry=geoms, crs="EPSG:9377")
gpkg = OUT / "landslides.gpkg"
if gpkg.exists():
    gpkg.unlink()
gdf.to_file(gpkg, layer="landslides", driver="GPKG")

px_ha = 0.01
stats = {
    "aoi_px": int(aoi.sum()), "aoi_km2": aoi.sum() * px_ha / 100,
    "valid_pct": 100 * valid.sum() / aoi.sum(),
    "masked_t1_pct": 100 * (aoi & ~clear1).sum() / aoi.sum(),
    "masked_t2_pct": 100 * (aoi & ~clear2).sum() / aoi.sum(),
    "scl_t1_pct": {int(k): 100 * float((scl1[aoi] == k).mean()) for k in np.unique(scl1[aoi])},
    "scl_t2_pct": {int(k): 100 * float((scl2[aoi] == k).mean()) for k in np.unique(scl2[aoi])},
    "ndvi_t1_mean": float(np.nanmean(ndvi1[valid])), "ndvi_t2_mean": float(np.nanmean(ndvi2[valid])),
    "ndvi_t1_forest": float(np.nanmedian(ndvi1[valid & (scl1 == 4)])),
    "ndvi_t2_forest": float(np.nanmedian(ndvi2[valid & (scl2 == 4)])),
    "dndvi_mean": mu, "dndvi_std": sd, "dndvi_min": float(v.min()), "dndvi_max": float(v.max()),
    "threshold": T,
    "dnir_mean": float(dnir[valid].mean()), "dnir_std": float(dnir[valid].std()),
    "loss_raw_ha": loss_raw.sum() * px_ha, "loss_veg_ha": loss_veg.sum() * px_ha,
    "loss_sieve_ha": loss.sum() * px_ha,
    "n_polygons": len(geoms), "area_total_ha": float(areas.sum()),
    "area_mean_ha": float(areas.mean()) if len(areas) else 0, "area_max_ha": float(areas.max()) if len(areas) else 0,
    "area_median_ha": float(np.median(areas)) if len(areas) else 0,
    "pct_aoi_affected": 100 * loss.sum() / aoi.sum(),
    "dndvi_in_landslides_mean": float(dndvi[loss].mean()),
    "ndvi_t1_in_landslides": float(ndvi1[loss].mean()), "ndvi_t2_in_landslides": float(ndvi2[loss].mean()),
    "size_classes": {
        "0.1-0.5 ha": int(((areas >= 0.1) & (areas < 0.5)).sum()),
        "0.5-1 ha": int(((areas >= 0.5) & (areas < 1)).sum()),
        "1-5 ha": int(((areas >= 1) & (areas < 5)).sum()),
        ">=5 ha": int((areas >= 5).sum()),
    },
}
(OUT / "stats.json").write_text(json.dumps(stats, indent=2))
print(json.dumps(stats, indent=2))
