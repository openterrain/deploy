from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import rasterio

from openterrain import render_hillshade, Tile

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


if __name__ == "__main__":
    main()
