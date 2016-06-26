import os
from StringIO import StringIO

import boto3
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from raven import Client

from openterrain import get_hillshade, Tile


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

S3_BUCKET = os.environ["S3_BUCKET"]

sentry = Client()


def handle(event, context):
    try:
        s3 = boto3.resource("s3")
        zoom = int(event["params"]["path"]["z"])
        x = int(event["params"]["path"]["x"])
        y, format = event["params"]["path"]["y"].split(".")
        y = int(y)
        tile = Tile(x, y, zoom)

        # TODO bail if format != "png"
        # TODO bail if zoom > SRC_TILE_ZOOM
        # TODO retina

        # TODO check if the tile already exists (but maybe we actually want to overwrite it)

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

        key = "positron/{}/{}/{}.{}".format(tile.z, tile.x, tile.y, format)

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

        return {
            "location": "http://{}.s3.amazonaws.com/{}".format(S3_BUCKET, key)
        }
    except:
        sentry.captureException()
        raise
