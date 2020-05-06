# Kubeless Pulsar Trigger

This project implements a Pulsar Trigger for the [Kubeless serverless platform](https://kubeless.io/). In the spirit of how Kubeless works, it defines a new Custom Resource Definition for Kubernetes to represent a `PulsarTrigger`. The trigger controller creates dispatcher pods to handle queue messages, sending the contents to a Kubeless Function of your choice.

The components for this project are implemented in Python 3.6 (the default version for Ubuntu 18.04 LTS at the time). It uses the [Python Kubernetes Client library](https://github.com/kubernetes-client/python), along with a few others to get the job done.

## Architecture

There are two components to this solution:

* Kubernetes Controller - watches PulsarTrigger objects from the Kubernetes API and spins up Dispatcher Pods for processing queue events.
* Dispatcher Pods - subscribe to a sepecific Pulsar topic and send message contents to a Kubeless Function.

Inspired by discussions at the Kubeless project ([here](https://github.com/kubeless/kafka-trigger/issues/24) and [here](https://github.com/kubeless/kubeless/issues/826)), this implementation uses a different approach from the native [Kafka and NATS triggers](https://kubeless.io/docs/pubsub-functions/#kafka). Here, the the queue message processing is decoupled from the controller itself, allowing that part of the solution to scale and evolve independently.

## Installation

TODO: helm chart and instructions

## Creating a `PulsarTrigger`

Once the controller is running, and you have a Kubeless Function ready, creating a trigger is just a matter if creating an object that uses the `PulsarTrigger` CRD.

```yaml
apiVersion: kubeless.io/v1
kind: PulsarTrigger
metadata:
  name: mytrigger
  namespace: default
spec:
  ## Pulsar Topic persistent://public/default/mytopic
  pulsar:
    namespace: default
    topic: mytopic
    broker: pulsar://pulsar.addr:6650
    auth-token: nnn

  ## Function http://myfunction.default:8080
  kubeless:
    namespace: default
    function: myfunction
    port: 8080
    schema: http
```

The controller itself is only responsible for reconciling the status of `PulsarTrigger` objects, creating/updating Deployments to handle the actual message processing.

By default, the dispacther pod container uses small values for its resources:

```yaml
resources:
  limits:
    cpu: 1
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi
```

You can change those by overriding specific values in the `deployment` object in your trigger. In fact, the entire Deployment spec can be included directly in the trigger.

```yaml
apiVersion: kubeless.io/v1
kind: PulsarTrigger
metadata:
  name: mytrigger
  namespace: default
spec:
  ## Pulsar Topic persistent://public/default/mytopic
  pulsar:
    namespace: default
    topic: mytopic
    broker: pulsar://pulsar.addr:6650
    auth-token: nnn

  ## Function http://myfunction.default:8080
  kubeless:
    namespace: default
    function: myfunction
    port: 8080
    schema: http

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

> ***NOTE**: Please, be aware of how the controller merges your Deployment spec with the default template. The controller assumes the first container in the Deployment is the dispatcher. It is currently not possible to include more containers in that pod. The controller merges the default template with the deployment/container specs you defined, replacing the container list for the Deployment. A better merge logic is planned for the future versions.*

You can view the default values used for the [Deployment](controller/src/deployment-template.yaml) and [Container](controller/src/container-template.yaml) specs in the source code.

The trigger parameters (pulsar topic, auth token, function name, etc.) are also added to the Deployment at runtime.

## Dispatcher Pods

This project also includes Docker images used in the dispatcher pods. They also have one single responsibility: To subscribe to the given Pulsar Topic and send any queued messages to the given Kubeless Function. These parameters come from the `PulsarTrigger` definition that you create and arrive at the dispatcher pods in the form of environment variables.

```bash
PULSAR_TOPIC_NAMESPACE
PULSAR_TOPIC_NAME
PULSAR_BROKER
PULSAR_AUTH_TOKEN
KUBELESS_FUNCTION
KUBELESS_FUNCTION_NAMESPACE
KUBELESS_FUNCTION_SCHEMA
```

The included containers for dispatcher pods are also implemented in Python with the simple example of a Pulsar client. If you know what you are doing, feel free to replace it to suit your needs. You can override the container image from your `PulsarTrigger` definition (explained above).