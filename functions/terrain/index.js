"use strict";

const env = require("require-env");

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
        source: "http://tmp.openterrain.org.s3-website-us-east-1.amazonaws.com/terrain-classic-features/{z}/{x}/{y}.png",
      },
      {
        source: "http://tmp.openterrain.org.s3-website-us-east-1.amazonaws.com/terrain-classic-labels/{z}/{x}/{y}.png",
      }
    ],
    format: "png8"
  }
};

const makeHandler = require("lib/");

exports.handle = makeHandler(
  SOURCE,
  env.require("S3_BUCKET"),
  env.require("KEY_PREFIX")
);
