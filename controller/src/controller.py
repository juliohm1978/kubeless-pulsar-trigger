#!/usr/local/bin/python

import argh
import json
import pulsar
import kubernetes
import logging
import logging.config
import time
import hiyapyco

PULSAR_BROKER_DEFAULT = "pulsar://pulsar-broker.pulsar:6650"
PULSAR_TOPIC_DEFAULT  = "persistent://public/default/mytopic"

KUBELESS_TRIGGER_NAME     = "pulsartriggers.kubeless.io"
KUBELESS_TRIGGER_GROUP    = "kubeless.io"
KUBELESS_TRIGGER_KIND     = "PulsarTrigger"
KUBELESS_TRIGGER_SINGULAR = "pulsartrigger"
KUBELESS_TRIGGER_PLURAL   = "pulsartriggers"
KUBELESS_TRIGGER_VERSION  = "v1"

def deep_merge(a, b, path=None):
    "Deep merge dicts b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                deep_merge(a[key], b[key], path + [str(key)])
            elif a[key] != b[key]:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a

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

def reconcile_dispatchers(trigger_list, deployment_template):
  """
  Reconcile the state of dispatcher pods with the state of trigger objects.
  """
  logging.info("Reconciling dispatchers")
  v1api = kubernetes.client.AppsV1Api()
  running_depls = v1api.list_deployment_for_all_namespaces(label_selector='created-by=kubeless-pulsar-trigger')

  ## remove orphan deployments, with no associated trigger
  for depl in running_depls.items:
    found = False
    for trigger in trigger_list:
      if depl.metadata.name == trigger['metadata']['name']:
        found = True
    if not found:
      logging.info("Reconciling deployment {ns}/{name} DELETE".format(ns=depl.metadata.namespace, name=depl.metadata.name))
      v1api.delete_namespaced_deployment(depl.metadata.name, depl.metadata.namespace)

  ## loop throug all triggers and find the corresponding deployment
  for trigger in trigger_list:
    deployment_merged = deployment_template
    if 'deployment' in trigger['spec'] and trigger['spec']['deployment']:
      deployment_merged = deep_merge(deployment_template, trigger['spec']['deployment'])
    deployment_merged['metadata']['name'] = trigger['metadata']['name']
    dplist = v1api.list_deployment_for_all_namespaces(
      field_selector="metadata.namespace={ns},metadata.name={name}".format(
        ns=deployment_merged['metadata']['namespace'],
        name=deployment_merged['metadata']['name']
      )
    )
    ## create a deployment if there isn't one
    if len(dplist.items) <= 0:
      logging.info("Reconciling deployment {ns}/{name} CREATE".format(ns=deployment_merged['metadata']['namespace'], name=deployment_merged['metadata']['name']))
      v1api.create_namespaced_deployment(deployment_merged['metadata']['namespace'], deployment_merged)
    
  logging.info('Reconciliation done')

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

  logging.info("Loading deployment template")
  deployment_template = hiyapyco.load('deployment-template.yaml')

  if kubeconfig:
    kubernetes.config.load_kube_config(config_file=kubeconfig)
  else:
    kubernetes.config.load_incluster_config()

  crdApi = kubernetes.client.CustomObjectsApi()

  ## global list of triggers
  trigger_list = []

  logging.info("Initial trigger load")
  list = crdApi.list_cluster_custom_object(KUBELESS_TRIGGER_GROUP, KUBELESS_TRIGGER_VERSION, KUBELESS_TRIGGER_PLURAL)
  for item in list['items']:
    trigger_list.append(item)
  reconcile_dispatchers(trigger_list, deployment_template)

  while True:
    time.sleep(10)
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

argh.dispatch_command(main)
