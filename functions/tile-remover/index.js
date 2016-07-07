"use strict";

const AWS = require("aws-sdk"),
  env = require("require-env");

const Lambda = new AWS.Lambda(),
  S3 = new AWS.S3(),
  SQS = new AWS.SQS();

const QUEUE_URL = env.require("QUEUE_URL"),
  PROCESS_MESSAGE = "process-message";


function process(message, callback) {
  const payload = JSON.parse(message.Body);

  return S3.deleteObject({
    Bucket: payload.Bucket,
    Key: payload.Key,
  }, (err) => {
    if (err) {
      console.warn(err.stack);
    }

    // delete message
    const params = {
      QueueUrl: QUEUE_URL,
      ReceiptHandle: message.ReceiptHandle
    };
    return SQS.deleteMessage(params, (err) => callback(err, message));
  });
}

function poll(functionName, callback) {
  const params = {
    QueueUrl: QUEUE_URL,
    MaxNumberOfMessages: 10, // TODO appears to assume 10 messages / polling interval
    VisibilityTimeout: 10
  };
  // batch request messages
  SQS.receiveMessage(params, (err, data) => {
    if (err) {
      return callback(err);
    }

    // for each message, reinvoke the function
    const promises = (data.Messages || []).map((message) => {
      const payload = {
        operation: PROCESS_MESSAGE,
        message: message
      };
      const params = {
        FunctionName: functionName,
        InvocationType: "Event",
        Payload: new Buffer(JSON.stringify(payload))
      };
      return new Promise((resolve, reject) => {
        Lambda.invoke(params, (err) => err ? reject(err) : resolve());
      });
    });
    // complete when all invocations have been made
    Promise.all(promises).then(() => {
      const result = `Messages received: ${data.Messages.length}`;
      console.log(result);
      callback(null, result);
    });
  });
}

exports.handle = (event, context, callback) => {
  try {
    if (event.operation === PROCESS_MESSAGE) {
      // invoked by poller
      process(event.message, callback);
    } else {
      // invoked by schedule
      poll(context.functionName, callback);
    }
  } catch (err) {
    callback(err);
  }
};
