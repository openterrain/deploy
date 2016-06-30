"use strict";

const AWS = require("aws-sdk"),
  env = require("require-env"),
  holdtime = require("holdtime"),
  retry = require("retry"),
  tilelive = require("tilelive-cache")(require("tilelive"));
  // tilelive = require("tilelive");

require("tilelive-modules/loader")(tilelive);

const S3_BUCKET = env.require("S3_BUCKET");

const S3 = new AWS.S3()

const SOURCE = "mapnik://./terrain-classic-labels.xml?metatile=1";
// const SOURCE = "mapnik://./terrain-classic.xml?internal_cache=false";

exports.handle = (event, context, callback) => {
  context.callbackWaitsForEmptyEventLoop = false;

  const z = event.params.path.z || 0,
    x = event.params.path.x || 0,
    parts = event.params.path.y.split("."),
    y = parts.shift() || 0,
    format = parts.shift();

  // TODO validate zoom
  // TODO validate format

  // configure retries
  // retrying occurs in case Mapnik runs into a problem with one of its extant connections
  const operation = retry.operation({
    retries: 2,
    minTimeout: 0,
  });

  return operation.attempt(currentAttempt => {
    return tilelive.load(SOURCE, holdtime((err, source, elapsedMS) => {
      if (err) {
        return callback(err);
      }

      console.log("loading took %dms", elapsedMS);

      // TODO subscribe to source and write generated tiles out
      return source.getTile(z, x, y, holdtime((err, data, headers, elapsedMS) => {
        if (operation.retry(err)) {
          console.warn(err.stack);
          // close the source and allow it to be reloaded
          source.close();
          return;
        }

        if (err) {
          console.warn("Error after retry:", err.stack);
          return callback(operation.mainError());
        }

        console.log("rendering %d/%d/%d took %dms", z, x, y, elapsedMS);

        const key = `terrain-classic-labels/${z}/${x}/${y}.png`;

        return S3.putObject({
          Bucket: S3_BUCKET,
          Key: key,
          Body: data,
          ACL: "public-read",
          ContentType: "image/png",
          CacheControl: "public, max-age=2592000",
          StorageClass: "REDUCED_REDUNDANCY",
        }, holdtime((err, data, elapsedMS) => {
          if (err) {
            return callback(err);
          }

          console.log("writing %s took %dms", key, elapsedMS);

          return callback(null, {
            location: `http://${S3_BUCKET}.s3.amazonaws.com/${key}`
          });
        }));
      }));
    }));
  });
};
