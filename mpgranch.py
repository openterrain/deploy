import re
from StringIO import StringIO
from PIL import Image
# import matplotlib.pyplot as plt
import numpy as np
import rasterio

from openterrain import MAX_ZOOM, render_tile, Tile

def main():
    meta = {}
    #15/6009/11565
    #20/192292/370086
    # data = render_tile(Tile(6009, 11565, 15), src_meta=meta)
    data = render_tile(Tile(192292 / 2, 370086 / 2, 19), src_meta=meta)

    meta.update(
        driver="GTiff",
        compress="deflate",
        predictor=1,
        nodata=None,
        tiled=True,
        sparse_ok=True,
        blockxsize=256,
        blockysize=256,
    )


    with rasterio.open("mpgranch.tiff", "w", **meta) as tmp:
        tmp.write(data)

    imgarr = np.ma.transpose(data, [1, 2, 0]).astype(np.uint8)
    print imgarr.shape

    # TODO dtype is uint16
    # plt.imsave(
    #     "mpgranch.png",
    #     imgarr,
    #     format="png",
    # )

    im = Image.fromarray(imgarr, 'RGB')
    im.save("mpgranch2.png")

def handle(event):
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

    data = render_tile(tile)
    imgarr = np.ma.transpose(data, [1, 2, 0]).astype(np.uint8)

    out = StringIO()
    im = Image.fromarray(imgarr, "RGB")
    im.save(out, format)

    if scale == 1:
        im = Image.open(out)
        im.thumbnail((256, 256), Image.ANTIALIAS)
        out = StringIO()
        im.save(out, format)

    return out.getvalue()


if __name__ == "__main__":
    main()
