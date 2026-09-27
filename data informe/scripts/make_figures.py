"""Thematic maps / figures for the report (EPSG:9377)."""
import json
from pathlib import Path

import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
from matplotlib.colors import ListedColormap
import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import shape, Point, box

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "qgis" / "aligned"
RES = ROOT / "qgis" / "results"
FIG = ROOT.parents[0] / "EDT" / "Classes" / "Class06" / "informe" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
COL = ROOT / "datasets" / "colombia.gpkg"  # limites de Colombia (no incluido en el repo)
stats = json.loads((RES / "stats.json").read_text())

with rasterio.open(IN / "t1_B04.tif") as s:
    T = s.transform
    H, W = s.shape
    B = s.bounds
EXT = [B.left, B.right, B.bottom, B.top]
to9377 = Transformer.from_crs(4326, 9377, always_xy=True)
TOWN = to9377.transform(-76.2336, 4.9010)
EPI = (-76.23, 4.90)  # approx. epicentre (SGC) - San José del Palmar

roi = gpd.read_file(ROOT / "roi_palmar.geojson").set_crs(4326, allow_override=True).to_crs(9377)
slides = gpd.read_file(RES / "landslides.gpkg")


def rd(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float32")
        nd = s.nodata
    if nd is not None:
        a[a == nd] = np.nan
    return a


def rgb(t, bands=("B04", "B03", "B02"), pmin=2, pmax=98):
    arr = np.dstack([rd(IN / f"{t}_{b}.tif") for b in bands])
    aoi = arr.sum(axis=2) > 0
    out = np.zeros_like(arr)
    for i in range(3):
        v = arr[..., i][aoi]
        lo, hi = np.percentile(v, pmin), np.percentile(v, pmax)
        out[..., i] = np.clip((arr[..., i] - lo) / (hi - lo), 0, 1)
    out = np.dstack([out, aoi.astype("float32")])
    return out


def decorate(ax, title, extent=EXT, sb=2000):
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Este (m) – EPSG:9377", fontsize=8)
    ax.set_ylabel("Norte (m)", fontsize=8)
    for lab in ax.get_yticklabels():
        lab.set_rotation(90); lab.set_va("center")
    # north arrow
    ax.annotate("N", xy=(0.95, 0.93), xytext=(0.95, 0.80), xycoords="axes fraction",
                ha="center", va="center", fontsize=11, fontweight="bold",
                arrowprops=dict(facecolor="black", width=4, headwidth=11))
    # scale bar
    x0 = extent[0] + 0.05 * (extent[1] - extent[0]); y0 = extent[2] + 0.06 * (extent[3] - extent[2])
    ax.add_patch(Rectangle((x0, y0), sb / 2, (extent[3] - extent[2]) * 0.012, fc="black", ec="black"))
    ax.add_patch(Rectangle((x0 + sb / 2, y0), sb / 2, (extent[3] - extent[2]) * 0.012, fc="white", ec="black"))
    ax.text(x0, y0 + (extent[3] - extent[2]) * 0.025, "0", fontsize=7, ha="center")
    ax.text(x0 + sb, y0 + (extent[3] - extent[2]) * 0.025, f"{sb/1000:g} km", fontsize=7, ha="center")
    ax.set_facecolor("#f2f2f2")
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(4)); ax.yaxis.set_major_locator(MaxNLocator(4))


def town(ax):
    ax.plot(*TOWN, marker="s", ms=5, mec="black", mfc="yellow")
    ax.text(TOWN[0] + 150, TOWN[1] + 150, "San José\ndel Palmar", fontsize=7, fontweight="bold",
            color="black", bbox=dict(fc="white", alpha=0.7, lw=0, pad=1))


def outline(ax, color="black"):
    roi.boundary.plot(ax=ax, color=color, lw=1)


SRC = "Datos: Copernicus Sentinel-2 L2A (ESA). Procesamiento: QGIS."


def finish(fig, name):
    fig.text(0.01, 0.005, SRC, fontsize=6, color="gray")
    fig.savefig(FIG / name.replace(".png", ".jpg"), dpi=150, bbox_inches="tight", pil_kwargs={"quality": 85})
    plt.close(fig)
    print("saved", name)


# --- true / false colour ---
for t, d in [("t1", "24 jul 2026"), ("t2", "18 ago 2026")]:
    fig, ax = plt.subplots(figsize=(8, 5.6))
    ax.imshow(rgb(t), extent=EXT)
    outline(ax, "yellow"); town(ax)
    decorate(ax, f"Color verdadero (B4-B3-B2) – {'t1 (antes)' if t=='t1' else 't2 (después)'}: {d}")
    finish(fig, f"fig_{t}_truecolor.png")
    fig, ax = plt.subplots(figsize=(8, 5.6))
    ax.imshow(rgb(t, ("B08", "B04", "B03")), extent=EXT)
    outline(ax, "yellow"); town(ax)
    decorate(ax, f"Falso color (B8-B4-B3) – {d}")
    finish(fig, f"fig_{t}_falsecolor.png")

