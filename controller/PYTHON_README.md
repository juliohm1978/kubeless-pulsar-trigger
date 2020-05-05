# Environment setup

This is a skeleton that combines `pyenv` and `pipenv` to create a Python development environment. It can be used to start a new project quickly.

## Dependencies

Make sure `make`, `python3` and `pip3` are installed.

    sudo apt-get install -y make python3 python3-pip

Install `pipenv` and `virtualenv` packages using `pip`.

    pip3 install --user pipenv virtualenv

Install `pyenv` using the official installer: <https://github.com/pyenv/pyenv-installer>

    ## remove a previous installation
    rm -fr ~/.pyenv

    ## install the most recent
    curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

Configure your shell to use `pyenv` correctly.

For bash:

    ## append to ~/.bash_profile
    eval "$(pyenv init -)"

For fish:

    ## append to ~/.config/fish/config.fish
    status --is-interactive; and source (pyenv init -|psub)

You can acquire the updated version of those shell settings calling `pyenv init` from within your shell.

If the `pyenv` binary cannot be found, add `$HOME/.pyenv/bin` to you `$PATH`.

## Initialize the project environment

Edit the provided `Makefile` and define the preferred Python version to use in `PYENV_VERSION`.

Further `make` targets for your project can also be defined here, replacing the dummy `hello` target. The include directive for `Python.mk` will be used mostly in rare cases. Once to initialize the environment and perhaps to reset the entire project environment.

    make __init

This will create a virtual Python environment with the specified version along most settings, such as `Pipfile`. The virtual environment will live inside `.venv` directory, along with your project. This directory can be ignored by your VCS, since it can be recreated with `make __init`.

The source code for your project is expected to reside in `src`.

You can start a shell into the virtual environment by using `pipenv` as usual.

    pipenv shell

## Reset the environment

You can delete the entire virtual environment using:

    make __reset

**WARNING**: This should only be used as a last resort to fix a corrupted environment. Be aware this will remove `.venv`, along all dependency definitions, such as `Pipfile`, `Pipfile.lock` and `.env`. That means, all your dependencies and most of your configuration will be lost. Aside from the `.venv` directory, make sure you can recover backups or previous versions of those files.
