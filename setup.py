#!/usr/bin/env python


def get_version():
    d = {}
    execfile("qs/__init__.py", d, d)
    return d["__version__"]

if __name__ == "__main__":
    try:
        from setuptools import setup
    except ImportError:
        from distutils.core import setup
    setup(name='qserve',
          version=get_version(),
          url="https://github.com/pediapress/qserve",
          description="job queue server",
          license="BSD License",
          maintainer="pediapress.com",
          maintainer_email="info@pediapress.com",
          packages=["qs"])
