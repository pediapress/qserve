#! /usr/bin/env python

from __future__ import print_function

import traceback
from builtins import object
from builtins import str

from past.builtins import basestring

try:
    import simplejson as json
except ImportError:
    import json

from gevent import pool, server as gserver, Greenlet, getcurrent, queue, spawn, GreenletExit


def key2str(kwargs):
    r = {}
    for k, v in list(kwargs.items()):
        r[str(k)] = v
    return r


class Dispatcher(object):
    def __call__(self, req):
        name, kwargs = req
        kwargs = key2str(kwargs)

        assert isinstance(name, basestring), "bad name argument"
        cmd_name = str("rpc_" + name)
        m = getattr(self, cmd_name, None)
        if not m:
            raise RuntimeError("no such method: %r" % (name,))
        return m(**kwargs)


class RequestHandler(Dispatcher):
    def __init__(self, client=None, client_id=None, **kw):
        self.client = client
        self.client_id = client_id
        super(RequestHandler, self).__init__(**kw)

    def shutdown(self):
        super(RequestHandler, self).shutdown()


class ClientGreenlet(Greenlet):
    client_id = None
    status = ""

    def __str__(self):
        return "<%s: %s>" % (self.client_id, self.status)

    def __repr__(self):
        return "<Client %s>" % self.client_id


class Server(object):
    def __init__(self, port=8080, host="", get_request_handler=None, secret=None, is_allowed=None):
        self.port = port
        self.host = host
        self.secret = secret
        self.get_request_handler = get_request_handler
        self.pool = pool.Pool(1024, ClientGreenlet)
        self.stream_server = gserver.StreamServer(
            (host, port), self.handle_client, spawn=self.pool.spawn
        )
        if hasattr(self.stream_server, "pre_start"):
            self.stream_server.pre_start()
        else:
            self.stream_server.init_socket()  # gevent >= 1.0b1
        self.client_count = 0

        if is_allowed is None:
            self.is_allowed = lambda x: True
        else:
            self.is_allowed = is_allowed

    def run_forever(self):
        self.stream_server.serve_forever()

    def log(self, msg):
        print(msg)

    def handle_client(self, sock, addr):
        if not self.is_allowed(addr[0]):
            self.log("+DENY %r" % (addr,))
            sock.close()
            return

        sock_file = None
        current = getcurrent()
        try:
            self.client_count += 1
            clientid = "<%s %s:%s>" % (self.client_count, addr[0], addr[1])
            current.clientid = clientid
            sock_file = sock.makefile()
            lineq = queue.Queue()

            def readlines():
                while 1:
                    try:
                        line = sock_file.readline()
                    except Exception as e:
                        self.log("error reading socket: {}".format(e))
                        break
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
                except ValueError as err:
                    self.log("+protocol error %s: %s" % (clientid, err))
                    break

                current.status = "dispatching: %s" % line[:-1]
                try:
                    d = handle_request(req)
                    response = json.dumps(dict(result=d)) + "\n"
                except GreenletExit:
                    raise
                except Exception as err:
                    response = json.dumps(dict(error=str(err))) + "\n"
                    traceback.print_exc()

                current.status = "sending response: %s" % response[:-1]
                sock_file.write(response)
                sock_file.flush()
        except GreenletExit:
            raise
        except:
            traceback.print_exc()

        finally:
            current.status = "dead"
            # self.log("-disconnect: %s" % (clientid,))
            sock.close()
            if sock_file is not None:
                sock_file.close()
            handle_request.shutdown()
