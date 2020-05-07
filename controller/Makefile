PYENV_VERSION=3.6.10
TAG=juliohm/kubeless-pulsar-trigger-controller:beta

.PHONY: $(MAKECMDGOALS)

vscode:
	pipenv run code .

docker:
	pipenv lock -r > src/requirements.txt
	docker build -t $(TAG) .

push: docker
	docker push $(TAG)

install:
	helm upgrade --install kpt kubeless-pulsar-trigger/kubeless-pulsar-trigger-crd
	helm upgrade --install kpt kubeless-pulsar-trigger/kubeless-pulsar-trigger

delete:
	helm del kpt

include Python.mk
