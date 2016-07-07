"use strict";

const env = require("require-env");

const HOSTS = env.require("HOSTS").split(" "),
  PROTOCOL = process.env.PROTOCOL || "http:";

exports.handle = (event, context, callback) => {
  console.log("Event:", event);

  const path = event.params.path,
    targetPath = [path.style, path.z, path.x, path.y].join("/");

  return callback(null, {
    location: `${PROTOCOL}//${HOSTS[(Math.random() * HOSTS.length) | 0]}/${targetPath}`
  });
};