# --- NDVI ---
for t, d in [("t1", "24 jul 2026"), ("t2", "18 ago 2026")]:
    fig, ax = plt.subplots(figsize=(8, 5.6))
    im = ax.imshow(rd(RES / f"{t}_NDVI.tif"), extent=EXT, cmap="RdYlGn", vmin=0, vmax=1)
    outline(ax); town(ax)
    decorate(ax, f"NDVI – {d}")
    cb = fig.colorbar(im, ax=ax, shrink=0.8); cb.set_label("NDVI")
    finish(fig, f"fig_{t}_ndvi.png")

# --- dNDVI ---
dnd = rd(RES / "dNDVI.tif")
fig, ax = plt.subplots(figsize=(8, 5.6))
im = ax.imshow(dnd, extent=EXT, cmap="RdYlGn", vmin=-0.5, vmax=0.5)
outline(ax); town(ax)
decorate(ax, "ΔNDVI = NDVI(18 ago) − NDVI(24 jul)")
cb = fig.colorbar(im, ax=ax, shrink=0.8, extend="both"); cb.set_label("ΔNDVI  (rojo = pérdida de vegetación)")
finish(fig, "fig_dndvi.png")

# --- dNIR ---
fig, ax = plt.subplots(figsize=(8, 5.6))
im = ax.imshow(rd(RES / "dNIR.tif"), extent=EXT, cmap="RdBu", vmin=-0.2, vmax=0.2)
outline(ax); town(ax)
decorate(ax, "ΔNIR = B08(18 ago) − B08(24 jul)")
cb = fig.colorbar(im, ax=ax, shrink=0.8, extend="both"); cb.set_label("Δ reflectancia (NIR)")
finish(fig, "fig_dnir.png")

# --- mask ---
val = rd(RES / "valid.tif")
fig, ax = plt.subplots(figsize=(8, 5.6))
ax.imshow(val, extent=EXT, cmap=ListedColormap(["#222222", "#e8e8e8"]), vmin=0, vmax=1, interpolation="nearest")
outline(ax, "red"); town(ax)
decorate(ax, f"Máscara de píxeles válidos (SCL) – {stats['valid_pct']:.1f}% de la ROI válido")
ax.legend(handles=[Patch(fc="#e8e8e8", ec="k", label="Despejado en ambas fechas"),
                   Patch(fc="#222222", label="Nube / sombra / cirro / sin dato")], loc="lower right", fontsize=7)
finish(fig, "fig_mask.png")

