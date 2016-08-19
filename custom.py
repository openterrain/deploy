import re
from StringIO import StringIO

from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from PIL import Image
import rasterio

from openterrain import MAX_ZOOM, render_hillshade, Tile

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

DARKMATTER_RAMP = {
    "red": [(0.0, 60 / 255.0, 60 / 255.0),
            (1.0, 220 / 255.0, 220 / 255.0)],
    "green": [(0.0, 75 / 255.0, 75 / 255.0),
              (1.0, 1.0, 1.0)],
    "blue": [(0.0, 80 / 255.0, 80 / 255.0),
             (1.0, 100 / 255.0, 100 / 255.0)],
    "alpha": [(0.0, 0.4, 0.4),
              (180 / 255.0, 0.0, 0.0),
              (1.0, 0.2, 0.2)]
}

DARKMATTER = LinearSegmentedColormap("darkmatter", DARKMATTER_RAMP)


def main():
    meta = {}
    data = render_hillshade(Tile(653, 1581, 12), src_meta=meta, resample=True)

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

    with rasterio.open("hillshade_combined_resampled.tif", "w", **meta) as tmp:
        tmp.write(data, 1)

    plt.imsave(
        "darkmatter_combined_resampled.png",
        data,
        cmap=DARKMATTER,
        vmin=0,
        vmax=255,
        format="png",
    )

    plt.imsave(
        "positron_combined_resampled.png",
        data,
        cmap=POSITRON,
        vmin=0,
        vmax=255,
        format="png",
    )

def handle(event):
    zoom = int(event["params"]["path"]["z"])
    x = int(event["params"]["path"]["x"])
    filename, format = event["params"]["path"]["y"].split(".")

    parts = filename.split("@")
    y = int(parts[0])
    if len(parts) > 1:
        scale = int(re.sub(r"[^\d]", "", parts[1]))
    else:
        scale = 1

    tile = Tile(x, y, zoom)

    if format != "png":
        raise Exception("Invalid format")

    if not 0 <= tile.z <= MAX_ZOOM:
        raise Exception("Invalid zoom")

    if not 0 < scale <= 2:
        raise Exception("Invalid scale")

    if not 0 <= tile.x < 2**tile.z:
        raise Exception("Invalid coordinates")

    if not 0 <= tile.y < 2**tile.z:
        raise Exception("Invalid coordinates")

    hs = render_hillshade(tile, resample=True)

    out = StringIO()
    plt.imsave(
        out,
        hs,
        cmap=POSITRON,
        # cmap=plt.get_cmap("Accent"), # use a default coloramp
        vmin=0,
        vmax=255,
        format=format,
    )

    if scale == 1:
        im = Image.open(out)
        im.thumbnail((256, 256), Image.ANTIALIAS)
        out = StringIO()
        im.save(out, format)

    return out.getvalue()


if __name__ == "__main__":
    main()
