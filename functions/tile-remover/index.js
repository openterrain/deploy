"use strict";

const async = require("async"),
  AWS = require("aws-sdk"),
  env = require("require-env");

const S3 = new AWS.S3(),
  SQS = new AWS.SQS();

const QUEUE_URL = env.require("QUEUE_URL");


exports.handle = (event, context, callback) => {
  return async.doWhilst(
    done => {
      // batch request messages
      return SQS.receiveMessage({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10, // maximum number of messages that can be fetched
        VisibilityTimeout: 10
      }, (err, data) => {
        if (err) {
          return done(err);
        }

        return async.each(data.Messages, (message, cb) => {
          const payload = JSON.parse(message.Body);

          console.log("deleting", payload.Key);

          return S3.deleteObject({
            Bucket: payload.Bucket,
            Key: payload.Key,
          }, (err) => {
            if (err) {
              console.warn(err.stack);
            }

            // delete message
            return SQS.deleteMessage({
              QueueUrl: QUEUE_URL,
              ReceiptHandle: message.ReceiptHandle
            }, cb);
          });
        }, err => done(err, (data.Messages || []).length));
      });
    },
    messageCount => messageCount > 0 && context.getRemainingTimeInMillis() > 1000,
    callback
  );
};
