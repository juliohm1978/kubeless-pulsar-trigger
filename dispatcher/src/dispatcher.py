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

ERROR_BACKOFF_DELAY_INITIAL  = 1
ERROR_BACKOFF_DELAY_MAX      = 90
ERROR_BACKOFF_FACTOR         = 5

def main(
  kubeconfig:'Kubernetes config file. Default loads in-cluster config' = None,
  logging_config:'Logging configuration .ini format' = 'logging.ini'
  ):
  """
  A Pulsar client that sends events from a topic to a Kubeless Function.

  Most of the configuration for this component comes from environment variables,
  passed by the Kubernetes Controller.
  """

  timezone           = os.environ.get("TZ")
  if not timezone:
    timezone = "UTC"

  event_name         = os.environ.get("TRIGGER_NAME")
  event_namespace    = os.environ.get("TRIGGER_NAMESPACE")
  event_time         = datetime.datetime.now(pytz.timezone(timezone))
  pulsar_broker      = os.environ.get("PULSAR_BROKER")
  pulsar_namespace   = os.environ.get("PULSAR_TOPIC_NAMESPACE")
  pulsar_topic       = os.environ.get("PULSAR_TOPIC_NAME")
  pulsar_topic_type  = os.environ.get("PULSAR_TOPIC_TYPE")
  pulsar_authtoken   = os.environ.get("PULSAR_AUTH_TOKEN")
  kubeless_namespace = os.environ.get("KUBELESS_FUNCTION_NAMESPACE")
  kubeless_function  = os.environ.get("KUBELESS_FUNCTION")
  kubeless_port      = os.environ.get("KUBELESS_FUNCTION_PORT")
  kubeless_schema    = os.environ.get("KUBELESS_FUNCTION_SCHEMA")

  if os.environ.get("ERROR_BACKOFF_DELAY_MAX"):
    ERROR_BACKOFF_DELAY_MAX = int(os.environ.get("ERROR_BACKOFF_DELAY_MAX"))
  if os.environ.get("ERROR_BACKOFF_FACTOR"):
    ERROR_BACKOFF_FACTOR = int(os.environ.get("ERROR_BACKOFF_FACTOR"))

  if not pulsar_broker:
    logging.critical("Missing parameter PULSAR_BROKER")
    sys.exit(-1)
  if not pulsar_namespace:
    logging.critical("Missing parameter PULSAR_TOPIC_NAMESPACE")
    sys.exit(-1)
  if not pulsar_topic:
    logging.critical("Missing parameter PULSAR_TOPIC_NAME")
    sys.exit(-1)
  if not kubeless_namespace:
    logging.critical("Missing parameter KUBELESS_FUNCTION_NAMESPACE")
    sys.exit(-1)
  if not kubeless_function:
    logging.critical("Missing parameter KUBELESS_FUNCTION")
    sys.exit(-1)
  if not kubeless_port:
    logging.critical("Missing parameter KUBELESS_FUNCTION_PORT")
    sys.exit(-1)

  if not event_name:
    event_name = ""
  if not event_namespace:
    event_namespace = ""
  if not pulsar_topic_type:
    pulsar_topic_type = "persistent"
  if not kubeless_schema:
    kubeless_schema = "http"

  logging.config.fileConfig(fname=logging_config)

  pulsar_topic_str = "{type}://{n}/{t}".format(
    type=pulsar_topic_type,
    n=pulsar_namespace,
    t=pulsar_topic
  )

  logging.info("Welcome to Kubeless Pulsar Event Dispatcher")
  logging.info("Kubeless endpoint {s}://{f}.{n}:{p}".format(
    s=kubeless_schema,
    f=kubeless_function,
    n=kubeless_namespace,
    p=kubeless_port
  ))
  logging.info("Pulsar Broker {b}".format(b=pulsar_broker))
  logging.info("Pulsar Topic {t}".format(t=pulsar_topic_str))

  logging.info("Connecting to Pulsar")
  if pulsar_authtoken:
    pulsar_client = pulsar.Client(pulsar_broker, authentication=pulsar.AuthenticationToken(pulsar_authtoken))
  else:
    pulsar_client = pulsar.Client(pulsar_broker)

  consumer = pulsar_client.subscribe(pulsar_topic_str, subscription_name="{n}-{ns}".format(n=event_name,ns=event_namespace))
  error_backoff_delay = ERROR_BACKOFF_DELAY_INITIAL

  function_url = "{s}://{fn}.{ns}:{port}".format(
    s=kubeless_schema,
    fn=kubeless_function,
    ns=kubeless_namespace,
    port=kubeless_port
  )

  while True:
    msg = consumer.receive()
    try:
      logging.debug("Message: {m}".format(msg))
      
      try:
        http_payload = json.loads(msg.data)
        content_type = 'application/json'
      except:
        http_payload = msg.data
        content_type = 'application/x-www-form-urlencoded'

      http_headers = {
        'Content-Type': content_type,
        'event-id': msg.message_id,
        'event-time': event_time,
        'event-namespace': event_namespace,
        'event-name': event_name
      }

      r = requests.post(function_url, data=http_payload, headers=http_headers, allow_redirects=True)
      if r.status_code < 200 or r.status_code > 299:
        raise Exception("HTTP Status Code {sc}, response: {body}".format(sc=r.status_code, body=r.text))

      ## upon success, reset error backoff delay
      error_backoff_delay = ERROR_BACKOFF_DELAY_INITIAL
    except Exception as err:
      logging.error(err, exc_info=True)

      ## notify pulsar the message was not processed successfully
      consumer.negative_acknowledge(msg)

      ## back off during repeated errors
      logging.warn("Increasing delay backoff, will retry within {n} seconds".format(n=error_backoff_delay))
      time.sleep(error_backoff_delay)
      if error_backoff_delay < ERROR_BACKOFF_DELAY_MAX:
        error_backoff_delay += ERROR_BACKOFF_FACTOR
      else:
        error_backoff_delay = ERROR_BACKOFF_DELAY_MAX

  pulsar_client.close()

argh.dispatch_command(main)
