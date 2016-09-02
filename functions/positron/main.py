import os
import re
from StringIO import StringIO

import boto3
import matplotlib
matplotlib.use("Agg")

from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from PIL import Image
from raven import Client

from openterrain import get_hillshade, MAX_ZOOM, Tile


POSITRON_RAMP = {
    "red": [(0.0, 0.0, 0.3),
            (1.0, 1.0, 1.0)],
    "green": [(0.0, 0.0, 0.3),
              (1.0, 1.0, 1.0)],
    "blue": [(0.0, 0.0, 0.3),
             (1.0, 1.0, 1.0)],
    "alpha": [(0.0, 0.7, 0.7),
              (195 / 255.0, 0.0, 0.0),
              (1.0, 1.0, 1.0)]
}

POSITRON = LinearSegmentedColormap("positron", POSITRON_RAMP)

S3_BUCKET = os.environ["S3_BUCKET"]

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

    if not 0 <= tile.x < 2**tile.z:
        raise Exception("Invalid coordinates")

    if not 0 <= tile.y < 2**tile.z:
        raise Exception("Invalid coordinates")


    # TODO maybe check if the tile already exists (but maybe we actually want to overwrite it)

    try:
        hs = get_hillshade(tile)

        out = StringIO()
        plt.imsave(
            out,
            hs,
            cmap=POSITRON,
            vmin=0,
            vmax=255,
            format=format,
        )

        key = "positron/{}/{}/{}@2x.{}".format(tile.z, tile.x, tile.y, format)

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
            )

            # resize as 1x asset
            key = "positron/{}/{}/{}.{}".format(tile.z, tile.x, tile.y, format)
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
        )
    except:
        sentry.captureException()
        raise

    return {
        "location": "http://{}.s3.amazonaws.com/{}".format(S3_BUCKET, key)
    }
