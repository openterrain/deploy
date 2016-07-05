"use strict";

const AWS = require("aws-sdk"),
  holdtime = require("holdtime"),
  raven = require("raven"),
  retry = require("retry"),
  SphericalMercator = require("sphericalmercator"),
  tilelive = require("tilelive-cache")(require("tilelive"));

require("tilelive-modules/loader")(tilelive);

const S3 = new AWS.S3(),
  mercator = new SphericalMercator(),
  sentry = new raven.Client();

const getExtension = (format) => {
  // trim PNG variant info
  switch ((format || "").replace(/^(png).*/, "$1")) {
  case "png":
    return "png";

  default:
    return format;
  }
};

module.exports = (uri, bucket, prefix) => {
  return (event, context, callback) => {
    context.callbackWaitsForEmptyEventLoop = false;

    const z = event.params.path.z || 0,
      x = event.params.path.x || 0,
      parts = event.params.path.y.split("."),
      y = parts.shift() || 0,
      format = parts.shift();

    // configure retries
    // retrying occurs in case Mapnik runs into a problem with one of its extant connections
    const operation = retry.operation({
      retries: 2,
      minTimeout: 0,
    });

    return operation.attempt(currentAttempt => {
      return tilelive.load(uri, holdtime((err, source, elapsedMS) => {
        if (err) {
          sentry.captureException(err);
          return callback(err);
        }

        console.log("loading took %dms", elapsedMS);

        return source.getInfo((err, info) => {
          if (err) {
            sentry.captureException(err);
            return callback(err);
          }

          // TODO these defaults belong in tilelive-http / tilelive-blend
          info.format = info.format || "png";
          info.minzoom = "minzoom" in info ? info.minzoom : 0;
          info.maxzoom = "maxzoom" in info ? info.maxzoom : Infinity;
          info.bounds = info.bounds || [-180, -85.0511, 180, 85.0511];

          // validate format / extension
          var ext = getExtension(info.format);

          if (ext !== format) {
            return callback(new Error("Invalid format"));
          }

          // validate zoom
          if (z < info.minzoom || z > info.maxzoom) {
            return callback(new Error("Invalid zoom"));
          }

          // validate coords against bounds
          var xyz = mercator.xyz(info.bounds, z);

          if (x < xyz.minX ||
              x > xyz.maxX ||
              y < xyz.minY ||
              y > xyz.maxY) {
            return callback(new Error("Invalid coordinates"));
          }

          // TODO subscribe to source and write generated tiles out
          return source.getTile(z, x, y, holdtime((err, data, headers, elapsedMS) => {
            if (operation.retry(err)) {
              console.warn(err.stack);
              sentry.captureException(err);
              // close the source and allow it to be reloaded
              source.close();
              return;
            }

            if (err) {
              console.warn("Error after retry:", err.stack);
              sentry.captureException(err);
              return callback(operation.mainError());
            }

            console.log("rendering %d/%d/%d took %dms", z, x, y, elapsedMS);

            const key = `${prefix}/${z}/${x}/${y}.png`;

            return S3.putObject({
              Bucket: bucket,
              Key: key,
              Body: data,
              ACL: "public-read",
              ContentType: "image/png",
              CacheControl: "public, max-age=2592000",
              StorageClass: "REDUCED_REDUNDANCY",
            }, holdtime((err, data, elapsedMS) => {
              if (err) {
                sentry.captureException(err);
                return callback(err);
              }

              console.log("writing %s took %dms", key, elapsedMS);

              return callback(null, {
                location: `http://${bucket}.s3.amazonaws.com/${key}`
              });
            }));
          }));
        });
      }));
    });
  };
};
