#! /usr/bin/env py.test

import cPickle
from qs import jobs
import gevent


def loaddump(obj):
    return cPickle.loads(cPickle.dumps(obj))


def test_job_defaults():
    j1 = jobs.job("render")
    assert j1.ttl == 3600
    assert j1.priority == 0


def test_job_pickle():
    j1 = jobs.job("render", payload=(1, 2, 3), priority=5, jobid=11, timeout=100, ttl=20)
    j2 = loaddump(j1)

    assert j2.channel == "render"
    assert j2.payload == (1, 2, 3)
    assert j2.priority == 5
    assert j2.jobid == 11
    assert j2.timeout == j1.timeout
    assert j2.ttl == 20
    assert j2.done == False


def test_job_unpickle_event():
    j = jobs.job("render")
    j = loaddump(j)
    assert not j.finish_event.is_set()

    j.done = True
    j = loaddump(j)
    assert j.finish_event.is_set()


def test_workq_pickle():
    w = jobs.workq()
    w.pushjob(jobs.job("render1"))
    w.pushjob(jobs.job("render2"))
    w2 = loaddump(w)
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


def test_stats():
    w = jobs.workq()
    joblst = [w.push("render", payload=i) for i in range(10)]
    stats = w.getstats()
    print "stats before", stats
    assert stats == {'count': 10, 'busy': {'render': 10}, 'channel2stat': {}, 'numjobs': 10}

    w.killjobs(joblst[1:])

    stats = w.getstats()
    print "stats after", stats
    assert stats == {'count': 10, 'busy': {'render': 1}, 'channel2stat': {'render': {'success': 0, 'killed': 9, 'timeout': 0, 'error': 0}}, 'numjobs': 10}
    print w.waitjobs(joblst[1:])

