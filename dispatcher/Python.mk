__init:
	mkdir -p src
	echo -n $(PYENV_VERSION) > .python-version
	pyenv install --skip-existing
	virtualenv -p `pyenv root`/shims/python .venv
	pipenv install

__reset:
	rm -fr .venv
	rm -fr .python-version

__hardreset: reset
	rm -fr Pipfile Pipfile.lock

__shell:
	pipenv shell

__requirements:
	pipenv lock -r > src/requirements.txt