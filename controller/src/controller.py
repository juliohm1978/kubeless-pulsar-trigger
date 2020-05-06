#!/usr/local/bin/python

import argh
import json
import kubernetes
import logging
import logging.config
import time
import hiyapyco
import copy

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

def reconcile_dispatchers(crdApi, deployment_template, container_template, timezone):
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

  ## loop throug all triggers, create/update deployments
  for trigger in trigger_list:
    deployment_merged = copy.deepcopy(deployment_template)
    container_merged  = copy.deepcopy(container_template)
    
    ## merge deployment and container specs to the values coming from the trigger
    if 'deployment' in trigger['spec'] and trigger['spec']['deployment']:
      deployment_merged = deep_merge(deployment_merged, trigger['spec']['deployment'])

      ## merge container spec
      if 'spec' in trigger['spec']['deployment']:
        if 'template' in trigger['spec']['deployment']['spec']:
          if 'spec' in trigger['spec']['deployment']['spec']['template']:
            if 'containers' in trigger['spec']['deployment']['spec']['template']['spec'] and len(trigger['spec']['deployment']['spec']['template']['spec']['containers']) > 0:
              container_merged = deep_merge(container_merged, trigger['spec']['deployment']['spec']['template']['spec']['containers'][0])
      
      ## add merged container spec to the deployment
      deployment_merged['spec']['template']['spec']['containers'] = list()
      deployment_merged['spec']['template']['spec']['containers'].append(container_merged)
    
    ## give the deployment the same name as the trigger
    deployment_merged['metadata']['name'] = trigger['metadata']['name']
    
    ## check if the deployment already exists
    dplist = v1api.list_deployment_for_all_namespaces(
      field_selector="metadata.namespace={ns},metadata.name={name}".format(
        ns=deployment_merged['metadata']['namespace'],
        name=deployment_merged['metadata']['name']
      )
    )

    ## Add parameters to the Deployment.
    ## These parameters are passed as environment variables to the dispatcher pod.
    container = deployment_merged['spec']['template']['spec']['containers'][0]
    container['env'] = list()
    
    d = dict()
    d['name'] = 'TRIGGER_NAME'
    d['value'] = trigger['metadata']['name']
    container['env'].append(d)
    
    d = dict()
    d['name'] = 'TRIGGER_NAMESPACE'
    d['value'] = trigger['metadata']['namespace']
    container['env'].append(d)
    
    ## use the timezone configured for this controller
    d = dict()
    d['name'] = 'TZ'
    d['value'] = timezone
    container['env'].append(d)
    
    d = dict()
    d['name'] = 'PULSAR_TOPIC_NAMESPACE'
    d['value'] = trigger['spec']['pulsar']['namespace']
    container['env'].append(d)
    
    d = dict()
    d['name'] = 'PULSAR_TOPIC_NAME'
    d['value'] = trigger['spec']['pulsar']['topic']
    container['env'].append(d)
    
    d = dict()
    d['name'] = 'PULSAR_BROKER'
    d['value'] = trigger['spec']['pulsar']['broker']
    container['env'].append(d)
    
    if 'auth-token' in trigger['spec']['pulsar']:
      d = dict()
      d['name'] = 'PULSAR_AUTH_TOKEN'
      d['value'] = trigger['spec']['pulsar']['auth-token']
      container['env'].append(d)
    
    d = dict()
    d['name'] = 'KUBELESS_FUNCTION_NAMESPACE'
    d['value'] = trigger['spec']['kubeless']['namespace']
    container['env'].append(d)

    d = dict()
    d['name'] = 'KUBELESS_FUNCTION'
    d['value'] = trigger['spec']['kubeless']['function']
    container['env'].append(d)

    d = dict()
    d['name'] = 'KUBELESS_FUNCTION_PORT'
    d['value'] = str(trigger['spec']['kubeless']['port'])
    container['env'].append(d)

    d = dict()
    d['name'] = 'KUBELESS_FUNCTION_SCHEME'
    if 'scheme' in trigger['spec']['kubeless']:
      d['value'] = trigger['spec']['kubeless']['scheme']
    else:
      d['value'] = "http"
    container['env'].append(d)

    ## create a deployment if there isn't one
    if len(dplist.items) <= 0:
      logging.info("Reconciling deployment {ns}/{name} ADDED".format(ns=deployment_merged['metadata']['namespace'], name=deployment_merged['metadata']['name']))
      logging.debug(deployment_merged)
      v1api.create_namespaced_deployment(deployment_merged['metadata']['namespace'], deployment_merged)
    else:
      logging.info("Reconciling deployment {ns}/{name} MODIFED".format(ns=deployment_merged['metadata']['namespace'], name=deployment_merged['metadata']['name']))
      v1api.replace_namespaced_deployment(name=deployment_merged['metadata']['name'], namespace=deployment_merged['metadata']['namespace'], body=deployment_merged)

  logging.info('Reconciliation done')

def main(
  kubeconfig:'Kubernetes config file. Default loads in-cluster config' = None,
  logging_config:'Logging configuration .ini format' = 'logging.ini',
  timezone:'Local timezone to use in Python timestamps' = 'UTC'
  ):
  """
  K8S controller for PulsarTrigger objects.
  """

  logging.config.fileConfig(fname=logging_config)

  logging.info("Welcome to Kubeless Pulsar Trigger Controller")

  logging.info("Loading deployment template")
  deployment_template = hiyapyco.load('deployment-template.yaml')
  container_template = hiyapyco.load('container-template.yaml')

  if kubeconfig:
    kubernetes.config.load_kube_config(config_file=kubeconfig)
  else:
    kubernetes.config.load_incluster_config()

  crdApi = kubernetes.client.CustomObjectsApi()

  logging.info("Initial reconciliation")
  reconcile_dispatchers(crdApi, deployment_template, container_template, timezone)
  while True:
    try:
      for event in kubernetes.watch.Watch().stream(crdApi.list_cluster_custom_object, KUBELESS_TRIGGER_GROUP, KUBELESS_TRIGGER_VERSION, KUBELESS_TRIGGER_PLURAL):
        reconcile_dispatchers(crdApi, deployment_template, container_template, timezone)
    except Exception as err:
      logging.critical(err, exc_info=True)
    time.sleep(30)

argh.dispatch_command(main)
