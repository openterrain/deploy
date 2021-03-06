"use strict";

const os = require("os"),
  url = require("url");

const AWS = require("aws-sdk"),
  clone = require("clone"),
  env = require("require-env"),
  handlebars = require("handlebars"),
  holdtime = require("holdtime"),
  raven = require("raven"),
  retry = require("retry"),
  SphericalMercator = require("sphericalmercator"),
  tilelive = require("tilelive-cache")(require("tilelive"));

require("tilelive-modules/loader")(tilelive);

const HOSTS = env.require("HOSTS").split(" "),
  PROTOCOL = process.env.PROTOCOL || "http:",
  QUEUE_URL = env.require("QUEUE_URL");

const S3 = new AWS.S3(),
  SQS = new AWS.SQS(),
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

module.exports = (sourceUri, bucket, prefix, headers) => {
  if (typeof sourceUri === "string") {
    sourceUri = url.parse(sourceUri, true);
  }

  const templates = Object.keys(headers || {}).reduce((obj, name) => {
    obj[name] = handlebars.compile(headers[name]);

    // attempt to parse so we can fail fast
    try {
      obj[name]();
    } catch (err) {
      console.error("'${name}' header is invalid.")
      console.error(err);

      sentry.captureException(err);

      process.exit(1);
    }

    return obj;
  }, {});

  return (event, context, _callback) => {
    const startTimes = os.cpus().map(x => x.times);
    context.callbackWaitsForEmptyEventLoop = false;
    const timeout = setTimeout(() => {
      console.error("About to be timed out by Lambda, quitting for cleanup purposes...");

      process.exit(124);
    }, context.getRemainingTimeInMillis() - 500);

    // wrap the callback so that the timeout is canceled
    const callback = function() {
      clearTimeout(timeout);

      return _callback.apply(null, arguments);
    };

    const z = event.params.path.z | 0,
      x = event.params.path.x | 0,
      parts = event.params.path.y.split("."),
      parts2 = parts.shift().split("@"),
      y = parts2.shift() | 0,
      scale = parseInt(parts2.shift() || 1),
      format = parts.shift(),
      uri = clone(sourceUri);

    if (scale > 1) {
      uri.query.scale = scale;

      if (uri.protocol === "mapnik:") {
        uri.query.tileSize = scale * 256;
      }
    }

    if (scale < 1 || scale > 2) {
      return callback(new Error("Invalid scale"));
    }

    // configure retries
    // retrying occurs in case Mapnik runs into a problem with one of its extant connections
    const operation = retry.operation({
      retries: 2,
      minTimeout: 0,
    });

    return operation.attempt(currentAttempt => {
      return tilelive.load(uri, holdtime((err, source, elapsedMS) => {
        if (operation.retry(err)) {
          sentry.captureException(err);
          console.warn("tileload.load:", err.stack);
          if (source) {
            // close the source and allow it to be reloaded
            source.close(() => {});
          }
          return;
        }

        if (err) {
          sentry.captureException(err);
          console.warn("Error after retry:", err.stack);
          return callback(operation.mainError());
        }

        console.log("loading took %dms", elapsedMS);

        return source.getInfo((err, info) => {
          if (operation.retry(err)) {
            sentry.captureException(err);
            console.warn("source.getInfo:", err.stack);
            // close the source and allow it to be reloaded
            source.close(() => {});
            return;
          }

          if (err) {
            sentry.captureException(err);
            console.warn("Error after retry:", err.stack);
            return callback(operation.mainError());
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

          return source.getTile(z, x, y, holdtime((err, data, headers, elapsedMS) => {
            if (operation.retry(err)) {
              console.warn("source.getTile:", err.stack);
              sentry.captureException(err);
              // close the source and allow it to be reloaded
              source.close(() => {});
              return;
            }

            if (err) {
              sentry.captureException(err);
              console.warn("Error after retry:", err.stack);
              return callback(operation.mainError());
            }

            let key = `${prefix}/${z}/${x}/${y}.png`;

            if (scale > 1) {
              key = `${prefix}/${z}/${x}/${y}@${scale}x.png`;
            }

            console.log("Rendering %s took %dms", key, elapsedMS);

            headers = headers || {};

            const maxAge = (headers["Cache-Control"] || headers["cache-control"] || "")
              .split(",")
              .map(x => x.trim())
              .filter(x => x.match(/^max-age=/))
              .map(x => x.split("=")[1])
              .filter(x => x != null)
              .shift();

            if (maxAge != null && (maxAge | 0) === 0) {
              console.log("Invalidating %s with a maxAge of %s (%s)", key, maxAge, headers["Cache-Control"] || headers["cache-control"]);
              // queue an immediate deletion of this tile since it's effectively invalid
              SQS.sendMessage({
                MessageBody: JSON.stringify({
                  Bucket: bucket,
                  Key: key,
                }),
                QueueUrl: QUEUE_URL,
              }, (err) => {
                if (err) {
                  console.warn(err.stack);
                }
              });
            }

            // populate custom headers
            const params = {
              prefix,
              scale,
              x,
              y,
              z,
              zoom: z,
            };

            const metadata = Object.keys(templates).reduce((obj, name) => {
              obj[name] = templates[name](params);

              return obj;
            }, {});

            return S3.putObject({
              Bucket: bucket,
              Key: key,
              Body: data,
              ACL: "public-read",
              ContentType: headers["Content-Type"] || headers["content-type"],
              CacheControl: headers["Cache-Control"] || headers["cache-control"] || "public, max-age=2592000",
              Metadata: metadata,
              StorageClass: "REDUCED_REDUNDANCY",
            }, holdtime((err, data, elapsedMS) => {
              if (err) {
                sentry.captureException(err);
                return callback(err);
              }

              console.log("writing %s took %dms", key, elapsedMS);

              const endTimes = os.cpus().map(x => x.times);
              const times = ["user", "nice", "sys", "idle"].reduce((obj, cat) => {
                obj[cat] = endTimes.reduce((sum, time) => sum + time[cat], 0) - startTimes.reduce((sum, time) => sum + time[cat], 0);

                return obj;
              }, {});

              console.log("%s user: %d:", key, times.user);
              console.log("%s nice: %d:", key, times.nice);
              console.log("%s sys: %d:", key, times.sys);
              console.log("%s idle: %d:", key, times.idle);

              return callback(null, {
                location: `${PROTOCOL}//${HOSTS[(Math.random() * HOSTS.length) | 0]}/${key}`
              });
            }));
          }));
        });
      }));
    });
  };
};
