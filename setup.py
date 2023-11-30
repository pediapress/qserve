#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    description="job queue server",
    install_requires=["future"],
    license="BSD License",
    maintainer="pediapress.com",
    maintainer_email="info@pediapress.com",
    name="qserve",
    packages=find_packages(),
    url="https://github.com/pediapress/qserve",
    version="0.3.1",
)
