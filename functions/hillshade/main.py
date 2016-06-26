from raven import Client

from openterrain import MAX_ZOOM, render_hillshade, save_hillshade, Tile


sentry = Client()


def handle(event, context):
    zoom = int(event["params"]["path"]["z"])
    x = int(event["params"]["path"]["x"])
    y, format = event["params"]["path"]["y"].split(".")
    y = int(y)
    tile = Tile(x, y, zoom)

    if format != "tif":
        raise Exception("Invalid format")

    if not 0 <= tile.z <= MAX_ZOOM:
        raise Exception("Invalid zoom")

    # TODO maybe check if the tile already exists (but maybe we actually want to overwrite it)

    meta = {}
    try:
        location = save_hillshade(tile, data=render_hillshade(tile, src_meta=meta), meta=meta)
    except:
        sentry.captureException()
        raise

    return {
        "location": location
    }
