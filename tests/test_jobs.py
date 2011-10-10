#! /usr/bin/env py.test

import cPickle
from qs import jobs
import gevent


def test_job_defaults():
    j1 = jobs.job("render")
    assert j1.ttl == 3600
    assert j1.priority == 0


def test_job_pickle():
    j1 = jobs.job("render", payload=(1, 2, 3), priority=5, jobid=11, timeout=100, ttl=20)
    j2 = cPickle.loads(cPickle.dumps(j1))

    assert j2.channel == "render"
    assert j2.payload == (1, 2, 3)
    assert j2.priority == 5
    assert j2.jobid == 11
    assert j2.timeout == j1.timeout
    assert j2.ttl == 20


def test_workq_pickle():
    w = jobs.workq()
    w.pushjob(jobs.job("render1"))
    w.pushjob(jobs.job("render2"))
    w2 = cPickle.loads(cPickle.dumps(w))
    print w.__dict__
    print w2.__dict__
    assert w.__dict__ == w2.__dict__


def test_pushjob_pop():
    w = jobs.workq()
    j1 = jobs.job("render", payload="hello")
    jid = w.pushjob(j1)
    assert jid == 1
    assert j1.jobid == 1
    assert len(w.channel2q["render"]) == 1
    assert len(w.timeoutq) == 1

    j = w.pop(["foo", "render", "bar"])
    assert j is j1

    g1 = gevent.spawn(w.pop, ["render"])
    gevent.sleep(0)


    j2 = jobs.job("render", payload=" world")
    w.pushjob(j2)
    g1.join()
    res = g1.get()
    assert res is j2


