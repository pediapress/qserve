
import gevent, greenlet


def pytest_report_header(config):
    return "gevent %s  --  greenlet %s" % (
        ".".join([str(x) for x in gevent.version_info]),
        greenlet.__version__)
