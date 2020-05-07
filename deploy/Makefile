repo:
	helm repo add kubeless-pulsar-trigger https://juliohm1978.github.io/kubeless-pulsar-trigger/chart-index

install:
	kubectl apply -f crd.yaml
	helm repo up
	helm upgrade --install kpt kubeless-pulsar-trigger/kubeless-pulsar-trigger

delete:
	helm del kpt

deletecrd:
	kubectl delete -f crd.yaml
