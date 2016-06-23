from StringIO import StringIO

import boto3
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
import numpy as np
import rasterio

from openterrain import Tile


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

SRC_TILE_ZOOM = 14
SRC_TILE_WIDTH = 512
SRC_TILE_HEIGHT = 512

DST_TILE_WIDTH = 256
DST_TILE_HEIGHT = 256


def handle(event, context):
    s3 = boto3.resource('s3')
    zoom = int(event["params"]["path"]["z"])
    x = int(event["params"]["path"]["x"])
    y, format = event["params"]["path"]["y"].split(".")
    y = int(y)
    tile = Tile(x, y, zoom)

    # TODO bail if format != "png"
    # TODO bail if zoom > SRC_TILE_ZOOM
    # TODO retina

    # do calculations in SRC_TILE_ZOOM space

    # TODO retina calculations
    # dz = SRC_TILE_ZOOM - tile.z - (2 - SRC_TILE_WIDTH / DST_TILE_WIDTH)
    dz = SRC_TILE_ZOOM - tile.z
    x = 2**dz * tile.x
    y = 2**dz * tile.y
    mx = 2**dz * (tile.x + 1)
    my = 2**dz * (tile.y + 1)
    dx = mx - x
    dy = my - y
    top = (2**SRC_TILE_ZOOM * SRC_TILE_HEIGHT) - 1

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

    # TODO check S3 and generate if necessary
    with rasterio.open("hillshades.xml") as src:
        # use decimated reads to read from overviews, per https://github.com/mapbox/rasterio/issues/710
        data = np.empty(shape=(DST_TILE_WIDTH, DST_TILE_HEIGHT)).astype(src.profile["dtype"])
        data = src.read(1, out=data, window=window)

        out = StringIO()
        plt.imsave(
            out,
            data,
            cmap=DARKMATTER,
            vmin=0,
            vmax=255,
            format=format,
        )

        # TODO make configurable
        bucket = "hillshades.openterrain.org"
        key = "darkmatter/{}/{}/{}.{}".format(tile.z, tile.x, tile.y, format)

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
