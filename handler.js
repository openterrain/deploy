"use strict";

const env = require("require-env");

const makeHandler = require("./lib/");

exports.handle = makeHandler(
  env.require("SOURCE_URI"),
  env.require("S3_BUCKET"),
  env.require("KEY_PREFIX")
);
