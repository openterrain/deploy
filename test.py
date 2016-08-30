from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from mercantile import Tile
import rasterio

from openterrain import render_hillshade

POSITRON_RAMP = {
    "red": [(0.0, 0.0, 0.0),
            (1.0, 1.0, 1.0)],
    "green": [(0.0, 0.0, 0.0),
              (1.0, 1.0, 1.0)],
    "blue": [(0.0, 0.0, 0.0),
             (1.0, 1.0, 1.0)],
    "alpha": [(0.0, 1.0, 1.0),
              (180 / 255.0, 0.0, 0.0),
              (1.0, 1.0, 1.0)]
}

POSITRON = LinearSegmentedColormap("positron", POSITRON_RAMP)


meta = {}
hs = render_hillshade(Tile(722, 1579, 12), src_meta=meta, resample_factor=0.8)

meta.update(
    driver="GTiff",
    dtype=rasterio.uint8,
    compress="deflate",
    predictor=1,
    nodata=None,
    tiled=True,
    sparse_ok=True,
    blockxsize=256,
    blockysize=256,
)

with rasterio.open("/tmp/12_722_1579_resampled.tif", "w", **meta) as tmp:
    tmp.write(hs, 1)

plt.imsave(
    "/tmp/12_722_1579_resampled.png",
    hs,
    cmap=POSITRON,
    vmin=0,
    vmax=255,
    format="png",
)

meta = {}
hs = render_hillshade(Tile(722, 1579, 12), src_meta=meta, resample_factor=1.0)

meta.update(
    driver="GTiff",
    dtype=rasterio.uint8,
    compress="deflate",
    predictor=1,
    nodata=None,
    tiled=True,
    sparse_ok=True,
    blockxsize=256,
    blockysize=256,
)

with rasterio.open("/tmp/12_722_1579.tif", "w", **meta) as tmp:
    tmp.write(hs, 1)

plt.imsave(
    "/tmp/12_722_1579.png",
    hs,
    cmap=POSITRON,
    vmin=0,
    vmax=255,
    format="png",
)