# --- histogram ---
v = dnd[np.isfinite(dnd)]
fig, ax = plt.subplots(figsize=(7, 3.8))
ax.hist(v, bins=200, range=(-0.6, 0.4), color="#4a7fb5")
ax.axvline(stats["dndvi_mean"], color="k", ls="--", lw=1, label=f"μ = {stats['dndvi_mean']:.3f}")
ax.axvline(stats["threshold"], color="red", lw=1.5, label=f"μ − 2σ = {stats['threshold']:.3f}")
ax.axvline(stats["dndvi_mean"] + 2 * stats["dndvi_std"], color="green", lw=1, ls=":", label=f"μ + 2σ = {stats['dndvi_mean']+2*stats['dndvi_std']:.3f}")
ax.set_yscale("log"); ax.set_xlabel("ΔNDVI"); ax.set_ylabel("Píxeles (log)")
ax.set_title("Histograma de ΔNDVI (píxeles válidos) y umbral de cambio", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
finish(fig, "fig_histogram.png")

# --- landslides over t2 ---
fig, ax = plt.subplots(figsize=(8, 5.6))
ax.imshow(rgb("t2"), extent=EXT)
outline(ax, "yellow")
slides.plot(ax=ax, facecolor="none", edgecolor="red", lw=0.9)
town(ax)
decorate(ax, f"Deslizamientos cosísmicos detectados: {stats['n_polygons']} polígonos, {stats['area_total_ha']:.1f} ha")
ax.legend(handles=[Line2D([], [], color="red", lw=1.5, label="Deslizamiento (ΔNDVI < μ−2σ)"),
                   Line2D([], [], color="yellow", lw=1.5, label="ROI")], loc="lower right", fontsize=7)
finish(fig, "fig_landslides.png")

# --- zoom on largest landslides: before / after / dNDVI ---
big = slides.sort_values("area_ha", ascending=False).iloc[0]
cx, cy = big.geometry.centroid.x, big.geometry.centroid.y
half = 900
ze = [cx - half, cx + half, cy - half, cy + half]
fig, axs = plt.subplots(1, 3, figsize=(13, 4.6))
for ax, img, ttl in [(axs[0], rgb("t1"), "t1 – 24 jul 2026"), (axs[1], rgb("t2"), "t2 – 18 ago 2026")]:
    ax.imshow(img, extent=EXT)
    slides.plot(ax=ax, facecolor="none", edgecolor="red", lw=1) if ax is axs[1] else None
    decorate(ax, ttl, ze, sb=500)
im = axs[2].imshow(dnd, extent=EXT, cmap="RdYlGn", vmin=-0.5, vmax=0.5)
slides.plot(ax=axs[2], facecolor="none", edgecolor="black", lw=0.8)
decorate(axs[2], "ΔNDVI + polígonos detectados", ze, sb=500)
fig.colorbar(im, ax=axs[2], shrink=0.8)
finish(fig, "fig_zoom_largest.png")

# --- co-registration check (zoom on town) ---
ze = [TOWN[0] - 700, TOWN[0] + 700, TOWN[1] - 500, TOWN[1] + 500]
fig, axs = plt.subplots(1, 2, figsize=(11, 4.4))
for ax, t, ttl in [(axs[0], "t1", "t1 – 24 jul 2026"), (axs[1], "t2", "t2 – 18 ago 2026")]:
    ax.imshow(rgb(t), extent=EXT, interpolation="nearest")
    for a in axs:
        pass
    ax.axvline(TOWN[0], color="cyan", lw=0.7); ax.axhline(TOWN[1], color="cyan", lw=0.7)
    decorate(ax, ttl, ze, sb=200)
finish(fig, "fig_coregistration.png")

# --- location map ---
col = gpd.read_file(COL)
fig, axs = plt.subplots(1, 2, figsize=(12, 6), gridspec_kw=dict(width_ratios=[1, 1.2]))
ax = axs[0]
col.plot(ax=ax, color="#f3efe0", edgecolor="#777", lw=0.4)
hl = col[col.NAME_1.isin(["Chocó", "Risaralda", "Valle del Cauca", "Caldas"])]
hl.plot(ax=ax, color="#fbd9a6", edgecolor="#555", lw=0.6)
for _, r in hl.iterrows():
    p = r.geometry.representative_point()
    ax.text(p.x, p.y, r.NAME_1, fontsize=7, ha="center")
ax.plot(*EPI, marker="*", ms=16, mfc="red", mec="k")
ax.add_patch(Rectangle((-77.3, 3.6), 2.4, 2.4, fill=False, ec="blue", lw=1.2))
ax.set_xlim(-80, -66.5); ax.set_ylim(-4.5, 13)
ax.set_title("Colombia – epicentro (★) del sismo Mw 7.4, 10 ago 2026", fontsize=10, fontweight="bold")
ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud"); ax.tick_params(labelsize=7)
ax = axs[1]
col.plot(ax=ax, color="#f3efe0", edgecolor="#555", lw=0.6)
hl.plot(ax=ax, color="#fbd9a6", edgecolor="#555", lw=0.8)
for _, r in hl.iterrows():
    p = r.geometry.representative_point()
    if -77.3 < p.x < -74.9 and 3.6 < p.y < 6.0:
        ax.text(p.x, p.y, r.NAME_1, fontsize=8, ha="center")
cities = {"Pereira": (-75.696, 4.814), "Manizales": (-75.517, 5.068), "Cali": (-76.532, 3.452), "Quibdó": (-76.658, 5.694), "Cartago": (-75.912, 4.747)}
for n, (x, y) in cities.items():
    ax.plot(x, y, "ko", ms=3); ax.text(x + 0.03, y + 0.03, n, fontsize=7)
roi.to_crs(4326).plot(ax=ax, facecolor="none", edgecolor="blue", lw=1.5)
ax.plot(*EPI, marker="*", ms=16, mfc="red", mec="k")
ax.text(EPI[0] - 0.05, EPI[1] + 0.12, "San José del Palmar\n(epicentro, SGC)", fontsize=7, ha="right", fontweight="bold")
ax.set_xlim(-77.3, -74.9); ax.set_ylim(3.3, 6.0)
ax.set_title("Área de estudio (ROI, azul) – Cordillera Occidental", fontsize=10, fontweight="bold")
ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud"); ax.tick_params(labelsize=7)
ax.annotate("N", xy=(0.93, 0.93), xytext=(0.93, 0.80), xycoords="axes fraction", ha="center", fontsize=11,
            fontweight="bold", arrowprops=dict(facecolor="black", width=4, headwidth=11))
fig.text(0.01, 0.005, "Límites: GADM nivel 1 (EPSG:4326). Epicentro: Servicio Geológico Colombiano.", fontsize=6, color="gray")
fig.savefig(FIG / "fig_location.jpg", dpi=150, bbox_inches="tight", pil_kwargs={"quality": 85}); plt.close(fig); print("saved fig_location.png")
