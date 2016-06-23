import copy
from collections import namedtuple
import os
from StringIO import StringIO

import boto3
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio._io import virtual_file_to_buffer

Tile = namedtuple("Tile", "x y z")


RAMP = {
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

COLORMAP = LinearSegmentedColormap("darkmatter", RAMP)
TMP_PATH = "/vsimem/tmp-{}".format(os.getpid())

BUFFER = 2
SRC_TILE_ZOOM = 14
SRC_TILE_WIDTH = 512
SRC_TILE_HEIGHT = 512

DST_TILE_WIDTH = 256
DST_TILE_HEIGHT = 256
DST_BLOCK_SIZE = 256

def hillshade(elevation, azdeg=315, altdeg=45, vert_exag=1, dx=1, dy=1, fraction=1.):
    """
    Calculates the illumination intensity for a surface using the defined
    azimuth and elevation for the light source.
    Imagine an artificial sun placed at infinity in some azimuth and
    elevation position illuminating our surface. The parts of the surface
    that slope toward the sun should brighten while those sides facing away
    should become darker.
    Parameters
    ----------
    elevation : array-like
        A 2d array (or equivalent) of the height values used to generate an
        illumination map
    azdeg : number, optional
        The azimuth (0-360, degrees clockwise from North) of the light
        source. Defaults to 315 degrees (from the northwest).
    altdeg : number, optional
        The altitude (0-90, degrees up from horizontal) of the light
        source.  Defaults to 45 degrees from horizontal.
    vert_exag : number, optional
        The amount to exaggerate the elevation values by when calculating
        illumination. This can be used either to correct for differences in
        units between the x-y coordinate system and the elevation
        coordinate system (e.g. decimal degrees vs meters) or to exaggerate
        or de-emphasize topographic effects.
    dx : number, optional
        The x-spacing (columns) of the input *elevation* grid.
    dy : number, optional
        The y-spacing (rows) of the input *elevation* grid.
    fraction : number, optional
        Increases or decreases the contrast of the hillshade.  Values
        greater than one will cause intermediate values to move closer to
        full illumination or shadow (and clipping any values that move
        beyond 0 or 1). Note that this is not visually or mathematically
        the same as vertical exaggeration.
    Returns
    -------
    intensity : ndarray
        A 2d array of illumination values between 0-1, where 0 is
        completely in shadow and 1 is completely illuminated.
    """
    # Azimuth is in degrees clockwise from North. Convert to radians
    # counterclockwise from East (mathematical notation).
    az = np.radians(90 - azdeg)
    alt = np.radians(altdeg)

    # Because most image and raster GIS data has the first row in the array
    # as the "top" of the image, dy is implicitly negative.  This is
    # consistent to what `imshow` assumes, as well.
    dy = -dy

    # Calculate the intensity from the illumination angle
    dy, dx = np.gradient(vert_exag * elevation, dy, dx)
    # The aspect is defined by the _downhill_ direction, thus the negative
    aspect = np.arctan2(-dy, -dx)
    slope = 0.5 * np.pi - np.arctan(np.hypot(dx, dy))
    intensity = (np.sin(alt) * np.sin(slope) +
                 np.cos(alt) * np.cos(slope) * np.cos(az - aspect))

    # Apply contrast stretch
    # imin, imax = intensity.min(), intensity.max()
    intensity *= fraction

    # Rescale to 0-1, keeping range before contrast stretch
    # If constant slope, keep relative scaling (i.e. flat should be 0.5,
    # fully occluded 0, etc.)
    # if (imax - imin) > 1e-6:
    #     # Strictly speaking, this is incorrect. Negative values should be
    #     # clipped to 0 because they're fully occluded. However, rescaling
    #     # in this manner is consistent with the previous implementation and
    #     # visually appears better than a "hard" clip.
    #     intensity -= imin
    #     intensity /= (imax - imin)
    intensity = np.clip(intensity, 0, 1, intensity)

    return intensity

def handle(event, context):
    print "processing event:", event
    s3 = boto3.resource('s3')
    zoom = int(event["params"]["path"]["z"])
    x = int(event["params"]["path"]["x"])
    y, format = event["params"]["path"]["y"].split(".")
    y = int(y)
    tile = Tile(x, y, zoom)

    # TODO bail if format != "png"

    # calculate these in z14 pixels
    dz = SRC_TILE_ZOOM - tile.z
    x = 2**dz * tile.x
    y = 2**dz * tile.y
    mx = 2**dz * (tile.x + 1)
    my = 2**dz * (tile.y + 1)
    dx = mx - x
    dy = my - y
    top = (2**SRC_TILE_ZOOM * SRC_TILE_HEIGHT) - 1

    print("dz:", dz)
    print("tile.x:", tile.x)
    print("x:", x)
    print("dx:", dx)
    print("tile.y", tile.y)
    print("y:", y)
    print("dy:", dy)

    # y, x (rows, columns)
    window = [
              [
               top - (top - (SRC_TILE_HEIGHT * y)),
               top - (top - ((SRC_TILE_HEIGHT * y) + int(SRC_TILE_HEIGHT * dy)))
              ],
              [
               SRC_TILE_WIDTH * x,
               (SRC_TILE_WIDTH * x) + int(SRC_TILE_WIDTH * dx)
              ]
             ]

    buffered_window = copy.deepcopy(window)

    # buffer so we have neighboring pixels
    buffered_window[0][0] -= BUFFER
    buffered_window[0][1] += BUFFER
    buffered_window[1][0] -= BUFFER
    buffered_window[1][1] += BUFFER

    # TODO use XML @ zoom - 1 (since we can't explicitly load from overviews)
    # OR use decimated reads, per https://github.com/mapbox/rasterio/issues/710
    with rasterio.open("mapzen.xml") as src:
        data = np.empty(shape=(DST_TILE_WIDTH + 2 * BUFFER, DST_TILE_HEIGHT + 2 * BUFFER)).astype(src.profile["dtype"])
        data = src.read(1, out=data, window=buffered_window)
        dx = abs(src.meta["affine"][0])
        dy = abs(src.meta["affine"][4])

        # meta = src.meta.copy()
        # del meta["transform"]
        # meta.update(
        #     driver='GTiff',
        #     height=buffered_window[0][1] - buffered_window[0][0],
        #     width=buffered_window[1][1] - buffered_window[1][0],
        #     affine=src.window_transform(buffered_window),
        # )
        # with rasterio.open("{}_{}_{}_src.tif".format(tile.z, tile.x, tile.y), "w", **meta) as dst:
        #     dst.write(data, 1)

        # filter out negative values
        data[data == src.meta["nodata"]] = 9999
        data[data < 0] = 0
        data[data == 9999] = src.meta["nodata"]

        # meta = src.meta.copy()
        # del meta["transform"]
        # meta.update(
        #     driver='GTiff',
        #     height=buffered_window[0][1] - buffered_window[0][0],
        #     width=buffered_window[1][1] - buffered_window[1][0],
        #     affine=src.window_transform(buffered_window),
        # )
        # with rasterio.open("{}_{}_{}_src_filtered.tif".format(tile.z, tile.x, tile.y), "w", **meta) as dst:
        #     dst.write(data, 1)

        hs = hillshade(data,
            dx=dx,
            dy=dy,
        )
        hs = (255.0 * hs).astype(np.uint8)

        meta = src.meta.copy()
        del meta["transform"]
        meta.update(
            driver='GTiff',
            dtype=rasterio.uint8,
            compress="deflate",
            predictor=1,
            nodata=None,
            tiled=True,
            sparse_ok=True,
            blockxsize=DST_BLOCK_SIZE,
            blockysize=DST_BLOCK_SIZE,
            height=DST_TILE_HEIGHT,
            width=DST_TILE_WIDTH,
            affine=src.window_transform(window)
        )

        # with rasterio.open("{}_{}_{}.tif".format(tile.z, tile.x, tile.y), "w", **meta) as dst:
        #     # ignore the border pixels when writing
        #     dst.write(hs[BUFFER:-BUFFER, BUFFER:-BUFFER], 1)
        with rasterio.open(TMP_PATH, "w", **meta) as tmp:
            tmp.write(hs[BUFFER:-BUFFER, BUFFER:-BUFFER], 1)

        out = StringIO()
        plt.imsave(
            out,
            hs[BUFFER:-BUFFER, BUFFER:-BUFFER],
            cmap=COLORMAP,
            vmin=0,
            vmax=255,
            format=format,
        )

        # TODO make configurable
        bucket = "hillshades.openterrain.org"
        key = "darkmatter/{}/{}/{}.{}".format(tile.z, tile.x, tile.y, format)
        hillshade_key = "3857/{}/{}/{}.tif".format(tile.z, tile.x, tile.y)

        s3.Object(
            bucket,
            hillshade_key,
        ).put(
            Body=bytes(bytearray(virtual_file_to_buffer(TMP_PATH))),
            ACL="public-read",
            ContentType="image/tiff",
            # TODO
            CacheControl="",
            StorageClass="REDUCED_REDUNDANCY",
        )

        s3.Object(
            bucket,
            key,
        ).put(
            Body=out.getvalue(),
            ACL="public-read",
            ContentType="image/{}".format(format),
            # TODO
            CacheControl="",
            StorageClass="REDUCED_REDUNDANCY",
        )

        return {
            "location": "http://{}.s3.amazonaws.com/{}".format(bucket, key)
        }

if __name__ == "__main__":
    # handle({
    #     "params": {
    #         "path": {
    #             "z": "15",
    #             "x": "5252",
    #             "y": "11445.png",
    #         }
    #     }
    # }, None)

    # # Elliot Bay
    # handle({
    #     "params": {
    #         "path": {
    #             "z": "15",
    #             "x": "5244",
    #             "y": "11444.png",
    #         }
    #     }
    # }, None)
    #
    # # improperly tinted?
    # # 15/5244/11446.png
    # handle({
    #     "params": {
    #         "path": {
    #             "z": "15",
    #             "x": "5244",
    #             "y": "11446.png",
    #         }
    #     }
    # }, None)
    #
    # handle({
    #     "params": {
    #         "path": {
    #             "z": "15",
    #             "x": "5244",
    #             "y": "11447.png",
    #         }
    #     }
    # }, None)
    handle({
        "params": {
            "path": {
                "z": "15",
                "x": "5245",
                "y": "11441.png",
            }
        }
    }, None)
    handle({
        "params": {
            "path": {
                "z": "15",
                "x": "5246",
                "y": "11441.png",
            }
        }
    }, None)
    handle({
        "params": {
            "path": {
                "z": "15",
                "x": "5247",
                "y": "11441.png",
            }
        }
    }, None)
