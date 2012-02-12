
import gevent, greenlet


def pytest_report_header(config):
    return "gevent %s  --  greenlet %s" % (
        gevent.__version__,
        greenlet.__version__)
