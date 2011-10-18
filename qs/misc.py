
import sys
import gevent
import traceback

def safecall(fun, *args, **kwargs):
    try:
        return fun(*args, **kwargs)
    except gevent.GreenletExit:
        raise
    except:
        pass

class call_in_loop(object):
    def __init__(self, sleep_time, function, *args, **kwargs):
        self.sleep_time = sleep_time
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def iterate(self):
        try:
            self.function(*self.args, **self.kwargs)
        except gevent.GreenletExit:
            raise
        except:
            safecall(self.report_error)
        safecall(gevent.sleep, self.sleep_time)

    def __call__(self):
        while 1:
            try:
                self.iterate()
            except gevent.GreenletExit:
                raise
            except:
                pass

    def report_error(self):
        exc_info = sys.exc_info()
        sys.stderr.write("\nError while calling %s:\n" % self.function)
        traceback.print_exception(*exc_info)
        sys.stderr.write("\n")