FROM lambci/lambda:build-python2.7

# Install deps

ADD deps/automake16-1.6.3-18.6.amzn1.noarch.rpm /tmp
ADD deps/freetype-devel-2.3.11-15.14.amzn1.x86_64.rpm /tmp
ADD deps/libcurl-devel-7.40.0-8.54.amzn1.x86_64.rpm /tmp
ADD deps/libpng-devel-1.2.49-2.14.amzn1.x86_64.rpm /tmp

RUN \
  rpm -ivh /tmp/freetype-devel-2.3.11-15.14.amzn1.x86_64.rpm \
    /tmp/automake16-1.6.3-18.6.amzn1.noarch.rpm \
    /tmp/libcurl-devel-7.40.0-8.54.amzn1.x86_64.rpm \
    /tmp/libpng-devel-1.2.49-2.14.amzn1.x86_64.rpm

# Fetch PROJ.4

RUN \
  curl -L http://download.osgeo.org/proj/proj-4.9.2.tar.gz | tar zxf - -C /tmp

# Build and install PROJ.4

WORKDIR /tmp/proj-4.9.2

RUN \
  ./configure && \
  make -j $(nproc) && \
  make install

# Fetch GDAL

RUN \
  curl -L http://download.osgeo.org/gdal/2.1.1/gdal-2.1.1.tar.gz | tar zxf - -C /tmp

# Build + install GDAL

WORKDIR /tmp/gdal-2.1.1

RUN \
  ./configure \
    --datarootdir=/var/task/share/gdal \
    --without-qhull \
    --without-mrf \
    --without-grib \
    --without-pcraster \
    --without-png \
    --without-jpeg \
    --without-gif \
    --without-pcidsk && \
  make -j $(nproc) && \
  make install

# Install Python deps in a virtualenv

RUN \
  virtualenv /tmp/virtualenv

ENV PATH /tmp/virtualenv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN \
  pip install numpy

RUN \
  pip install rasterio

RUN \
  pip install matplotlib

RUN \
  pip install raven

RUN \
  pip install mercantile

RUN \
  pip install pillow

# Add GDAL libs to the function zip

WORKDIR /usr/local

RUN \
  strip lib/libgdal.so.20.1.1

RUN \
  strip lib/libproj.so.9.1.0

RUN \
  zip --symlinks \
    -r9 /tmp/task.zip \
    lib/libgdal.so* \
    lib/libproj.so*

WORKDIR /var/task

RUN \
  zip --symlinks \
    -r9 /tmp/task.zip \
    share/gdal/

# Add Python deps to the function zip

WORKDIR /tmp/virtualenv/lib64/python2.7/site-packages

RUN \
  zip --symlinks \
    -x easy_install.py\* \
    -x pip\* \
    -x pkg_resources\* \
    -x setuptools\* \
    -x wheel\* \
    -x \*/tests/\* \
    -x \*/test/\* \
    -x matplotlib/testing/\* \
    -x matplotlib/backends/web_backend/\* \
    -x numpy/core/include/numpy/multiarray_api.txt \
    -x matplotlib/backends/qt_editor/\* \
    -x matplotlib/backends/backend_qt4.pyc \
    -x matplotlib/backends/backend_gtkcairo.py \
    -x matplotlib/backends/backend_mixed.pyc \
    -x matplotlib/backends/backend_svg.py \
    -x matplotlib/backends/backend_wx.pyc \
    -x matplotlib/backends/backend_gtk.py \
    -x matplotlib/backends/backend_ps.pyc \
    -x matplotlib/backends/qt_compat.pyc \
    -x matplotlib/backends/backend_pgf.py \
    -x matplotlib/backends/backend_cairo.py \
    -x matplotlib/backends/backend_wxagg.pyc \
    -x matplotlib/backends/backend_qt4agg.py \
    -x matplotlib/backends/backend_webagg_core.pyc \
    -x matplotlib/backends/windowing.py \
    -x matplotlib/backends/backend_gtk.pyc \
    -x matplotlib/backends/backend_macosx.py \
    -x matplotlib/backends/backend_qt4.py \
    -x matplotlib/backends/backend_gtk3.py \
    -x matplotlib/backends/backend_ps.py \
    -x matplotlib/backends/backend_template.pyc \
    -x matplotlib/backends/qt4_compat.py \
    -x matplotlib/backends/backend_svg.pyc \
    -x matplotlib/backends/backend_cairo.pyc \
    -x matplotlib/backends/backend_pgf.pyc \
    -x matplotlib/backends/backend_qt5agg.pyc \
    -x matplotlib/backends/backend_tkagg.pyc \
    -x matplotlib/backends/backend_pdf.py \
    -x matplotlib/backends/wx_compat.py \
    -x matplotlib/backends/Matplotlib.nib/\* \
    -x matplotlib/backends/backend_cocoaagg.py \
    -x matplotlib/backends/tkagg.py \
    -x matplotlib/backends/backend_gtk3.pyc \
    -x matplotlib/backends/backend_gtk3cairo.py \
    -x matplotlib/backends/backend_gtkcairo.pyc \
    -x matplotlib/backends/backend_cocoaagg.pyc \
    -x matplotlib/backends/backend_qt4agg.pyc \
    -x matplotlib/backends/backend_gtk3agg.pyc \
    -x matplotlib/backends/backend_qt5.pyc \
    -x matplotlib/backends/backend_template.py \
    -x matplotlib/backends/backend_qt5.py \
    -x matplotlib/backends/backend_wxagg.py \
    -x matplotlib/backends/backend_gtk3agg.py \
    -x matplotlib/backends/backend_gtk3cairo.pyc \
    -x matplotlib/backends/backend_gtkagg.py \
    -x matplotlib/backends/tkagg.pyc \
    -x matplotlib/backends/backend_gtkagg.pyc \
    -x matplotlib/backends/backend_webagg_core.py \
    -x matplotlib/backends/windowing.pyc \
    -x matplotlib/backends/wx_compat.pyc \
    -x matplotlib/backends/backend_tkagg.py \
    -x matplotlib/backends/backend_gdk.py \
    -x matplotlib/backends/backend_gdk.pyc \
    -x matplotlib/backends/backend_nbagg.pyc \
    -x matplotlib/backends/backend_macosx.pyc \
    -x matplotlib/backends/qt4_compat.pyc \
    -x matplotlib/backends/backend_nbagg.py \
    -x matplotlib/backends/backend_wx.py \
    -x matplotlib/backends/backend_webagg.py \
    -x matplotlib/backends/qt_compat.py \
    -x matplotlib/backends/backend_qt5agg.py \
    -x matplotlib/backends/backend_pdf.pyc \
    -r9 /tmp/task.zip *
