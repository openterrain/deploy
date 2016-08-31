# GDAL Warped VRT Notes

See this tutorial that explains warped VRT: http://erouault.blogspot.com/2014/10/warping-overviews-and-warped-overviews.html

Basically, the following, but with a target size matching z15 (2**15 * 256) and extent matching the world (`-20037508.34 -20037508.34 20037508.34 20037508.34`)

```
gdalwarp /vsicurl/http://data.stamen.com.s3.amazonaws.com/mpgranch/imagery/2016_c.tif out.vrt -t_srs EPSG:3857 \
  -r cubic -overwrite -of VRT
```

zoom 19, include an alpha channel to prevent black cuffs

```bash
gdalwarp 2015_c.tif out.vrt -t_srs EPSG:3857 -r cubic -overwrite -of VRT -te -20037508.34 -20037508.34 20037508.34 20037508.34 -ts 134217728 134217728 -srcnodata None -dstalpha
```
