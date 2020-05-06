PYENV_VERSION=3.6.10
TAG=juliohm/kubeless-pulsar-trigger-dispatcher:beta

.PHONY: $(MAKECMDGOALS)

vscode:
	pipenv run code .

docker:
	pipenv lock -r > src/requirements.txt
	docker build -t $(TAG) .

push: docker
	docker push $(TAG)


include Python.mk
