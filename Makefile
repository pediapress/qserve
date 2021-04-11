IMAGE_LABEL ?= "latest"
IMAGE_NAME=qserve

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

docker-build-py27::
	docker build -f Dockerfile-py27 -t ${IMAGE_NAME}-py27:${IMAGE_LABEL} .

docker-debug-py27::
	docker run -it --rm --entrypoint='' \
		${IMAGE_NAME}-py27:${IMAGE_LABEL} bash

docker-test-py27:: docker-build-py27
	docker run --rm ${IMAGE_NAME}-py27:${IMAGE_LABEL}
