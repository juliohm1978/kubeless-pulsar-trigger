# Kubeless Pulsar Trigger

This project implements a Pulsar Trigger for the [Kubeless serverless platform](https://kubeless.io/). In the spirit of how Kubeless works, it defines a new Custom Resource Definition for Kubernetes to represent a `PulsarTrigger`. The trigger controller creates dispatcher pods to handle queue messages, sending the contents to a Kubeless Function of your choice.

The components for this project are implemented in Python 3.6 (the default version for Ubuntu 18.04 LTS at the time). It uses the [Python Kubernetes Client library](https://github.com/kubernetes-client/python), along with a few others to get the job done.

## Architecture

There are two components to this solution:

* Kubernetes Controller - watches PulsarTrigger objects from the Kubernetes API and spins up Dispatcher Pods for processing queue events.
* Dispatcher Pods - subscribe to a sepecific Pulsar topic and send message contents to a Kubeless Function.

Inspired by discussions at the Kubeless project ([here](https://github.com/kubeless/kafka-trigger/issues/24) and [here](https://github.com/kubeless/kubeless/issues/826)), this implementation uses a different approach from the native [Kafka and NATS triggers](https://kubeless.io/docs/pubsub-functions/#kafka). Here, the the queue message processing is decoupled from the controller itself, allowing that part of the solution to scale and evolve independently.

## Installation

A Helm Chart is available in this repository. For a quick installation namespace, use the `Makefile` targetes from the `/deploy` directory.

```bash
cd deploy

## Add this repository to your helm config
make repo

## Quick installation to `default` namespace.
## Use the most recent chart version.
make install
```

For further customization, you can issue `helm` commands manually.

```bash
## Add repo
helm repo add kubeless-pulsar-trigger https://juliohm1978.github.io/kubeless-pulsar-trigger/chart-index
helm repo up

## Don't forget the CRD first
kubectl apply -f crd.yaml

## Install
helm upgrade --install kpt kubeless-pulsar-trigger/kubeless-pulsar-trigger
```

To uninstall, follow the `Makefile` targets:

```bash
## Uninstall the controller
make delete

## Uninstall the CRD
make deletecrd
```

> ***❗️❗️❗️ WARNING** 👉 Removing the CRD definitions will also permanently delete ALL `PulsarTriggers` you may have already created.*

## Creating a `PulsarTrigger`

Once the controller is running, [and you have a Kubeless Function ready](https://kubeless.io/docs/quick-start/), creating a trigger is just a matter if creating a `PulsarTrigger` object.

```yaml
apiVersion: kubeless.io/v1
kind: PulsarTrigger
metadata:
  name: mytrigger
  namespace: default
spec:
  pulsar:
    topic: persistent://public/default/mytopic
    broker: pulsar://pulsar.addr:6650
    auth-token: nnn

  kubeless:
    function: http://myfunction.default:8080
```

The controller itself is only responsible for reconciling the status of `PulsarTriggers`, creating/updating Deployments to handle the actual message processing. That job is handled by dispatcher pods, and a default implementation is also included. Once your `PulsarTrigger` is created, you should see a Deployment and its Pod also created shortly after.

By default, the dispacther pod uses relatively small resource values:

```yaml
resources:
  limits:
    cpu: 1
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi
```

You can change those by overriding specific values in the `deployment` object in your trigger. In fact, the entire Deployment spec can be included.

```yaml
apiVersion: kubeless.io/v1
kind: PulsarTrigger
metadata:
  name: mytrigger
  namespace: default
spec:
  pulsar:
    topic: persistent://public/default/mytopic
    broker: pulsar://pulsar.addr:6650
    auth-token: nnn

  kubeless:
    function: http://myfunction.default:8080

  ## Override any deployment spec from the default template
  deployment:
    metadata:
      namespace: another-namespace
    spec:
      template:
        spec:
          containers:
            - resources:
                limits:
                  cpu: 4
                  memory: 1Gi
                requests:
                  cpu: 1
                  memory: 512Mi
```

> ***NOTE**: Please, be aware of how the controller merges your Deployment spec with an internal default template. While most Deployment values can be safely overriden, the controller assumes the first container in the list as the dispatcher. It is currently not possible to include more than one container in that pod. The internal logic merges and replaces the container list using the specs from your trigger. A more flexible implementation is planned for future versions.*

You can view the default values used for the [Deployment](controller/src/deployment-template.yaml) and [Container](controller/src/container-template.yaml) specs in the source code.

The trigger parameters (pulsar topic, auth token, function name, etc.) are also added to the Deployment at runtime.

## Dispatcher Pods

This project also includes Docker images used in the dispatcher pods. They also have one single responsibility: subscribe to the given Pulsar Topic and send any queued messages to the given Kubeless Function. These parameters come from the `PulsarTrigger` definition that you create and arrive at the dispatcher pods in the form of environment variables.

```bash
PULSAR_TOPIC_NAMESPACE
PULSAR_TOPIC_NAME
PULSAR_BROKER
PULSAR_AUTH_TOKEN
KUBELESS_FUNCTION
KUBELESS_FUNCTION_NAMESPACE
KUBELESS_FUNCTION_PORT
KUBELESS_FUNCTION_SCHEMA

## additional values passed
TRIGGER_NAME
TRIGGER_NAMESPACE
TIMEZONE
```

The included containers for dispatcher pods are also implemented in Python with a simple example of a Pulsar client. It includes an increasing backoff delay on repeated errors while calling the Kubeless Function (up to 90s). If you need more advanced message handling and know what you are doing, feel free to replace it to suit your needs. You can override the container image from your `PulsarTrigger` definition (explained above).
