PYENV_VERSION=3.6.10
TAG=cert-watch:1.0

.PHONY: $(MAKECMDGOALS)

vscode:
	pipenv run code .

docker:
	pipenv lock -r > src/requirements.txt
	cd ../ && ./build --cache cert-watch --tag $(TAG)

push:
	cd ../ && ./build --cache cert-watch --tag $(TAG) --push


include Python.mk
