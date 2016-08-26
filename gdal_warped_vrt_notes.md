# GDAL Warped VRT Notes

See this tutorial that explains warped VRT: http://erouault.blogspot.com/2014/10/warping-overviews-and-warped-overviews.html

Basically, the following, but with a target size matching z15 and extent matching the world

```
gdalwarp /vsicurl/http://data.stamen.com.s3.amazonaws.com/mpgranch/imagery/2016_c.tif out.vrt -t_srs EPSG:3857 \
  -r cubic -overwrite -of VRT
```
