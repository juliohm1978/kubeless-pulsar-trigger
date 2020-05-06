# Kubeless Pulsar Trigger

This project implements a Pulsar Trigger for the [Kubeless serverless platform](https://kubeless.io/). In the spirit of how Kubeless works, it defines a new Custom Resource Definition for Kubernetes to represent the a `PulsarTrigger` that reacts to Pulsar topic events, sending the contents to a Kubeless Function of your choice.

The components for this project are implemented in Python 3.6 (the default version for Ubuntu 18.04 LTS at the time). It uses the [Python Kubernetes Client library](https://github.com/kubernetes-client/python), along with a few others to get the job done.

## Architecture

There are two components to this solution:

* Kubernetes Controller - watches PulsarTrigger CRD objects from the Kubernetes API and spins up Dispatcher Pods responsible for processing queue events.
* Dispatcher Pods - subscribe to a sepecific Pulsar topic and send message contents to a Kubeless Function.

Inspired by discussions at the Kubeless project ([here](https://github.com/kubeless/kafka-trigger/issues/24) and [here](https://github.com/kubeless/kubeless/issues/826)), this implementation uses a different approach from the native [Kafka and NATS triggers](https://kubeless.io/docs/pubsub-functions/#kafka). It decouples the Dispatcher Pod logic from the Kubernetes Controller, allowing the queue message processing to scale indepndently from the controller itself.

## Creating a `PulsarTrigger`

Once the controller is running, and you have a Kubeless Function ready to be called, creating a trigger is just a matter if creating an object that uses the PulsarTrigger CRD.

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

The controller itself is only responsible for watching for PulsarTrigger CRDs objects. It reconciles the status of a PulsarTrigger with a Deployment that spins up independent Dispatcher Pods.

By default, the Deployment uses small values for its container resources:

```yaml
resources:
  limits:
    cpu: 1
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi
```

You change those by overriding them in the `deployment` object for your trigger. In fact, the entire Deployment created by the controller can be customized directly in the trigger.

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

You can view the default values used for the [Deployment](controller/src/deployment-template.yaml) and [Container](controller/src/container-template.yaml) specs in the source code.

The trigger parameters (pulsar topic, auth token, function name, etc.) are also added to the Deployment at runtime.

## Dispatcher Pods

This project also includes Docker images used in the dispatcher pods. If you know what you are doing, feel free to replace it to suit your needs.

The dispatcher pods also have one single responsibility: To subscribe to the given Pulsar Topic and send any queued messages to the given Kubeless Function. These parameters come from the `PulsarTrigger` definition that you create and arrive at the dispatcher pods in the form of environment variables.

```bash
PULSAR_TOPIC_NAMESPACE
PULSAR_TOPIC_NAME
PULSAR_BROKER
PULSAR_AUTH_TOKEN
KUBELESS_FUNCTION
KUBELESS_FUNCTION_NAMESPACE
KUBELESS_FUNCTION_SCHEMA
```
