from openterrain import render_hillshade, save_hillshade, Tile


def handle(event, context):
    zoom = int(event["params"]["path"]["z"])
    x = int(event["params"]["path"]["x"])
    y, format = event["params"]["path"]["y"].split(".")
    y = int(y)
    tile = Tile(x, y, zoom)

    # TODO bail if format != "tif"
    # TODO bail if zoom > SRC_TILE_ZOOM

    # TODO check if the tile already exists (but maybe we actually want to overwrite it)

    meta = {}
    location = save_hillshade(tile, data=render_hillshade(tile, src_meta=meta), meta=meta)

    return {
        "location": location
    }
