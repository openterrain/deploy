# coding=utf-8

from collections import namedtuple
import copy
import os

import boto3
import mercantile
import numpy as np
import rasterio
from rasterio._io import virtual_file_to_buffer


BUFFER = 2
MAX_ZOOM = 15
SRC_TILE_ZOOM = 14
SRC_TILE_WIDTH = 512
SRC_TILE_HEIGHT = 512

DST_TILE_WIDTH = 256
DST_TILE_HEIGHT = 256
DST_BLOCK_SIZE = 128
TMP_PATH = "/vsimem/tmp-{}".format(os.getpid())

# from http://www.shadedrelief.com/web_relief/
EXAGGERATION = {
    0: 45.0,
    1: 29.0,
    2: 20.0,
    3: 14.0,
    4: 9.5,
    5: 6.5,
    6: 5.0,
    7: 3.6,
    8: 2.7,
    9: 2.1,
    10: 1.7,
    11: 1.4,
    12: 1.3,
    13: 1.2,
    14: 1.1,
}

S3_BUCKET = os.environ["S3_BUCKET"]

Tile = namedtuple("Tile", "x y z")


def get_hillshade(tile, cache=True):
    s3 = boto3.resource("s3")

    key = "3857/{}/{}/{}.tif".format(tile.z, tile.x, tile.y)

    try:
        s3.Object(
            S3_BUCKET,
            key,
        ).load()

        with rasterio.open("s3://{}/{}".format(S3_BUCKET, key)) as src:
            return src.read(1)
    except:
        meta = {}
        data = render_hillshade(tile, src_meta=meta)

        if cache:
            save_hillshade(tile, data=data, meta=meta)

        return data


def render_hillshade(tile, src_meta={}):
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

    # clip buffered_window on edges so values don't go negative
    right = top = BUFFER
    left = bottom = 0

    if buffered_window[1][0] > 0:
        left = BUFFER

    if buffered_window[0][1] > 0:
        bottom = BUFFER

    # buffer so we have neighboring pixels
    buffered_window[0][0] -= top
    buffered_window[0][1] += bottom
    buffered_window[1][0] -= left
    buffered_window[1][1] += right

    with rasterio.open("mapzen.xml") as src:
        # use decimated reads to read from overviews, per https://github.com/mapbox/rasterio/issues/710
        data = np.empty(shape=(DST_TILE_WIDTH + left + right, DST_TILE_HEIGHT + top + bottom)).astype(src.profile["dtype"])
        data = src.read(1, out=data, window=buffered_window)

        # scale data

        # account for overviews
        scale = (buffered_window[1][1] - buffered_window[1][0]) / data.shape[0]

        # interpolate latitudes
        bounds = mercantile.bounds(tile.x, tile.y, tile.z)
        height = data.shape[0]
        latitudes = np.interp(np.arange(height), [top, height - bottom - 1], [bounds.north, bounds.south])

        factors = 1 / np.cos(np.radians(latitudes))

        # convert to 2d array, rotate 270º, scale data
        data = data * np.rot90(np.atleast_2d(factors), 3)

        dx = abs(src.meta["affine"][0]) * scale
        dy = abs(src.meta["affine"][4]) * scale

        src_meta.update(src.meta.copy())
        del src_meta["transform"]
        src_meta.update(dict(
            height=DST_TILE_HEIGHT,
            width=DST_TILE_WIDTH,
            affine=src.window_transform(window)
        ))

        # filter out negative values
        data[data == src.meta["nodata"]] = 9999
        data[data < 0] = 0
        data[data == 9999] = src.meta["nodata"]

        hs = hillshade(data,
            dx=dx,
            dy=dy,
            vert_exag=EXAGGERATION.get(tile.z, 1.0),
        )

        hs = (255.0 * hs).astype(np.uint8)

        return hs[left:-right, top:-bottom]


def save_hillshade(tile, data, meta):
    s3 = boto3.resource("s3")
    meta.update(
        driver="GTiff",
        dtype=rasterio.uint8,
        compress="deflate",
        predictor=1,
        nodata=None,
        tiled=True,
        sparse_ok=True,
        blockxsize=DST_BLOCK_SIZE,
        blockysize=DST_BLOCK_SIZE,
    )

    with rasterio.open(TMP_PATH, "w", **meta) as tmp:
        tmp.write(data, 1)

    key = "3857/{}/{}/{}.tif".format(tile.z, tile.x, tile.y)

    s3.Object(
        S3_BUCKET,
        key,
    ).put(
        Body=bytes(bytearray(virtual_file_to_buffer(TMP_PATH))),
        ACL="public-read",
        ContentType="image/tiff",
        CacheControl="public, max-age=2592000",
        StorageClass="REDUCED_REDUNDANCY",
    )

    return "http://{}.s3.amazonaws.com/{}".format(S3_BUCKET, key)


def hillshade(elevation, azdeg=315, altdeg=45, vert_exag=1, dx=1, dy=1, fraction=1.):
    """
    This is a slightly modified version of
    matplotlib.colors.LightSource.hillshade, modified to remove the contrast
    stretching (because that uses local min/max values).

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
    intensity *= fraction

    intensity = np.clip(intensity, 0, 1, intensity)

    return intensity
