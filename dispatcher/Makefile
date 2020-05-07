include ../common.mk

docker:
	pipenv lock -r > src/requirements.txt
	docker build -t $(DISPATCHER_TAG) .

push: docker
	docker push $(DISPATCHER_TAG)

vscode:
	pipenv run code .

include Python.mk
