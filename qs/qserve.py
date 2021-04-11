#! /usr/bin/env python

from __future__ import print_function

import getopt
import os
import pickle
import sys
from builtins import object
from builtins import str

import gevent
import gevent.pool
from future import standard_library

from qs import jobs, rpcserver, misc

standard_library.install_aliases()


class db(object):
    def __init__(self):
        self.key2data = {}
        self.workq = jobs.workq()


class QPlugin(object):
    def __init__(self, **kw):
        self.running_jobs = {}

    def rpc_qadd(
        self, channel, payload=None, priority=0, job_id=None, wait=False, timeout=None, ttl=None
    ):
        job_id = self.workq.push(
            payload=payload,
            priority=priority,
            channel=channel,
            jobid=job_id,
            timeout=timeout,
            ttl=ttl,
        )
        if not wait:
            return job_id

        res = self.workq.waitjobs([job_id])[0]
        return res._json()

    def rpc_qpull(self, channels=None):
        if not channels:
            channels = []

        j = self.workq.pop(channels)
        self.running_jobs[j.jobid] = j

        return j._json()

    def rpc_qfinish(self, jobid, result=None, error=None, traceback=None):
        if error:
            print("error finish: %s: %r" % (jobid, error))
        else:
            print("finish: %s: %r" % (jobid, result))
        self.workq.finishjob(jobid, result=result, error=error)
        if jobid in self.running_jobs:
            del self.running_jobs[jobid]

    def rpc_qsetinfo(self, jobid, info):
        self.workq.updatejob(jobid, info)

    def rpc_qinfo(self, jobid):
        if jobid in self.workq.id2job:
            return self.workq.id2job[jobid]._json()
        return None

    def rpc_qwait(self, jobids):
        res = self.workq.waitjobs(jobids)
        return [j._json() for j in res]

    def rpc_qkill(self, jobids):
        self.workq.killjobs(jobids)

        for jobid in jobids:
            if jobid in self.running_jobs:
                del self.running_jobs[jobid]

    def rpc_qdrop(self, jobids):
        self.workq.dropjobs(jobids)

    def rpc_qprefixmatch(self, prefix):
        return list(self.workq.prefixmatch(prefix))

    def rpc_getstats(self):
        return self.workq.getstats()

    def shutdown(self):
        for j in list(self.running_jobs.values()):
            # print "reschedule", j
            self.workq.pushjob(j)


class Main(object):
    def __init__(self, port, interface, data_dir, allowed_ips):
        self.port = port
        self.interface = interface
        self.data_dir = data_dir
        self.allowed_ips = allowed_ips
        self.loaddb()

    def loaddb(self):
        data_dir = self.data_dir
        if data_dir is not None:
            if not os.path.isdir(data_dir):
                sys.exit("%r is not a directory" % (data_dir,))
            qpath = os.path.join(data_dir, "workq.pickle")
        else:
            qpath = None

        if qpath and os.path.exists(qpath):
            print("loading", qpath)
            self.db = pickle.load(open(qpath))
            print("loaded", len(self.db.workq.id2job), "jobs")
        else:
            self.db = db()
        self.qpath = qpath

    def savedb(self):
        if self.qpath:
            print("saving", self.qpath)
            pickle.dump(self.db, open(self.qpath, "w"), 2)

    def is_allowed_ip(self, ip):
        return not self.allowed_ips or ip in self.allowed_ips

    def handletimeouts(self):
        self.db.workq.handletimeouts()

    def watchdog(self):
        self.db.workq.dropdead()

    def report(self):
        self.db.workq.report()
        # pool = self.server.pool
        # print "= %s clients" % len(pool)
        # for cl in pool:
        #     print cl
        print()

    def run(self):
        class Handler(rpcserver.RequestHandler, QPlugin):
            def __init__(self, **kwargs):
                super(Handler, self).__init__(**kwargs)

            workq = self.db.workq
            db = self.db

        s = self.server = rpcserver.Server(
            self.port,
            host=self.interface,
            get_request_handler=Handler,
            is_allowed=self.is_allowed_ip,
        )
        self.port = s.stream_server.socket.getsockname()[1]
        print("listening on %s:%s" % (self.interface, self.port))

        loops = [(self.report, 20), (self.watchdog, 15), (self.handletimeouts, 1)]
        workers = gevent.pool.Pool()
        for fun, sleeptime in loops:
            workers.spawn(misc.CallInLoop(sleeptime, fun))

        bs = None
        try:
            backdoor_port = port_from_str(os.environ.get("qserve_backdoor", ""))
        except ValueError:
            pass
        else:
            from gevent import backdoor

            bs = backdoor.BackdoorServer(
                ("localhost", backdoor_port),
                locals=dict(_main=self, workers=workers, server=s, workq=self.db.workq),
            )
            bs.banner = "Welcome to qserve!"
            if hasattr(bs, "pre_start"):
                bs.pre_start()
            else:
                bs.init_socket()  # gevent >= 1.0b1
            print("starting backdoor on 127.0.0.1:%s" % bs.socket.getsockname()[1])
            bs.start()

        try:
            s.run_forever()
        except KeyboardInterrupt:
            print("interrupted")
        finally:
            self.savedb()
            workers.kill()
            if bs is not None:
                bs.kill()


def usage():
    print("mw-qserve [-p PORT] [-i INTERFACE] [-d DATADIR]")


def port_from_str(port):
    port = int(port)
    if port < 0 or port > 65535:
        raise ValueError("bad port")
    return port


def parse_options(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "a:d:p:i:h", ["help", "port=", "interface="])
    except getopt.GetoptError as err:
        print(str(err))
        sys.exit(10)

    if args:
        print("too many arguments")
        sys.exit(10)

    port = 14311
    interface = "0.0.0.0"
    datadir = None
    allowed_ips = set()

    for o, a in opts:
        if o in ("-p", "--port"):
            try:
                port = port_from_str(a)
            except ValueError:
                print("expected positive integer as argument to %s" % o)
                sys.exit(10)
        elif o in ("-i", "--interface"):
            interface = a
        elif o in ("-d"):
            datadir = a
        elif o in ("-a"):
            allowed_ips.add(a)
        elif o in ("-h", "--help"):
            usage()
            sys.exit(0)

    return dict(port=port, interface=interface, datadir=datadir, allowed_ips=allowed_ips)


def main(argv=None):
    Main(**parse_options(argv=argv)).run()


if __name__ == "__main__":
    main()
