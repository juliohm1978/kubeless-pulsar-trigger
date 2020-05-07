include ../common.mk

docker:
	pipenv lock -r > src/requirements.txt
	docker build -t $(CONTROLLER_TAG) .

push: docker
	docker push $(CONTROLLER_TAG)

vscode:
	pipenv run code .

include Python.mk
