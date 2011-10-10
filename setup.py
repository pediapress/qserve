#!/usr/bin/env python


def get_version():
    d = {}
    try:
        execfile("qs/__init__.py", d, d)
    except (ImportError, RuntimeError):
        pass
    return d["__version__"]


from distutils.core import setup
setup(name='qserve',
      version=get_version(),
      url="https://github.com/pediapress/qserve",
      description="job queue server",
      license="BSD License",
      maintainer="pediapress.com",
      maintainer_email="info@pediapress.com",
      packages=["qs"])
