repo:
	helm repo add kubeless-pulsar-trigger https://juliohm1978.github.io/kubeless-pulsar-trigger/chart-index
	helm repo up

install: repo
	kubectl apply -f crd.yaml
	helm upgrade --install kpt kubeless-pulsar-trigger/kubeless-pulsar-trigger

delete:
	helm del kpt
