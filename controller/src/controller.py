#!/usr/local/bin/python

import argh
import json
import pulsar
import kubernetes
import logging
import logging.config
import os

PULSAR_BROKER_DEFAULT = "pulsar://pulsar-broker.pulsar:6650"
PULSAR_TOPIC_DEFAULT  = "persistent://public/cert-watch/cert-updates"

KUBELESS_TRIGGER_NAME     = "pulsartriggers.kubeless.io"
KUBELESS_TRIGGER_GROUP    = "kubeless.io"
KUBELESS_TRIGGER_KIND     = "PulsarTrigger"
KUBELESS_TRIGGER_SINGULAR = "pulsartrigger"
KUBELESS_TRIGGER_PLURAL   = "pulsartriggerss"
KUBELESS_TRIGGER_VERSION  = "v1"

def read_rv(obj):
  """
  Reads the last resource version known from disk. If there isn't one, the
  current object version is returned.
  """

  tmpfile = "/tmp/obj.{namespace}.{name}.rv".format(namespace=obj.metadata.namespace, name=obj.metadata.name)
  rv = None
  try:
    with open(tmpfile) as f:
      rv = f.read()
  except FileNotFoundError:
    save_rv(obj)
    pass
  
  try:
    return int(rv)
  except:
    obj.metadata.resource_version

def save_rv(obj):
  """
  Saves the resource version to disk.
  """
  tmpfile = "/tmp/obj.{namespace}.{name}.rv".format(namespace=obj.metadata.namespace, name=obj.metadata.name)
  with open(tmpfile, "w") as f:
    f.write("{revision}".format(revision=obj.metadata.resource_version))

def main(
  kubeconfig:'Kubernetes config file. Default loads in-cluster config' = None,
  pulsar_broker:'Pulsar broker addr' = PULSAR_BROKER_DEFAULT,
  pulsar_token:'Pulsar authentication token' = None,
  pulsar_topic:'Pulsar topic to subscribe to' = PULSAR_TOPIC_DEFAULT,
  logging_config:'Logging configuration .ini format' = 'logging.ini'
  ):
  """
  Controller main function
  """

  logging.config.fileConfig(fname=logging_config)

  logging.info("Welcome to Kubeless Pulsar Trigger Controller")

  if kubeconfig:
    kubernetes.config.load_kube_config(config_file=kubeconfig)
  else:
    kubernetes.config.load_incluster_config()

  v1 = kubernetes.client.CustomObjectsApi()

  while True:
    try:
      list = v1.list_cluster_custom_object(KUBELESS_TRIGGER_GROUP, KUBELESS_TRIGGER_VERSION, KUBELESS_TRIGGER_PLURAL)
      logging.info(list)
      # while True:
      #   for event in kubernetes.watch.Watch().stream(v1.list_cluster_custom_object, KUBELESS_TRIGGER_GROUP, KUBELESS_TRIGGER_VERSION, KUBELESS_TRIGGER_PLURAL):
      #     obj = event['object']
      #     ev_type = event['type']

      #     if obj.metadata.labels and CERTMANAGER_LABEL in obj.metadata.labels:
      #       last_resource_version = read_rv(obj)
      #       if (last_resource_version) and (int(obj.metadata.resource_version) > last_resource_version) and (ev_type == 'ADDED' or ev_type == 'MODIFIED'):
      #         logging.info("{last_rv} > {rv}, {namespace}/{name} enviado".format(last_rv=last_resource_version, rv=obj.metadata.resource_version, namespace=obj.metadata.namespace, name=obj.metadata.name))
      #         pulsar_producer.send(json.dumps(event['raw_object']).encode('utf-8'))
      #         save_rv(obj)

    except kubernetes.client.rest.ApiException as err:
      if err.status == 404:
        logging.error("Missing CRD: {name}".format(name=KUBELESS_TRIGGER_NAME))
        logging.error("Make sure the controller installation is complete")
      raise err
    except Exception as err:
      raise err

argh.dispatch_command(main)
