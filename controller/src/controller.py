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

def reconcile_dispatchers(crdApi, deployment_template):
  """
  Reconcile the state of dispatcher pods with the state of trigger objects.
  Dispatcher pods are controlled with a Deployment object.
  """

  ## recover a list of defined pulsartriggers
  trigger_list = crdApi.list_cluster_custom_object(KUBELESS_TRIGGER_GROUP, KUBELESS_TRIGGER_VERSION, KUBELESS_TRIGGER_PLURAL)['items']

  ## recover a list of deployments created by this controller
  v1api = kubernetes.client.AppsV1Api()
  running_depls = v1api.list_deployment_for_all_namespaces(label_selector='created-by=kubeless-pulsar-trigger')

  ## remove orphan deployments, with no associated trigger
  for depl in running_depls.items:
    found = False
    for trigger in trigger_list:
      if depl.metadata.name == trigger['metadata']['name']:
        found = True
    if not found:
      logging.info("Reconciling deployment {ns}/{name} DELETED".format(ns=depl.metadata.namespace, name=depl.metadata.name))
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

    ## add parameters for Pulsar Topic and Kubeless Function to the Deployment
    ## these parameters are passed as environment variables to the dispatcher pod
    container = deployment_merged['spec']['template']['spec']['containers'][0]
    container['env'] = list()
    
    d = dict()
    d['name'] = 'TOPIC_NAMESPACE'
    d['value'] = trigger['spec']['topic-namespace']
    container['env'].append(d)
    
    d = dict()
    d['name'] = 'TOPIC_NAME'
    d['value'] = trigger['spec']['topic-name']
    container['env'].append(d)
    
    d = dict()
    d['name'] = 'KUBELESS_HANDLER'
    d['value'] = trigger['spec']['kubeless-handler']
    container['env'].append(d)

    d = dict()
    d['name'] = 'KUBELESS_FUNCTION'
    d['value'] = trigger['spec']['kubeless-function']
    container['env'].append(d)

    d = dict()
    d['name'] = 'KUBELESS_FUNCTION_NAMESPACE'
    d['value'] = trigger['spec']['kubeless-function-namespace']
    container['env'].append(d)

    ## create a deployment if there isn't one
    if len(dplist.items) <= 0:
      logging.info("Reconciling deployment {ns}/{name} ADDED".format(ns=deployment_merged['metadata']['namespace'], name=deployment_merged['metadata']['name']))
      v1api.create_namespaced_deployment(deployment_merged['metadata']['namespace'], deployment_merged)
    else:
      logging.info("Reconciling deployment {ns}/{name} MODIFED".format(ns=deployment_merged['metadata']['namespace'], name=deployment_merged['metadata']['name']))
      v1api.replace_namespaced_deployment(name=deployment_merged['metadata']['name'], namespace=deployment_merged['metadata']['namespace'], body=deployment_merged)

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

  logging.info("Initial reconciliation")
  reconcile_dispatchers(crdApi, deployment_template)
  while True:
    try:
      for event in kubernetes.watch.Watch().stream(crdApi.list_cluster_custom_object, KUBELESS_TRIGGER_GROUP, KUBELESS_TRIGGER_VERSION, KUBELESS_TRIGGER_PLURAL):
        reconcile_dispatchers(crdApi, deployment_template)
    except Exception as err:
      logging.critical(err, exc_info=True)
    time.sleep(10)

argh.dispatch_command(main)
