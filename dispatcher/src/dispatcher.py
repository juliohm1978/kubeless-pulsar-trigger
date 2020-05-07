#!/usr/local/bin/python

import argh
import pulsar
import logging
import logging.config
import os
import sys
import datetime
import pytz
import requests
import json
import time
import uuid

def main(
  kubeconfig:'Kubernetes config file. Default loads in-cluster config' = None,
  logging_config:'Logging configuration .ini format' = 'logging.ini'
  ):
  """
  A Pulsar client that sends events from a topic to a Kubeless Function.

  Most of the configuration for this component comes from environment variables,
  passed by the Kubernetes Controller.
  """

  ERROR_BACKOFF_DELAY_INITIAL  = 1
  ERROR_BACKOFF_DELAY_MAX      = 90
  ERROR_BACKOFF_FACTOR         = 5

  timezone           = os.environ.get("TZ")
  if not timezone:
    timezone = "UTC"

  event_name         = os.environ.get("TRIGGER_NAME")
  event_namespace    = os.environ.get("TRIGGER_NAMESPACE")
  event_time         = datetime.datetime.now(pytz.timezone(timezone))
  pulsar_broker      = os.environ.get("PULSAR_BROKER")
  pulsar_topic       = os.environ.get("PULSAR_TOPIC")
  pulsar_authtoken   = os.environ.get("PULSAR_AUTH_TOKEN")
  kubeless_function  = os.environ.get("KUBELESS_FUNCTION")

  if os.environ.get("ERROR_BACKOFF_DELAY_MAX"):
    ERROR_BACKOFF_DELAY_MAX = int(os.environ.get("ERROR_BACKOFF_DELAY_MAX"))
  if os.environ.get("ERROR_BACKOFF_FACTOR"):
    ERROR_BACKOFF_FACTOR = int(os.environ.get("ERROR_BACKOFF_FACTOR"))

  if not pulsar_broker:
    logging.critical("Missing parameter PULSAR_BROKER")
    sys.exit(-1)
  if not pulsar_topic:
    logging.critical("Missing parameter PULSAR_TOPIC_NAME")
    sys.exit(-1)
  if not kubeless_function:
    logging.critical("Missing parameter KUBELESS_FUNCTION")
    sys.exit(-1)

  if not event_name:
    event_name = ""
  if not event_namespace:
    event_namespace = ""

  logging.config.fileConfig(fname=logging_config)

  pulsar_topic_str = "{s}".format(s=pulsar_topic)

  logging.info("Welcome to Kubeless Pulsar Event Dispatcher")
  logging.info("Kubeless endpoint {s}".format(s=kubeless_function))
  logging.info("Pulsar Broker {s}".format(s=pulsar_broker))
  logging.info("Pulsar Topic {s}".format(s=pulsar_topic_str))

  logging.info("Connecting to Pulsar")
  if pulsar_authtoken:
    pulsar_client = pulsar.Client(pulsar_broker, authentication=pulsar.AuthenticationToken(pulsar_authtoken))
  else:
    pulsar_client = pulsar.Client(pulsar_broker)

  consumer = pulsar_client.subscribe(pulsar_topic_str, subscription_name="{n}-{ns}".format(n=event_name,ns=event_namespace))
  error_backoff_delay = ERROR_BACKOFF_DELAY_INITIAL

  while True:
    msg = consumer.receive()
    try:

      ## determine if we have json content
      msg_data_str = msg.data().decode('utf-8')
      http_payload = msg_data_str
      try:
        json.loads(msg_data_str)
        logging.info("Content is json")
      except:
        content_type = 'application/x-www-form-urlencoded'

      http_headers = {
        'Content-Type': content_type,
        'event-id': str(uuid.uuid4()),
        'event-time': str(event_time),
        'event-namespace': event_namespace,
        'event-name': event_name
      }

      r = requests.post(kubeless_function, data=http_payload, headers=http_headers, allow_redirects=True)
      if r.status_code < 200 or r.status_code > 299:
        raise Exception("HTTP Status Code {sc}, response: {body}".format(sc=r.status_code, body=r.text))

      ## upon success, reset error backoff delay
      error_backoff_delay = ERROR_BACKOFF_DELAY_INITIAL
    except Exception as err:
      logging.error(err, exc_info=True)

      ## notify pulsar the message was not processed successfully
      consumer.negative_acknowledge(msg)

      ## back off during repeated errors
      logging.warn("Increasing delay backoff, will continue within {n} seconds".format(n=error_backoff_delay))
      time.sleep(error_backoff_delay)
      if error_backoff_delay < ERROR_BACKOFF_DELAY_MAX:
        error_backoff_delay += ERROR_BACKOFF_FACTOR
      else:
        error_backoff_delay = ERROR_BACKOFF_DELAY_MAX

  pulsar_client.close()

argh.dispatch_command(main)
