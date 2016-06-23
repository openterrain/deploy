import copy
import os

import boto3
import numpy as np
import rasterio
from rasterio._io import virtual_file_to_buffer

from openterrain import hillshade as _hillshade, Tile

TMP_PATH = "/vsimem/tmp-{}".format(os.getpid())

BUFFER = 2
SRC_TILE_ZOOM = 14
SRC_TILE_WIDTH = 512
SRC_TILE_HEIGHT = 512

DST_TILE_WIDTH = 256
DST_TILE_HEIGHT = 256
DST_BLOCK_SIZE = 128


def handle(event, context):
    s3 = boto3.resource('s3')
    zoom = int(event["params"]["path"]["z"])
    x = int(event["params"]["path"]["x"])
    y, format = event["params"]["path"]["y"].split(".")
    y = int(y)
    tile = Tile(x, y, zoom)

    # TODO bail if format != "tif"
    # TODO bail if zoom > SRC_TILE_ZOOM

    # do calculations in SRC_TILE_ZOOM space

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

    buffered_window = copy.deepcopy(window)

    # buffer so we have neighboring pixels
    buffered_window[0][0] -= BUFFER
    buffered_window[0][1] += BUFFER
    buffered_window[1][0] -= BUFFER
    buffered_window[1][1] += BUFFER

    with rasterio.open("mapzen.xml") as src:
        # use decimated reads to read from overviews, per https://github.com/mapbox/rasterio/issues/710
        data = np.empty(shape=(DST_TILE_WIDTH + 2 * BUFFER, DST_TILE_HEIGHT + 2 * BUFFER)).astype(src.profile["dtype"])
        data = src.read(1, out=data, window=buffered_window)
        dx = abs(src.meta["affine"][0])
        dy = abs(src.meta["affine"][4])

        # filter out negative values
        data[data == src.meta["nodata"]] = 9999
        data[data < 0] = 0
        data[data == 9999] = src.meta["nodata"]

        hs = _hillshade(data,
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

        with rasterio.open(TMP_PATH, "w", **meta) as tmp:
            tmp.write(hs[BUFFER:-BUFFER, BUFFER:-BUFFER], 1)

        # TODO make configurable
        bucket = "hillshades.openterrain.org"
        key = "3857/{}/{}/{}.tif".format(tile.z, tile.x, tile.y)

        s3.Object(
            bucket,
            key,
        ).put(
            Body=bytes(bytearray(virtual_file_to_buffer(TMP_PATH))),
            ACL="public-read",
            ContentType="image/tiff",
            # TODO
            CacheControl="",
            StorageClass="REDUCED_REDUNDANCY",
        )

        return {
            "location": "http://{}.s3.amazonaws.com/{}".format(bucket, key)
        }
