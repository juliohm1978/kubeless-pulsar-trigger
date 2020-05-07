repo:
	helm repo add kubeless-pulsar-trigger https://juliohm1978.github.io/kubeless-pulsar-trigger/chart-index
	helm repo up
	helm search repo kubeless

install:
	helm repo add kubeless-pulsar-trigger https://juliohm1978.github.io/kubeless-pulsar-trigger/chart-index
	helm repo up
	helm upgrade --install kpt kubeless-pulsar-trigger/kubeless-pulsar-trigger

delete:
	helm del kpt
