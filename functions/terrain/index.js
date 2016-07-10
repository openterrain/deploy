"use strict";

const env = require("require-env");

const SOURCE = {
  protocol: "blend:",
  query: {
    layers: [
      {
        source: "http://tile.stamen.com.s3-website-us-east-1.amazonaws.com/terrain-bg/{z}/{x}/{y}.png",
      },
      {
        source: {
          protocol: "http:",
          host: "hillshades.openterrain.org.s3-website-us-east-1.amazonaws.com",
          pathname: "/positron/{z}/{x}/{y}.png",
          info: {
            minzoom: 0,
            maxzoom: 15
          }
        },
        "comp-op": "hard-light",
        opacity: "0.6"
      },
      {
        source: "http://tile.stamen.com.s3-website-us-east-1.amazonaws.com/terrain-features/{z}/{x}/{y}.png",
      },
      {
        source: "http://tile.stamen.com.s3-website-us-east-1.amazonaws.com/terrain-labels/{z}/{x}/{y}.png",
      }
    ],
    info: {
      minzoom: 0,
      maxzoom: 18,
    },
    format: "png8"
  }
};

const makeHandler = require("./lib/");

exports.handle = makeHandler(
  SOURCE,
  env.require("S3_BUCKET"),
  env.require("KEY_PREFIX"),
  {
    "Surrogate-Key": "{{prefix}} {{prefix}}/z{{zoom}}"
  }
);
