"use strict";

const AWS = require("aws-sdk"),
  env = require("require-env"),
  tilelive = require("tilelive-cache")(require("tilelive"));

require("tilelive-modules/loader")(tilelive);

const S3_BUCKET = env.require("S3_BUCKET");

const S3 = new AWS.S3()

const SOURCE = {
  protocol: "blend:",
  query: {
    layers: [
      {
        source: "http://tmp.openterrain.org.s3-website-us-east-1.amazonaws.com/terrain-classic-background/{z}/{x}/{y}.png",
      },
      {
        source: "http://hillshades.openterrain.org.s3-website-us-east-1.amazonaws.com/positron/{z}/{x}/{y}.png",
        "comp-op": "hard-light",
        opacity: "0.7"
      },
      {
        source: "http://tmp.openterrain.org.s3-website-us-east-1.amazonaws.com/terrain-classic-lines/{z}/{x}/{y}.png",
      },
      {
        source: "http://tmp.openterrain.org.s3-website-us-east-1.amazonaws.com/terrain-classic-labels/{z}/{x}/{y}.png",
      }
    ],
    format: "png8"
  }
};

exports.handle = (event, context, callback) => {
  const z = event.params.path.z || 0,
    x = event.params.path.x || 0,
    parts = event.params.path.y.split("."),
    y = parts.shift() || 0,
    format = parts.shift();

  // TODO validate zoom
  // TODO validate format

  return tilelive.load(SOURCE, (err, source) => {
    if (err) {
      return callback(err);
    }

    return source.getTile(z, x, y, (err, data) => {
      if (err) {
        return callback(err);
      }

      const key = `terrain/${z}/${x}/${y}.png`;

      return S3.putObject({
        Bucket: S3_BUCKET,
        Key: key,
        Body: data,
        ACL: "public-read",
        ContentType: "image/png",
        CacheControl: "public, max-age=2592000",
        StorageClass: "REDUCED_REDUNDANCY",
      }, (err, data) => {
        if (err) {
          return callback(err);
        }

        return callback(null, {
          location: `http://${S3_BUCKET}.s3.amazonaws.com/${key}`
        });
      })
    });
  });
};
