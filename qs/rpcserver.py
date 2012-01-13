#! /usr/bin/env python

import traceback

try:
    import simplejson as json
except ImportError:
    import json

from gevent import pool, server as gserver, Greenlet, getcurrent, queue, spawn, GreenletExit


def key2str(kwargs):
    r = {}
    for k, v in kwargs.items():
        r[str(k)] = v
    return r


class dispatcher(object):
    def __call__(self, req):
        name, kwargs = req
        kwargs = key2str(kwargs)

        assert isinstance(name, basestring), "bad name argument"
        cmdname = str("rpc_" + name)
        m = getattr(self, cmdname, None)
        if not m:
            raise RuntimeError("no such method: %r" % (name, ))
        return m(**kwargs)


class request_handler(dispatcher):
    def __init__(self, client=None, clientid=None, **kw):
        self.client = client
        self.clientid = clientid
        super(request_handler, self).__init__(**kw)

    def shutdown(self):
        super(request_handler, self).shutdown()


class ClientGreenlet(Greenlet):
    clientid = None
    status = ""

    def __str__(self):
        return "<%s: %s>" % (self.clientid, self.status)

    def __repr__(self):
        return "<Client %s>" % self.clientid


class server(object):
    def __init__(self, port=8080, host="", get_request_handler=None, secret=None, is_allowed=None):
        self.port = port
        self.host = host
        self.secret = secret
        self.get_request_handler = get_request_handler
        self.pool = pool.Pool(1024, ClientGreenlet)
        self.streamserver = gserver.StreamServer((host, port), self.handle_client, spawn=self.pool.spawn)
        if hasattr(self.streamserver, "pre_start"):
            self.streamserver.pre_start()
        else:
            self.streamserver.init_socket()  # gevent >= 1.0b1
        self.clientcount = 0

        if is_allowed is None:
            self.is_allowed = lambda x: True
        else:
            self.is_allowed = is_allowed

    def run_forever(self):
        self.streamserver.serve_forever()

    def log(self, msg):
        print msg

    def handle_client(self, sock, addr):
        if not self.is_allowed(addr[0]):
            self.log("+DENY %r" % (addr, ))
            sock.close()
            return

        sockfile = None
        current = getcurrent()
        try:
            self.clientcount += 1
            clientid = "<%s %s:%s>" % (self.clientcount, addr[0], addr[1])
            current.clientid = clientid
            sockfile = sock.makefile()
            lineq = queue.Queue()

            def readlines():
                while 1:
                    line = sockfile.readline()
                    lineq.put(line)
                    if not line:
                        break

            readgr = spawn(readlines)
            readgr.link(lambda _: current.kill())
            current.link(lambda _: readgr.kill())
            handle_request = self.get_request_handler(client=(sock, addr), clientid=clientid)

            # self.log("+connect: %s" % (clientid, ))

            while 1:
                current.status = "idle"
                line = lineq.get()
                if not line:
                    break

                try:
                    req = json.loads(line)
                except ValueError, err:
                    self.log("+protocol error %s: %s" % (clientid, err))
                    break

                current.status = "dispatching: %s" % line[:-1]
                try:
                    d = handle_request(req)
                    response = json.dumps(dict(result=d)) + "\n"
                except GreenletExit:
                    raise
                except Exception, err:
                    response = json.dumps(dict(error=str(err))) + "\n"
                    traceback.print_exc()

                current.status = "sending response: %s" % response[:-1]
                sockfile.write(response)
                sockfile.flush()
        except GreenletExit:
            raise
        except:
            traceback.print_exc()

        finally:
            current.status = "dead"
            # self.log("-disconnect: %s" % (clientid,))
            sock.close()
            if sockfile is not None:
                sockfile.close()
            handle_request.shutdown()
