pip-compile:
	pip install -U pip-tools
	pip-compile requirements.in

pip-compile-dev:
	pip install -U pip-tools
	pip-compile requirements-dev.in

install:: pip-compile pip-compile-dev
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
#	pip install -e .s