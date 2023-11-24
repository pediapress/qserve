#! /usr/bin/env python

import os
import sys
import time
import traceback
from builtins import object
from builtins import range
from builtins import str

from past.utils import old_div

from qs.rpcclient import ServerProxy


def short_err_msg():
    etype, val, tb = sys.exc_info()
    msg = []
    a = msg.append

    a(etype.__name__)
    a(": ")
    a(str(val))

    file, lineno, name, line = traceback.extract_tb(tb)[-1]
    a(" in function %s, file %s, line %s" % (name, file, lineno))

    return "".join(msg)


class Worker:
    def __init__(self, proxy):
        self.proxy = proxy

    def dispatch(self, job):
        self.job = job
        self.jobid = job["jobid"]
        self.priority = job["priority"]
        self.jobid_prefix = None

        method = job["channel"]
        
        method_name = f"rpc_{method}"

        m = getattr(self, method_name, None)
        if m is None:
            raise RuntimeError("no such method %r" % (method_name,))

        kwargs = job.get("payload") or dict()
        tmp = {}
        for k, v in list(kwargs.items()):
            if isinstance(k, str):
                tmp[str(k)] = v
            else:
                tmp[k] = v
        return m(**tmp)

    def q_set_info(self, info):
        return self.proxy.q_set_info(jobid=self.jobid, info=info)

    def qadd(
        self, channel, payload=None, jobid=None, prefix=None, wait=False, timeout=None, ttl=None
    ):
        """call q_add on proxy with the same priority as the current job"""
        if jobid is None and prefix is not None:
            jobid = "%s::%s" % (prefix, channel)

        return self.proxy.qadd(
            channel=channel,
            payload=payload,
            priority=self.priority,
            jobid=jobid,
            wait=wait,
            timeout=timeout,
            ttl=ttl,
        )

    def qaddw(self, channel, payload=None, jobid=None, timeout=None):
        r = self.proxy.qadd(
            channel=channel,
            payload=payload,
            priority=self.priority,
            jobid=jobid,
            wait=True,
            timeout=timeout,
        )
        error = r.get("error")
        if error is not None:
            raise RuntimeError(error)

        return r["result"]


def main(
    commands, host="localhost", port=None, numthreads=10, num_procs=0, numgreenlets=0, argv=None
):
    if port is None:
        port = 14311
    channels = []
    skip_channels = []

    if argv:
        import getopt

        try:
            opts, args = getopt.getopt(
                argv, "c:s:", ["host=", "port=", "numthreads=", "numprocs=", "channel=", "skip="]
            )
        except getopt.GetoptError as err:
            print(str(err))
            sys.exit(10)

        for o, a in opts:
            if o == "--host":
                host = a
            if o == "--port":
                port = int(a)
            if o == "--numthreads":
                numthreads = int(a)
                num_procs = 0
            if o == "--numprocs":
                num_procs = int(a)
                numthreads = 0
            if o == "-c" or o == "--channel":
                channels.append(a)
            if o == "-s" or o == "--skip":
                skip_channels.append(a)

    class WorkHandler(Worker, commands):
        pass

    available_channels = []
    for x in dir(WorkHandler):
        if x.startswith("rpc_"):
            available_channels.append(x[len("rpc_") :])
    available_channels.sort()

    if not channels:
        channels = available_channels
    else:
        for c in channels:
            assert c in available_channels, "no such channel: %s" % c

    for c in skip_channels:
        channels.remove(c)

    assert channels, "no channels"

    if num_procs:

        def check_parent():
            if os.getppid() == 1:
                print("parent died. exiting.")
                os._exit(0)

    else:

        def check_parent():
            pass

    def handle_one_job(server_proxy: ServerProxy):
        print("SLAVE HANDLING", server_proxy)
        sleeptime = 0.5

        while 1:
            try:
                job = server_proxy.qpull(channels=channels)
                break
            except Exception as err:
                check_parent()
                print("Error while calling pulljob:", str(err))
                time.sleep(sleeptime)
                check_parent()
                if sleeptime < 60:
                    sleeptime *= 2

        check_parent()
        print("got job:", job)
        try:
            print(server_proxy)
            result = WorkHandler(server_proxy).dispatch(job)
        except Exception as err:
            print("error:", err)
            try:
                server_proxy.qfinish(jobid=job["jobid"], error=short_err_msg())
                traceback.print_exc()
            except:
                pass
            return

        try:
            server_proxy.qfinish(jobid=job["jobid"], result=result)
        except:
            pass

    def start_worker():
        print("Server proxy form start_worker", host, port)
        qs = ServerProxy(host=host, port=port)
        while 1:
            handle_one_job(qs)

    print("pulling jobs from", "%s:%s" % (host, port), "for", ", ".join(channels))

    def run_with_threads():
        import threading
        for i in range(numthreads):
            t = threading.Thread(target=start_worker)
            t.start()

        try:
            while True:
                time.sleep(2 ** 26)
        finally:
            os._exit(0)

    def run_with_procs():
        children = set()
        print("Proc run")
        while 1:
            while len(children) < num_procs:
                try:
                    pid = os.fork()
                except:
                    print("failed to fork child")
                    time.sleep(1)
                    continue

                if pid == 0:
                    try:
                        print("Server Proxy", host, port)
                        qs = ServerProxy(host=host, port=port)
                        handle_one_job(qs)
                    finally:
                        os._exit(0)
                # print "forked", pid
                children.add(pid)

            try:
                pid, st = os.waitpid(-1, 0)
            except OSError:
                continue

            # print "done",  pid
            try:
                children.remove(pid)
            except KeyError:
                pass

    def run_with_gevent():
        from qs.misc import CallInLoop

        import gevent.pool

        pool = gevent.pool.Pool()
        for i in range(numgreenlets):
            pool.spawn(CallInLoop(1.0, start_worker))

        pool.join()

    if numgreenlets > 0:
        run_with_gevent()
    elif num_procs > 0:
        run_with_procs()
    elif numthreads > 0:
        run_with_threads()
    else:
        assert 0, "bad"


if __name__ == "__main__":

    class Commands:
        def rpc_divide(self, a, b):
            print("rpc_divide", (a, b))
            return old_div(a, b)

    main(Commands, num_procs=2)
