import os
import re
from StringIO import StringIO

import boto3
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from PIL import Image
from raven import Client

from openterrain import get_hillshade, MAX_ZOOM, Tile


GREY_HILLS_RAMP = {
    "red": [(0.0, 0.0, 0.0),
            (0.25, 0.0, 0.0),
            (180 / 255.0, 0.5, 0.5),
            (1.0, 170 / 255.0, 170 / 255.0)],
    "green": [(0.0, 0.0, 0.0),
              (0.25, 0.0, 0.0),
              (180 / 255.0, 0.5, 0.5),
              (1.0, 170 / 255.0, 170 / 255.0)],
    "blue": [(0.0, 0.0, 0.0),
             (0.25, 0.0, 0.0),
             (180 / 255.0, 0.5, 0.5),
             (1.0, 170 / 255.0, 170 / 255.0)],
}

GREY_HILLS = LinearSegmentedColormap("grey_hills", GREY_HILLS_RAMP)

# S3_BUCKET is used for hillshade saving, so if they differ, it's problematic
S3_BUCKET = "tile.stamen.com"

sentry = Client()


def handle(event, context):
    s3 = boto3.resource("s3")
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

    # TODO maybe check if the tile already exists (but maybe we actually want to overwrite it)

    try:
        hs = get_hillshade(tile)

        out = StringIO()
        plt.imsave(
            out,
            hs,
            cmap=GREY_HILLS,
            vmin=0,
            vmax=255,
            format=format,
        )

        key = "terrain-grey-hills/{}/{}/{}@{}x.{}".format(tile.z, tile.x, tile.y, scale, format)

        if scale == 1:
            # save retina version first
            # TODO check if this exists first
            s3.Object(
                S3_BUCKET,
                key,
            ).put(
                Body=out.getvalue(),
                ACL="public-read",
                ContentType="image/{}".format(format),
                CacheControl="public, max-age=2592000",
                StorageClass="REDUCED_REDUNDANCY",
                Metadata={"Surrogate-Key": "terrain-grey-hills terrain-grey-hills/z{}".format(zoom)},
            )

            # resize as 1x asset
            key = "terrain-grey-hills/{}/{}/{}.{}".format(tile.z, tile.x, tile.y, format)
            im = Image.open(out)
            im.thumbnail((256, 256), Image.ANTIALIAS)
            out = StringIO()
            im.save(out, format)

        s3.Object(
            S3_BUCKET,
            key,
        ).put(
            Body=out.getvalue(),
            ACL="public-read",
            ContentType="image/{}".format(format),
            CacheControl="public, max-age=2592000",
            StorageClass="REDUCED_REDUNDANCY",
            Metadata={"Surrogate-Key": "terrain-grey-hills terrain-grey-hills/z{}".format(zoom)},
        )
    except:
        sentry.captureException()
        raise

    return {
        "location": "http://{}.s3.amazonaws.com/{}".format(S3_BUCKET, key)
    }
